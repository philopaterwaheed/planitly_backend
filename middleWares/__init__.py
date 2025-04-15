import hashlib
from datetime import datetime
import time
from fastapi import Request
from fastapi import Depends, HTTPException
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, ExpiredSignatureError, jwt  # Used for decoding JWT
from models import User, RateLimit
import os
from dotenv import load_dotenv
from models.locks import is_account_locked, lock_account
from firebase_admin import auth

load_dotenv()
# Get secret key from environment variables
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Define OAuth2 scheme
# for accepting tokins
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def check_request_limit(request: Request):
    """Check if the request is within rate limits"""
    is_allowed = await check_rate_limit(request)
    if not is_allowed:
        raise HTTPException(
            status_code=429, detail="Too many requests. Please try again later."
        )
    return True


async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    """Dependency to extract and validate JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")  # 'sub' holds the user ID

        if await check_request_limit(request):
            # Check if the request is within rate limits
            pass
        else:
            raise HTTPException(
                status_code=429, detail="Too many requests. Please try again later."
            )
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = User.objects(id=user_id).first()  # Fetch user from DB
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user  # Return user object for further use

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def admin_required(user: User = Depends(get_current_user)):
    """Dependency to ensure the user is an admin"""
    if not user.admin:
        raise HTTPException(status_code=403, detail="Admins only!")
    return user  # Return user if admin


async def create_access_token(user_id: str):
    """Generate a JWT token."""
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)

MAX_REQUESTS_PER_MINUTE = 60


def get_device_identifier(request: Request):
    """Generate a unique device identifier based on user agent and IP"""
    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host
    # Create a hash from user agent and IP
    device_hash = hashlib.md5(f"{user_agent}:{client_ip}".encode()).hexdigest()
    return device_hash


async def check_rate_limit(request: Request):
    """Check if the client has exceeded rate limits using MongoDB"""
    client_ip = request.client.host
    current_time = datetime.utcnow()
    reset_time = current_time + timedelta(minutes=1)

    # Find or create rate limit document
    rate_limit = RateLimit.objects(
        key=client_ip,
        reset_at__gt=current_time
    ).first()

    if not rate_limit:
        # Create new rate limit
        rate_limit = RateLimit(
            key=client_ip,
            count=1,
            reset_at=reset_time
        )
        rate_limit.save()
        return True

    # Increment count
    rate_limit.count += 1
    rate_limit.save()

    # Check if limit exceeded
    if rate_limit.count > MAX_REQUESTS_PER_MINUTE:  # 60 requests per minute
        return False

    return True


async def authenticate_user(username_or_email: str, password: str, request: Request = None):
    """Enhanced authenticate user with device tracking"""
    user = User.objects.filter(
        __raw__={"$or": [{"email": username_or_email},
                         {"username": username_or_email}]}
    ).first()

    if not user:
        return None, "username or email not found"

    # Check if account is locked
    is_locked = await is_account_locked(str(user.id))
    if is_locked:
        return None, "Account locked due to too many invalid attempts"

    if user.check_password(password):
        # Check email verification status
        if not user.email_verified and user.firebase_uid:
            try:
                # Check Firebase for email verification status
                firebase_user = auth.get_user(user.firebase_uid)
                if firebase_user.email_verified:
                    user.email_verified = True
                    user.save()
                else:
                    return None, "Email not verified. Please check your inbox for verification link."
            except auth.UserNotFoundError:
                # If Firebase check fails, fall back to local verification
                if not user.email_verified:
                    return None, "Email not verified. Please check your inbox for verification link."
    else:
        return None, "Invalid password"

        # Reset invalid attempts on successful login
        user.invalid_attempts = 0
        user.save()

        # Add device if request provided
        if request:
            device_id = get_device_identifier(request)
            # Check if device limit reached
            if device_id not in user.devices and len(user.devices) >= 5:
                return None, "Maximum devices reached for this account"

            # Add device if not already registered
            if device_id not in user.devices:
                user.devices.append(device_id)
                user.save()

        return user, None

    # Increment invalid attempts on failure
    user.invalid_attempts += 1
    user.save()

    # Lock account if too many invalid attempts
    if user.invalid_attempts >= 10:
        await lock_account(str(user.id))

    return None, "Invalid credentials"


async def verify_device(request: Request, current_user: User = Depends(get_current_user)):
    """Verify that the current device is registered for this user"""
    device_id = get_device_identifier(request)
    if device_id not in current_user.devices:
        raise HTTPException(
            status_code=403,
            detail="Unrecognized device. Please login again."
        )
    return current_user
