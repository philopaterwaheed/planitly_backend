from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from middleWares import get_current_user, admin_required
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db
from mongoengine.queryset.visitor import Q
from mongoengine.errors import DoesNotExist

router = APIRouter(prefix="/subjects", tags=["Subjects"])

# create a new subject route
@router.post("/", dependencies=[Depends(get_current_user)], status_code=status.HTTP_201_CREATED)
async def create_subject(data: dict, current_user: User = Depends(get_current_user)):
    # for if the user didn't create an id himself
    sub_id = data.get("id") or 0
    if Subject_db.objects(
        (Q(id=sub_id) | Q(name=data['name'], owner=current_user.id))
    ).first():
        raise HTTPException(
            status_code=400, detail="Subject with this ID or name already exists")

    if data.get('template'):
        # todo create a subject from a template
        pass
    # create a new subject from data and save it
    subject = Subject(**data, owner=current_user.id)
    subject.save_to_db()
    return subject.to_json()

@router.get("/{subject_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user)])
async def get_subject(subject_id: str):
    """Retrieve a subject by its ID."""
    try:
        subject = Subject_db.objects.get(id=subject_id)
        return subject.to_mongo()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")

# get all subjects route
@router.get("/", dependencies=[Depends(get_current_user), Depends(admin_required)], status_code=status.HTTP_200_OK)
async def get_all_subjects():
    """Retrieve all subjects (Admin Only)."""
    subjects = Subject_db.objects()
    return [subj.to_mongo() for subj in subjects]

# get by User_id subjects route
@router.get("/user/{user_id}", status_code=status.HTTP_200_OK)
async def get_user_subjects(user_id: str, current_user=Depends(get_current_user)):
    """Retrieve subjects for a specific user."""
    if str(current_user.id) == user_id or current_user.admin:
        subjects = Subject_db.objects(owner=user_id)
        return [subj.to_mongo() for subj in subjects]
    raise HTTPException(
        status_code=403, detail="Not authorized to access these subjects")

@router.delete("/{subject_id}", status_code=status.HTTP_200_OK)
async def delete_subject(subject_id: str, current_user=Depends(get_current_user)):
    """Delete a subject and its associated components."""
    try:
        subject = Subject_db.objects.get(id=subject_id)
        if str(current_user.id) == str(subject.owner) or current_user.admin:
            for comp in subject.components:
                comp.delete()
            subject.delete()
            return {"message": f"Subject and associated components with ID {subject_id} deleted successfully."}
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this subject")
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


