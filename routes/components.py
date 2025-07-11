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
        allowed_widget_type = data.get("allowed_widget_type", "any")  # New field

        # Validate required fields
        if not name or not comp_type or not host_subject_id:
            raise HTTPException(status_code=400, detail="Name, type, and host_subject are required.")

        # Validate component type
        if comp_type not in PREDEFINED_COMPONENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid component type '{comp_type}'. Allowed types are: {', '.join(PREDEFINED_COMPONENT_TYPES.keys())}."
            )

        # Load the host subject
        host_subject = Subject.load_from_db(host_subject_id)
        if not host_subject:
            raise HTTPException(status_code=404, detail="Host subject not found.")

        # Check authorization
        if current_user.id != host_subject.owner and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to create this component.")

        # Get initial data
        initial_data = data.get("data", PREDEFINED_COMPONENT_TYPES[comp_type])

        # Use the subject's add_component method
        result = await host_subject.add_component(
            component_id=component_id,
            name=name,
            comp_type=comp_type,
            owner=current_user.id,
            data=initial_data,
            allowed_widget_type=allowed_widget_type
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])

        return {"message": "Component created successfully", "id": component_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/{component_id}", status_code=status.HTTP_200_OK)
async def get_component(
    component_id: str,
    user_device: tuple = Depends(verify_device)
):
    current_user, _ = user_device
    try:

        component = Component.load_from_db(component_id)
        if not component:
            raise HTTPException(status_code=404, detail="Component not found.")
        if component.owner != current_user.id and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to access this component.")
        return component.get_component()

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
                    host_id=component_id,
                    host_type='component'
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


@router.put("/{component_id}", status_code=status.HTTP_200_OK)
async def update_component(component_id: str, data: dict, user_device: tuple = Depends(verify_device)):
    """
    Update a component's data. Prevent editing reference fields/lists such as host_subject, owner, or id.
    Only the 'data' and 'name' fields can be updated.
    """
    current_user = user_device[0]
    try:
        component = Component_db.objects.get(id=component_id)
        if not component:
            raise HTTPException(status_code=404, detail="Component not found.")

        # Check ownership
        if str(current_user.id) != str(component.owner) and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to update this component.")

        # Prevent changing reference fields/lists
        forbidden_fields = {"host_subject", "owner", "id", "is_deletable", "comp_type"}
        if any(field in data for field in forbidden_fields):
            raise HTTPException(status_code=400, detail="Cannot update reference fields or lists.")

        # Only allow updating 'data' and 'name'
        updated = False
        if "data" in data:
            component.data = data["data"]
            updated = True
        if "name" in data:
            component.name = data["name"]
            updated = True

        if not updated:
            raise HTTPException(status_code=400, detail="No updatable fields provided (only 'data' and 'name' allowed).")

        component.save()
        return {"message": "Component updated successfully.", "id": component_id}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Component not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
