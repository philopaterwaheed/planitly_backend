from fastapi import APIRouter, Depends, HTTPException, status
from bson import json_util
from models import Subject_db
from middleWares import get_current_user, admin_required
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db
from mongoengine.errors import DoesNotExist

router = APIRouter(prefix="/components", tags=["Components"])

@router.post("/", dependencies=[Depends(get_current_user)], status_code=status.HTTP_201_CREATED)
async def create_component(data: dict, current_user: User = Depends(get_current_user)):
    # check if the component already exists
    if 'id' in data and Component.load_from_db(data['id']):
        raise HTTPException(
            status_code=400, detail="Component with this ID already exists")

    # check if the host subject id exists
    if 'host_subject' not in data:
        raise HTTPException(status_code=400, detail="Host subject is required")

    # check if the host subject exists
    host_subject = Subject.load_from_db(data['host_subject'])
    if not host_subject:
        raise HTTPException(status_code=404, detail="Host subject not found")

    if 'comp_type' not in data:
        raise HTTPException(
            status_code=400, detail="Component type is required")

    component = Component(**data, owner=current_user.id)
    component.save_to_db()
    host_subject.components.append(component.id)
    host_subject.save_to_db()
    return component.to_json()

@router.get("/{component_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user)])
async def get_component_by_id(component_id: str):
    """Retrieve a component by its ID."""
    try:
        component = Component_db.objects.get(id=component_id)
        return json_util.loads(component.to_mongo())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Component not found")

@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user), Depends(admin_required)])
async def get_all_components():
    """Retrieve all components (Admin Only)."""
    components = Component_db.objects()
    return json_util.loads(json_util.dumps([comp.to_mongo() for comp in components]))

@router.delete("/{component_id}", status_code=status.HTTP_200_OK)
async def delete_component(component_id: str, current_user=Depends(get_current_user)):
    """Delete a component and remove it from its host subject."""
    try:
        component = Component_db.objects.get(id=component_id)
        if str(current_user.id) == str(component.owner) or current_user.admin:
            host_subject = Subject_db.objects.get(id=component.host_subject.id)
            host_subject.components.remove(component_id)
            host_subject.save()
            component.delete()
            return {"message": "Component deleted successfully", "id": component_id}
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this component")
    except DoesNotExist:
        raise HTTPException(
            status_code=404, detail="Component or Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")
