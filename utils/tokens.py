import hashlib
from consts import env_variables
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, ExpiredSignatureError, jwt  # Used for decoding JWT
import time
from datetime import datetime, timedelta
from models import RefreshToken, User

# Get secret key from environment variables
JWT_SECRET_KEY = env_variables.get("JWT_SECRET", "supersecretkey")
REJWT_SECRET_KEY = env_variables.get("REJWT_SECRET", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 10
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Define OAuth2 scheme
# for accepting tokins
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def create_access_token(user_id: str):
    """Generate a short-lived JWT access token."""
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


async def create_refresh_token(user_id: str, device_id: str):
    """Generate a long-lived JWT refresh token and store in database."""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token_id = hashlib.sha256(f"{user_id}:{device_id}:{
                              time.time()}".encode()).hexdigest()

    # Create payload with token ID for future revocation
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "jti": token_id,  # JWT ID for token identification
        "device": device_id
    }

    # Create JWT
    refresh_token_jwt = jwt.encode(
        payload, REJWT_SECRET_KEY, algorithm=ALGORITHM)

    # Store token in database for revocation capability
    refresh_token = RefreshToken(
        token_id=token_id,
        user_id=user_id,
        device_id=device_id,
        expires_at=expire,
        revoked=False
    )
    refresh_token.save()

    return refresh_token_jwt


async def verify_refresh_token(refresh_token: str):
    """Verify that a refresh token is valid and not revoked"""
    try:
        # Decode the refresh token
        payload = jwt.decode(
            refresh_token, REJWT_SECRET_KEY, algorithms=[ALGORITHM])
        # Validate token type
        if payload.get("type") != "refresh":
            return None, "Invalid token type"
        user_id = payload.get("sub")
        token_id = payload.get("jti")
        device_id = payload.get("device")
        if not all([user_id, token_id, device_id]):
            return None, "Invalid token format"
        # Check if token exists and is not revoked
        token_record = RefreshToken.objects(
            token_id=token_id,
            user_id=user_id,
            device_id=device_id,
            revoked=False
        ).first()
        if not token_record:
            return None, "Token has been revoked or does not exist"
        # Get the user
        user = User.objects(id=user_id).first()
        if not user:
            return None, "User not found"
        return user, None
    except ExpiredSignatureError:
        return None, "Token has expired"
    except JWTError:
        return None, "Invalid token"
