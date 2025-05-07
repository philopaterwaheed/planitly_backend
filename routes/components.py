from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from middleWares import verify_device, admin_required
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db, ArrayItem_db
from mongoengine.errors import DoesNotExist
from models.arrayItem import Arrays
from models.component import PREDEFINED_COMPONENT_TYPES
import uuid

router = APIRouter(prefix="/components", tags=["Components"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_component(data: dict, user_device: tuple = Depends(verify_device)):
    current_user, device_id = user_device
    try:
        component_id = data.get("id", str(uuid.uuid4()))
        name = data.get("name")
        comp_type = data.get("type")
        host_subject_id = data.get("host_subject")

        # Validate required fields
        if not name or not comp_type or not host_subject_id:
            raise HTTPException(status_code=400, detail="Name, type, and host_subject are required.")

        # Validate component type
        if comp_type not in PREDEFINED_COMPONENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid component type '{comp_type}'. Allowed types are: {', '.join(PREDEFINED_COMPONENT_TYPES.keys())}."
            )

        initial_data = data.get("data", PREDEFINED_COMPONENT_TYPES[comp_type])
        host_subject = Subject_db.objects(id=host_subject_id).first()
        if not host_subject:
            raise HTTPException(status_code=404, detail="Host subject not found.")

        if current_user.id != host_subject.owner and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to create this component.")

        # Create the component
        component_data = {
            "id": component_id,
            "name": name,
            "host_subject": host_subject_id,
            "comp_type": comp_type,
            "owner": current_user.id
        }
        if initial_data is not None:
            component_data["data"] = initial_data

        component = Component_db(**component_data)

        # Handle Array_type and Array_generic components
        if comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]:
            array_metadata_result = Arrays.create_array(
                user_id=current_user.id,
                component_id=component_id,
                array_name=name,
            )
            if not array_metadata_result["success"]:
                raise HTTPException(status_code=500, detail=array_metadata_result["message"])

        component.save()
        return {"message": "Component created successfully", "id": component_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/{component_id}", status_code=status.HTTP_200_OK)
async def get_component(
    component_id: str,
    user_device: tuple = Depends(verify_device),
    page: int = 0,
    page_size: int = 10
):
    current_user, device_id = user_device
    try:
        component = Component_db.objects.get(id=component_id)
        if component.owner != current_user.id and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to access this component.")

        # Handle Array_type components with optional pagination
        if component.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"] and component.array_metadata:
            array_result = Arrays.get_array(
                user_id=current_user.id,
                component_id=component_id,
                page=page,
                page_size= page_size
            )
            if not array_result["success"]:
                raise HTTPException(status_code=500, detail=array_result["message"])

            component_data = component.to_mongo().to_dict()
            component_data["array_items"] = array_result["array"]
            component_data["pagination"] = {
                "page": page,
                "page_size": page_size,
                "total": array_result.get("total", len(array_result["array"]))
            }
            return component_data

        return component.to_mongo().to_dict()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Component not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device), Depends(admin_required)])
async def get_all_components():
    """Retrieve all components (Admin Only)."""
    components = Component_db.objects()
    return [comp.to_mongo() for comp in components]

@router.delete("/{component_id}", status_code=status.HTTP_200_OK)
async def delete_component(component_id: str, user_device: tuple = Depends(verify_device)):
    """Delete a component and remove it from its host subject."""
    current_user = user_device[0]
    try:
        component = Component_db.objects.get(id=component_id)
        # Check if component exists
        if not component:
            raise HTTPException(status_code=404, detail="Component not found")

        # Load the subject to check ownership
        subject = Subject.load_from_db(component.host_subject)

        # Check if component is deletable
        if not component.is_deletable:
            raise HTTPException(status_code=403, detail="This component cannot be deleted")

        # Check if user owns the subject/component
        if str(current_user.id) == str(component.owner) or current_user.admin:
            # Handle deletion of array metadata and associated array items for array types
            if component.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]:
                array_metadata_result = Arrays.delete_array(
                    user_id=current_user.id,
                    component_id=component_id
                )
                if not array_metadata_result["success"]:
                    raise HTTPException(status_code=500, detail=array_metadata_result["message"])

            # Remove the component from its host subject
            host_subject = Subject_db.objects.get(id=component.host_subject.id)
            host_subject.components.remove(component_id)
            host_subject.save()

            # Delete the component
            component.delete()
            return {"message": "Component deleted successfully", "id": component_id}
        else:
            raise HTTPException(status_code=403, detail="Not authorized to delete this component")
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Component or Subject not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
