from fastapi import HTTPException
from fastapi import APIRouter, HTTPException, status, Request, Response, Depends
import uuid
import re
import datetime
from mongoengine.errors import NotUniqueError, ValidationError
from models import User, Subject, Component, FCMManager
from middleWares import authenticate_user, get_current_user, check_rate_limit, get_device_identifier, admin_required, verify_device
from utils import create_access_token, create_refresh_token, verify_refresh_token, remove_refresh_token
from models.templets import DEFAULT_USER_TEMPLATES
from firebase_admin import auth as firebase_auth
import requests
from consts import env_variables
from errors import FirebaseRegisterError, revert_firebase_user
from fire import initialize_firebase
from firebase_admin import auth

router = APIRouter(prefix="/auth", tags=["Auth"])

if env_variables["DEV"]:
    print("Using local Firebase URL")
    fire_url = "http://localhost:3000/api/node/firebase_register"
else:
    print("Using production Firebase URL")
    fire_url = "https://planitly-backend.vercel.app/api/node/firebase_register"


async def node_firebase(email: str, password: str):
    try:
        data = {"email": email, "password": password}
        response = requests.post(fire_url, json=data)

        if response.status_code != 201:
            try:
                error_msg = response.json().get("error", response.text)
            except Exception:
                error_msg = response.text

            raise FirebaseRegisterError(
                message=error_msg,
                status_code=response.status_code
            )

        return response.json().get("firebase_uid")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))


