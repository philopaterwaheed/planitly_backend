from fastapi import Depends, HTTPException
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, ExpiredSignatureError, jwt  # Used for decoding JWT
from models import User  # Your User model
import os
from dotenv import load_dotenv

load_dotenv()
# Get secret key from environment variables
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Define OAuth2 scheme
# for accepting tokins
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to extract and validate JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")  # 'sub' holds the user ID

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


async def authenticate_user(email: str, password: str):
    """Authenticate user and return user instance."""
    user = User.objects(email=email).first()
    if user and user.check_password(password):
        return user
    return None


async def create_access_token(user_id: str):
    """Generate a JWT token."""
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)
