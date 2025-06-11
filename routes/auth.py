from fastapi import HTTPException
from fastapi import APIRouter, HTTPException, status, Request, Response, Depends
import uuid
import re
import datetime
from mongoengine.errors import NotUniqueError, ValidationError
from models import User, Subject, Component, FCMManager, RefreshToken,  Device_db  
from middleWares import authenticate_user, get_current_user,  get_device_identifier, verify_device
from utils import create_access_token, create_refresh_token, verify_refresh_token,  logout_user , get_ip_info
from models.templets import DEFAULT_USER_TEMPLATES
from errors import revert_firebase_user, UserLogutError
from fire import node_firebase
from errors import FirebaseAuthError
import user_agents
from firebase_admin import auth

router = APIRouter(prefix="/auth", tags=["Auth"])


async def create_default_subjects_for_user(user_id):
    """Create default non-deletable subjects for a new user and return their IDs."""
    try:
        subject_ids = {}
        for template_key, template_data in DEFAULT_USER_TEMPLATES.items():
            # Create a new subject with the template
            subject = Subject(
                name=template_data["name"],
                owner=user_id,
                template=template_key,
                is_deletable=template_data["is_deletable"],
                category=template_data.get("category", "system")
            )
            subject.save_to_db()
            if not subject.id:
                raise Exception(f"Failed to save subject: {template_data['name']}")

            subject_ids[template_key] = subject.id

            # Add the components from the template
            for comp_data in template_data["components"]:
                if "type" not in comp_data:
                    raise KeyError(f"Missing 'type' in component: {comp_data}")
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
                    if "type" not in widget_data:
                        raise KeyError(f"Missing 'type' in widget: {widget_data}")
                    reference_component = None
                    if "reference_component" in widget_data:
                        ref_comp_name = widget_data["reference_component"]
                        for comp_id in subject.components:
                            component = Component.load_from_db(comp_id)
                            if component and component.name == ref_comp_name:
                                reference_component = comp_id
                                break

                    await subject.add_widget(
                        widget_name=widget_data["name"],
                        widget_type=widget_data["type"],
                        data=widget_data.get("data", {}),
                        reference_component=reference_component,
                        is_deletable=widget_data.get("is_deletable", True)
                    )

        return subject_ids
    except KeyError as e:
        print(f"Error creating default subjects: {str(e)}")
        return []
    except Exception as e:
        print(f"Unexpected error creating default subjects: {str(e)}")
        return []


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: dict, request: Request):
    """Register a new user with device tracking."""
    try:
        username = user_data.get("username")
        email = user_data.get("email")
        password = user_data.get("password")
        firstname = user_data.get("firstName")
        lastname = user_data.get("lastName")
        phone_number = user_data.get("phoneNumber")
        birthday = user_data.get("birthday")

        if not username or not email or not password:
            raise HTTPException(
                status_code=400, detail="Username, email, and password are required."
            )

        if not re.match(r"^(?=.*[a-zA-Z])[a-zA-Z0-9_.-]+$", username):
            raise HTTPException(
                status_code=400,
                detail="Username must contain at least one letter and can only include letters, numbers, underscores, dots, and hyphens."
            )

        if not re.match(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&^#_+=<>.,;:|\\/-])[A-Za-z\d@$!%*?&^#_+=<>.,;:|\\/-]{8,}$", password):
            raise HTTPException(
                status_code=400, detail="Weak password. Must contain uppercase, lowercase, number, special character, and be at least 8 characters long."
            )

        if firstname and (not firstname.isalpha() or len(firstname) < 2 or len(firstname) > 19):
            raise HTTPException(
                status_code=400, detail="First name must contain only alphabetic characters and be between 2-19 characters long."
            )
        elif not firstname:
            raise HTTPException(
                status_code=400, detail="Missing first name"
            )

        if lastname and (not lastname.isalpha() or len(lastname) < 2 or len(lastname) > 19):
            raise HTTPException(
                status_code=400, detail="Last name must contain only alphabetic characters and be between 2-50 characters long."
            )
        elif not lastname:
            raise HTTPException(
                status_code=400, detail="Missing last name"
            )

        # Validate phone number structure
        if phone_number is not None:
            if not isinstance(phone_number, dict):
                raise HTTPException(
                    status_code=400, detail="Phone number must be a dictionary with country_code and number"
                )
            
            try:
                User.validate_phone_number(phone_number)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        elif not phone_number:
            raise HTTPException(
                status_code=400, detail="Missing phone number"
            )

        if birthday:
            try:
                if not isinstance(birthday, str):
                    birthday = datetime.strptime(birthday, "%Y-%m-%d %H:%M:%S")

                birthday_date = datetime.datetime.fromisoformat(birthday)
                if birthday_date > datetime.datetime.now():
                    raise HTTPException(
                        status_code=400, detail="Birthday cannot be in the future."
                    )
                if (datetime.datetime.now() - birthday_date).days < 13 * 365:
                    raise HTTPException(
                        status_code=400, detail="Users must be at least 13 years old."
                    )
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid birthday format. Use ISO format (YYYY-MM-DD)."
                )
        else: 
                raise HTTPException(
                    status_code=400, detail="Missing birthday"
                )

        try:
            user = User.objects.filter(
                __raw__={"$or": [{"email": email}, {"username": username}]}
            ).first()

            if user:
                raise HTTPException(
                    status_code=409, detail="Username or email already exists."
                )

            firebase_uid = (await node_firebase(email, password, "register")).json().get("firebase_uid")
            user = User(
                id=str(uuid.uuid4()),
                firebase_uid=firebase_uid,
                username=username,
                email=email,
                email_verified=False,
                firstname=firstname,
                lastname=lastname,
                birthday=birthday_date if birthday else None,
            )
            
            # Set phone number using the validation method
            user.set_phone_number(phone_number)
            user.save()

            # Create default subjects for the new user
            return {
                "message": "User registered successfully",
                "status_code": 201,
            }
        except FirebaseAuthError as e:
            raise e

    except ValidationError:
        await revert_firebase_user(firebase_uid)
        raise HTTPException(
            status_code=400, detail="Invalid data provided."
        )
    except NotUniqueError:
        await revert_firebase_user(firebase_uid)
        raise HTTPException(
            status_code=409, detail="Username or email already exists."
        )
    except FirebaseAuthError as e:
        raise HTTPException(
            status_code=e.status_code, detail=e.message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(user_data: dict, request: Request):
    try:
        username_or_email = user_data.get("usernameOremail")
        password = user_data.get("password")

        device_id = get_device_identifier(request)
        user_agent = request.headers.get("user-agent", "")
        agent_info = user_agents.parse(user_agent)
        device_name = f"{agent_info.device.family} {agent_info.os.family} {agent_info.os.version_string}"
        client_ip = request.client.host

        # Authenticate the user
        user, error_message = await authenticate_user(username_or_email, password, device_id)
        if not user:
            raise HTTPException(status_code=401, detail=error_message)

        # Check if email is verified and create default subjects if it's the first verified login
        if user.email_verified and not user.default_subjects:
            subject_ids = await create_default_subjects_for_user(str(user.id))
            user.default_subjects = subject_ids
            user.save()

        user_id_str = str(user.id)
        # Track the device in the database
        location = {}
        try:
            response = await get_ip_info(client_ip)
            if not response.status_code == 200:
                raise Exception(response)
            response = response.json()
            location = {
                "country": response.get("country", "Unknown"),
                "city": response.get("city", "Unknown"),
                "region": response.get("region", "Unknown"),
            }
        except Exception:
            location = {
                "country": "Unknown",
                "city": "Unknown",
                "region": "Unknown",
            }
        device = Device_db(
            user_id=user_id_str,
            device_name=device_name,
            device_id=device_id,
            user_agent=user_agent,
            location=location
        )
        device.last_used = datetime.datetime.utcnow()
        device.save()

        # Generate JWT tokens
        access_token = await create_access_token(user_id_str)

        # Get device ID for the refresh token
        refresh_token = await create_refresh_token(user_id_str, device_id)
        await FCMManager.send_login_notification(user, device_id)

        return {
            "message": "Login successful",
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "email_verified": user.email_verified,
            "defualt_subjects": user.default_subjects,
            "status": 201
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=500)



@router.post("/logout-device", status_code=status.HTTP_200_OK)
async def logout_device(request: Request, user_device: tuple = Depends(verify_device)):
    """Logout from a specific device"""
    try:
        current_user = user_device[0]
        current_device_id = user_device[1]

        # Check if the request body contains a device ID
        body = await request.json()
        device_id = body.get("device_id") if body else current_device_id

        if not device_id:
            raise HTTPException(
                status_code=400, detail="Device ID is required"
            )

        await logout_user(current_user, device_id)
        return {"message": "Device logged out successfully"}

    except HTTPException as he:
        raise he
    except UserLogutError as e:
        raise HTTPException(
            status_code=400, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-security", status_code=status.HTTP_200_OK)
async def reset_security(user_device: tuple = Depends(verify_device)):
    """Reset security settings for a user (clear invalid attempts)"""
    current_user = user_device[0]
    try:
        current_user.reset_invalid_attempts()
        return {"message": "Security settings reset successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices", status_code=status.HTTP_200_OK)
async def get_devices(user_device: tuple = Depends(verify_device)):
    """Get all registered devices for the user"""
    current_user = user_device[0]
    try:
        devices = Device_db.objects(user_id=str(current_user.id))
        return {
            "devices": [
                {
                    "device_id": device.device_id,
                    "device_name": device.device_name,
                    "user_agent": device.user_agent,
                    "location": device.location,
                    "last_used": device.last_used
                }
                for device in devices
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-devices", status_code=status.HTTP_200_OK)
async def clear_all_devices(request: Request, user_device: tuple = Depends(get_current_user)):
    """Clear all registered devices except the current one"""
    current_user = user_device[0]
    current_device = user_device[1]
    try:
        for device in current_user.devices:
            if device.device_id != current_device:
                await logout_user(current_user, device.device_id)
        return {"message": "All other devices have been logged out"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-token", status_code=status.HTTP_201_CREATED)
async def refresh_token(request: Request, tokens: dict):
    """Refresh the access token using the refresh token."""
    try:
        # Verify the refresh token
        refresh_token = tokens.get("refreshToken")
        if not refresh_token:
            raise HTTPException(
                status_code=400, detail="Refresh token is required"
            )

        user, error_message = await verify_refresh_token(refresh_token)

        # If there's an error message, handle it
        if error_message:
            # Only handle invalid or revoked tokens
            if error_message in ["Token has expired", "Invalid token", "Token has been revoked or does not exist"]:
                device_id = get_device_identifier(request=request)

                # Search for the device in the RefreshToken document
                token_record = RefreshToken.objects(
                    device_id=device_id).first()
                if not token_record:
                    raise HTTPException(
                        status_code=401, detail="Device not found in refresh tokens."
                    )

                # Use the logout_user function to handle cleanup
                current_user = User.objects(id=token_record.user_id).first()
                if not current_user:
                    raise HTTPException(
                        status_code=404, detail="User not found for the device."
                    )

                await logout_user(current_user, device_id)
                raise HTTPException(
                    status_code=401, detail="Refresh token is invalid or revoked."
                )

            # Otherwise, report the original verification error
            raise HTTPException(status_code=401, detail=error_message)

        # Generate a new access token
        access_token = await create_access_token(str(user.id))
        return {"accessToken": access_token, "refreshToken": refresh_token}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def reset_password(user_data: dict):
    """
    Reset password by calling the Node.js forget-password endpoint.
    """
    try:
        email = user_data.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required.")
        # Make a POST request to the Node.js endpoint
        response = await node_firebase(email=email, operation="forgot-password")

        # Handle the response from the Node.js API
        if response.status_code == 200:
            return {"detail": "Password reset email sent successfully."}
    except FirebaseAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")
