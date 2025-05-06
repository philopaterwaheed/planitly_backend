from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from middleWares import verify_device, admin_required
from models import User, Widget_db, Component, Subject, Subject_db,Category_db
from mongoengine.queryset.visitor import Q
from mongoengine.errors import DoesNotExist, ValidationError

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_subject(data: dict, user_device: tuple = Depends(verify_device)):
    """Create a new subject with an optional category."""
    current_user = user_device[0]
    try:
        sub_id = data.get("id") or 0
        sub_name = data.get("name") or None
        sub_tem = data.get("template") or None
        category_name = data.get("category") or None
        if not sub_name:
            raise HTTPException(status_code=400, detail="Subject name is required.")

        # Validate the category name
        if category_name:
            category = Category_db.objects(name=category_name, owner=current_user.id).first()
            if not category:
                raise HTTPException(status_code=404, detail=f"Category '{category_name}' not found.")

        subject = Subject(
            name=sub_name,
            owner=current_user.id,
            template=sub_tem,
            category=category_name,  # Store category name
        )
        if sub_tem:
            await subject.apply_template(sub_tem)
        subject.save_to_db()
        return subject.to_json()
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

#todo check the security of this route
@router.get("/{subject_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_subject(subject_id: str):
    """Retrieve a subject by its ID."""
    try:
        subject = Subject_db.objects.get(id=subject_id)
        return subject.to_mongo()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")


# get all subjects route
@router.get("/", dependencies=[Depends(verify_device), Depends(admin_required)], status_code=status.HTTP_200_OK)
async def get_all_subjects():
    try:
        """Retrieve all subjects (Admin Only)."""
        subjects = Subject_db.objects()
        return [subj.to_mongo() for subj in subjects]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# get by User_id subjects route


@router.get("/user/{user_id}", status_code=status.HTTP_200_OK)
async def get_user_subjects(user_id: str, user_device: tuple =Depends(verify_device)):
    current_user = user_device[0]
    try:
        """Retrieve subjects for a specific user."""
        if str(current_user.id) == user_id or current_user.admin:
            subjects = Subject_db.objects(owner=user_id)
            return [subj.to_mongo() for subj in subjects]
        raise HTTPException(
            status_code=403, detail="Not authorized to access these subjects")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{subject_id}", status_code=status.HTTP_200_OK)
async def update_subject(subject_id: str, data: dict, user_device: tuple =Depends(verify_device)):
    """Update a subject by its ID."""
    current_user = user_device[0]
    try:
        subject = Subject_db.objects.get(id=subject_id)
        if str(current_user.id) == str(subject.owner) or current_user.admin:
            subject.update(**data)
            return {"message": f"Subject with ID {subject_id} updated successfully."}
        raise HTTPException(
            status_code=403, detail="Not authorized to update this subject")
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{subject_id}/change-category", status_code=status.HTTP_200_OK)
async def change_subject_category(subject_id: str, data: dict, user_device: tuple = Depends(verify_device)):
    """Change the category of a subject."""
    current_user = user_device[0]
    try:
        new_category_name = data.get("category")
        if not new_category_name:
            raise HTTPException(status_code=400, detail="New category name is required.")

        # Fetch the subject
        subject = Subject_db.objects.get(id=subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found.")

        # Check if the subject has a template
        if subject.template:
            raise HTTPException(
                status_code=403,
                detail="Subjects with templates cannot have their category changed."
            )

        # Validate the new category
        new_category = Category_db.objects(name=new_category_name, owner=current_user.id).first()
        if not new_category:
            raise HTTPException(status_code=404, detail=f"Category '{new_category_name}' not found.")

        # Update the subject's category
        subject.update(category=new_category_name)
        return {"message": f"Subject category updated to '{new_category_name}'."}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{subject_id}/remove-category", status_code=status.HTTP_200_OK)
async def remove_subject_category(subject_id: str, user_device: tuple = Depends(verify_device)):
    """Remove a subject from its category (set to 'Uncategorized')."""
    current_user = user_device[0]
    try:
        # Fetch the subject
        subject = Subject_db.objects.get(id=subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found.")

        # Check if the subject has a template
        if subject.template:
            raise HTTPException(
                status_code=403,
                detail="Subjects with templates cannot be removed from their category."
            )

        # Update the subject's category to 'Uncategorized'
        subject.update(category="Uncategorized")
        return {"message": "Subject category removed and set to 'Uncategorized'."}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{subject_id}", status_code=status.HTTP_200_OK)
async def delete_subject(subject_id: str, user_device: tuple =Depends(verify_device)):
    """Delete a subject and its associated components."""
    current_user = user_device[0]
    try:
        subject = Subject_db.objects.get(id=subject_id)
        # Check if subject exists
        if not subject:
            raise HTTPException(
                status_code=404, detail="Subject not found")

        # Check if subject is deletable
        if not subject.is_deletable:
            raise HTTPException(
                status_code=403, detail="This subject cannot be deleted")

        if str(current_user.id) == str(subject.owner) or current_user.admin:
            for widget in subject.widgets:
                widget.delete()
            for comp in subject.components:
                comp.delete()
            subject.delete()
            return {"message": f"Subject and associated components and widgets with ID {subject_id} deleted successfully."}
        else:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this subject")
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/{subject_id}/full-data", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_subject_full_data(subject_id: str, user_device: tuple = Depends(verify_device)):
    """Retrieve all data inside a subject, including its components and widgets."""
    current_user = user_device[0]
    try:
        # Fetch the subject
        subject = Subject_db.objects.get(id=subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check if the user is authorized to access the subject
        if str(current_user.id) != str(subject.owner) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this subject"
            )

        # Fetch components
        components = []
        try:
            components = [
                Component.load_from_db(component_id).get_component()
                for component_id in (subject.components or [])
            ]
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error loading components: {str(e)}"
            )

        # Fetch widgets
        widgets = []
        try:
            widgets = [
                widget.to_mongo().to_dict()
                for widget in Widget_db.objects(host_subject=subject.id)
            ]
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error loading widgets: {str(e)}"
            )

        # Combine subject, components, and widgets data
        full_data = {
            "subject": subject.to_mongo().to_dict(),
            "components": components,
            "widgets": widgets,
        }

        return full_data
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