async def create_default_subjects_for_user(user_id):
    """Create default non-deletable subjects for a new user."""
    try:
        for template_key, template_data in DEFAULT_USER_TEMPLATES.items():
            # Create a new subject with the template
            subject = Subject(
                name=template_data["name"],
                owner=user_id,
                template=template_key,
                is_deletable=template_data["is_deletable"]
            )
            subject.save_to_db()

            # Add the components from the template
            for comp_data in template_data["components"]:
                # For date components, set to current date
                if comp_data["type"] == "date" and comp_data["name"] == "Joined Date":
                    comp_data["data"]["item"] = datetime.datetime.now().isoformat()

                await subject.add_component(
                    component_name=comp_data["name"],
                    component_type=comp_data["type"],
                    data=comp_data["data"],
                    is_deletable=comp_data.get("is_deletable", True)
                )

            # Add widgets from the template if they exist
            if "widgets" in template_data:
                for widget_data in template_data["widgets"]:
                    # Check if widget requires a reference to a component
                    reference_component = None
                    if "reference_component" in widget_data:
                        # Find the component ID by name
                        ref_comp_name = widget_data["reference_component"]
                        for comp_id in subject.components:
                            component = Component.load_from_db(comp_id)
                            if component and component.name == ref_comp_name:
                                reference_component = comp_id
                                break

                    # Add the widget to the subject
                    await subject.add_widget(
                        widget_type=widget_data["type"],
                        data=widget_data.get("data", {}),
                        reference_component=reference_component,
                        is_deletable=widget_data.get("is_deletable", True)
                    )

        return True
    except Exception as e:
        print(f"Error creating default subjects: {str(e)}")
        return False


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: dict, request: Request):
    """Register a new user with device tracking."""
    # todo add this to the get user

    try:
        username = user_data.get("username")
        email = user_data.get("email")
        password = user_data.get("password")

        if not username or not email or not password:
            raise HTTPException(
                status_code=400, detail="All fields are required.")

        if not re.match(r"^(?=.*[a-zA-Z])[a-zA-Z0-9_.-]+$", username):
            raise HTTPException(
                status_code=400,
                detail="Username must contain at least one letter and can only include letters, numbers, underscores, dots, and hyphens."
            )
        if not re.match(r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&^#_+=<>.,;:|\\/-])[A-Za-z\d@$!%*?&^#_+=<>.,;:|\\/-]{8,}$", password):
            raise HTTPException(
                status_code=400, detail="Weak password. Must contain uppercase, number, and special character.")
        try:
            firebase_uid = await node_firebase(email, password)
            user = User(id=str(uuid.uuid4()), firebase_uid=firebase_uid, username=username,
                        email=email, email_verified=False, password=password)
            user.hash_password()

            # Add the current device
            device_id = get_device_identifier(request)
            user.devices = [device_id]  # First device

            user.save()

            # Create default subjects for the new user
            subjects_created = await create_default_subjects_for_user(str(user.id))
            return ({
                "message": "User registered successfully",
                "default_subjects_created": subjects_created,
                "status_code": 201
            })
        except FirebaseRegisterError as e:
            raise e

    except ValidationError:
        await revert_firebase_user(firebase_uid)
        raise HTTPException(
            status_code=400, detail="Invalid data provided.")
    except NotUniqueError:
        await revert_firebase_user(firebase_uid)
        raise HTTPException(
            status_code=409, detail="username or email already exists.")
    except FirebaseRegisterError as e:
        raise HTTPException(
            status_code=e.status_code, detail=e.message)
    except Exception as e:
        await revert_firebase_user(firebase_uid)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(user_data: dict, request: Request):
    try:
        username_or_email = user_data.get("usernameOremail")
        password = user_data.get("password")

        user, error_message = await authenticate_user(username_or_email, password, request)
        if not user:
            raise HTTPException(
                status_code=401, detail=error_message)

        # Generate JWT tokens
        access_token = await create_access_token(str(user.id))

        # Get device ID for the refresh token
        device_id = get_device_identifier(request)
        user_id_str = str(user.id)
        refresh_token = await create_refresh_token(user_id_str, device_id)
        await FCMManager.send_login_notification(user_id_str, device_id)

        return {
            "message": "Login successful",
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "email_verified": user.email_verified,
            "status": 201
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=500)


@router.post("/logout-device", status_code=status.HTTP_200_OK)
async def logout_device(device_data: dict, current_user: User = Depends(get_current_user)):
    """Logout from a specific device"""
    try:
        device_id = device_data.get("device_id")
        if not device_id:
            raise HTTPException(
                status_code=400, detail="Device ID is required")

        success = await current_user.remove_device(device_id)
        await FCMManager.remove_token(str(current_user.id), device_id)
        if not success:
            raise HTTPException(status_code=404, detail="Device not found")

        return {"message": "Device logged out successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-security", status_code=status.HTTP_200_OK)
async def reset_security(current_user: User = Depends(verify_device)):
    """Reset security settings for a user (clear invalid attempts)"""
    try:
        current_user.reset_invalid_attempts()
        return {"message": "Security settings reset successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices", status_code=status.HTTP_200_OK)
async def get_devices(current_user: User = Depends(get_current_user)):
    """Get all registered devices for the user"""
    try:
        return {"devices": current_user.devices}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-devices", status_code=status.HTTP_200_OK)
async def clear_all_devices(request: Request, current_user: User = Depends(get_current_user)):
    """Clear all registered devices except the current one"""
    try:
        # Keep only the current device
        current_device = get_device_identifier(request)
        if current_device in current_user.devices:
            current_user.devices = [current_device]
        else:
            current_user.devices = []

        current_user.save()
        return {"message": "All other devices have been logged out"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-token", status_code=status.HTTP_200_OK)
async def refresh_token(tokens: dict):
    """Refresh the access token using the refresh token"""
    try:
        # Verify the refresh token
        refresh_token = tokens.get("refreshToken")
        if not refresh_token:
            raise HTTPException(
                status_code=400, detail="Refresh token is required")

        user, error_message = await verify_refresh_token(refresh_token)

        # If there's an error message, handle it
        if error_message:
            # Try to remove the token regardless of error type
            removed, remove_error = await remove_refresh_token(refresh_token)
            if not removed:
                # If there was an error removing the token, report that
                raise HTTPException(status_code=401, detail=remove_error)
            # Otherwise report the original verification error
            raise HTTPException(
                status_code=401, detail=error_message)

        # Generate a new access token
        access_token = await create_access_token(str(user.id))
        return {"accessToken": access_token, "refreshToken": refresh_token}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
