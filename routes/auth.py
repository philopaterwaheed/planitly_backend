from fastapi import APIRouter,  HTTPException, status
import uuid
import re
from mongoengine.errors import NotUniqueError, ValidationError
from models import User
from middleWares import create_access_token, authenticate_user




router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: dict):
    """Register a new user."""
    try:
        username = user_data.get("username")
        email = user_data.get("email")
        password = user_data.get("password")
        if not username or not email or not password:
            raise HTTPException(
                status_code=400, detail="All fields are required.")

        if not re.match(r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&^#_+=<>.,;:|\\/-])[A-Za-z\d@$!%*?&^#_+=<>.,;:|\\/-]{8,}$", password):
            raise HTTPException(
                status_code=400, detail="Weak password. Must contain uppercase, number, and special character.")

        user = User(id=str(uuid.uuid4()), username=username,
                    email=email, password=password)
        user.hash_password()
        user.save()

        # Generate JWT token
        access_token = await create_access_token(user_id=str(user.id))

        return ({
            "message": "User registered successfully",
            "token": access_token
        }), 201

    except ValidationError:
        return ({"message": "Invalid data", "status": "error"}), 400
    except NotUniqueError:
        return ({"message": "Username or Email already exist", "status": "error"}), 400
    except Exception as e:
        return ({"error": str(e)}), 500


@router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(user_data: dict):
    try:
        print(user_data)
        email = user_data.get("email")
        password = user_data.get("password")
        user = await authenticate_user(email, password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Generate JWT token
        access_token = await create_access_token(
            str(user.id)
        )

        return ({
            "message": "Login successful",
            "token": access_token
        }), 200

    except Exception as e:
        raise HTTPException(detail={"error": str(e)}, status_code=500)



