from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from middleWares import verify_device, admin_required
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db, ArrayItem_db
from mongoengine.errors import DoesNotExist

router = APIRouter(prefix="/components", tags=["Components"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_component(data: dict, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    try:
        # check if the component already exists
        if 'id' in data and Component.load_from_db(data['id']):
            raise HTTPException(
                status_code=400, detail="Component with this ID already exists")

        # check if the host subject id exists
        if 'host_subject' not in data:
            raise HTTPException(
                status_code=400, detail="Host subject is required")

        # check if the host subject exists
        host_subject = Subject.load_from_db(data['host_subject'])
        if not host_subject:
            raise HTTPException(
                status_code=404, detail="Host subject not found")

        if 'comp_type' not in data:
            raise HTTPException(
                status_code=400, detail="Component type is required")

        component = Component(**data, owner=current_user.id)
        component.save_to_db()
        if component.comp_type in ["Array_type", "Array_generic"] and "data" in data:
            for item in data["data"].get("items", []):
                ArrayItem_db(component=component.id, value=str(item)).save()
        host_subject.components.append(component.id)
        host_subject.save_to_db()
        return component.to_json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{component_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_component_by_id(component_id: str):
    """Retrieve a component by its ID."""
    try:
        component = Component.load_from_db(component_id)
        if component.comp_type in ["Array_type", "Array_generic"]:
            component_data = component.to_json()
            component_data["items"] = component.get_array_items()
            return component_data
        return component.to_json()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Component not found")


@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device), Depends(admin_required)])
async def get_all_components():
    """Retrieve all components (Admin Only)."""
    components = Component_db.objects()
    return [comp.to_mongo() for comp in components]


@router.delete("/{component_id}", status_code=status.HTTP_200_OK)
async def delete_component(component_id: str, user_device: tuple =Depends(verify_device)):
    """Delete a component and remove it from its host subject."""
    current_user = user_device[0]
    try:

        component = Component_db.objects.get(id=component_id)
        # Check if component exists
        if not component:
            raise HTTPException(
                status_code=404, detail="Component not found")

        # Load the subject to check ownership
        subject = Subject.load_from_db(component.host_subject)

        # Check if user owns the subject/component

        # Check if component is deletable
        if not component.is_deletable:
            raise HTTPException(
                status_code=403, detail="This component cannot be deleted")
        if str(current_user.id) == str(component.owner) or current_user.admin:
            host_subject = Subject_db.objects.get(id=component.host_subject.id)
            host_subject.components.remove(component_id)
            host_subject.save()
            component.delete()
            return {"message": "Component deleted successfully", "id": component_id}
        else:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this component")
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this component")
    except DoesNotExist:
        raise HTTPException(
            status_code=404, detail="Component or Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")
