from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from middleWares import verify_device, admin_required
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db
from mongoengine.queryset.visitor import Q
from mongoengine.errors import DoesNotExist, ValidationError

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_subject(data: dict, current_user: User = Depends(verify_device)):
    # for if the user didn't create an id himself
    try:
        sub_id = data.get("id") or 0
        sub_name = data.get("name") or None
        sub_tem = data.get("template") or None
        if not sub_name:
            raise HTTPException(
                status_code=400, detail="Subject name is required")
        if Subject_db.objects(
            (Q(id=sub_id) | Q(name=data['name'], owner=current_user.id))
        ).first():
            raise HTTPException(
                status_code=400, detail="Subject with this ID or name already exists")

        # create a new subject from data and save it
        subject = Subject(**data, owner=current_user.id)
        if sub_tem:
            await subject.apply_template(sub_tem)
        subject.save_to_db()
        return subject.to_json()
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


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
async def get_user_subjects(user_id: str, current_user=Depends(verify_device)):
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
async def update_subject(subject_id: str, data: dict, current_user=Depends(verify_device)):
    """Update a subject by its ID."""
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


@router.delete("/{subject_id}", status_code=status.HTTP_200_OK)
async def delete_subject(subject_id: str, current_user=Depends(verify_device)):
    """Delete a subject and its associated components."""
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
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this subject")
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")
