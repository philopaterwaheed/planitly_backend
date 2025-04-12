from fastapi import APIRouter, HTTPException, status
import uuid
import re
import datetime
from mongoengine.errors import NotUniqueError, ValidationError
from models import User, Subject, Component, Widget
from middleWares import create_access_token, authenticate_user, get_current_user
from models.templets import DEFAULT_USER_TEMPLATES


router = APIRouter(prefix="/auth", tags=["Auth"])


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

        # Create default subjects for the new user
        subjects_created = await create_default_subjects_for_user(str(user.id))

        # Generate JWT token
        access_token = await create_access_token(user_id=str(user.id))

        return ({
            "message": "User registered successfully",
            "token": access_token,
            "default_subjects_created": subjects_created
        }), 201

    except ValidationError:
        raise HTTPException(
            status_code=400, detail="Invalid data provided.")
    except NotUniqueError:
        raise HTTPException(
            status_code=400, detail="User with this email already exists.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
