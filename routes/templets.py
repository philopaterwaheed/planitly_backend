from fastapi import APIRouter, HTTPException, status, Depends
from models.templets import CustomTemplate_db
from models.component import PREDEFINED_COMPONENT_TYPES
from models.widget import Widget
from middleWares import verify_device
from mongoengine.errors import NotUniqueError, ValidationError

router = APIRouter(prefix="/custom-templates", tags=["templates"])

def validate_component_data(comp_type, data):
    """Validate component data against its type."""
    if comp_type not in PREDEFINED_COMPONENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid component type: {comp_type}")
    expected = PREDEFINED_COMPONENT_TYPES[comp_type]
    # Simple types
    if comp_type in ["int", "str", "bool", "date"]:
        if "item" not in data:
            raise HTTPException(status_code=400, detail=f"Component data for type '{comp_type}' must have 'item' field.")
    # Array types
    elif comp_type.startswith("Array"):
        if "type" not in data:
            raise HTTPException(status_code=400, detail=f"Component data for type '{comp_type}' must have 'type' field.")
    # Pair
    elif comp_type == "pair":
        if "key" not in data or "value" not in data:
            raise HTTPException(status_code=400, detail="Component data for type 'pair' must have 'key' and 'value' fields.")
    # Array_of_pairs
    elif comp_type == "Array_of_pairs":
        if "type" not in data or not isinstance(data["type"], dict):
            raise HTTPException(status_code=400, detail="Component data for type 'Array_of_pairs' must have 'type' dict.")
    # Add more as needed

def validate_widget_data(widget_type, data):
    """Validate widget data using Widget.validate_widget_type logic."""
    try:
        Widget.validate_widget_type(widget_type, None, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Widget data validation failed: {str(e)}")

def validate_template_structure(template_data):
    if not isinstance(template_data, dict):
        raise HTTPException(status_code=400, detail="Template data must be a dictionary.")

    # Components validation
    components = template_data.get("components")
    if not isinstance(components, list) or not components:
        raise HTTPException(status_code=400, detail="Template must include a non-empty 'components' list.")

    for comp in components:
        if not isinstance(comp, dict):
            raise HTTPException(status_code=400, detail="Each component must be a dictionary.")
        for field in ("name", "type", "data"):
            if field not in comp:
                raise HTTPException(status_code=400, detail=f"Component missing required field: '{field}'.")
        if not isinstance(comp["name"], str) or not comp["name"]:
            raise HTTPException(status_code=400, detail="Component 'name' must be a non-empty string.")
        if not isinstance(comp["type"], str) or not comp["type"]:
            raise HTTPException(status_code=400, detail="Component 'type' must be a non-empty string.")
        if not isinstance(comp["data"], dict):
            raise HTTPException(status_code=400, detail="Component 'data' must be a dictionary.")
        # Validate component data matches its type
        validate_component_data(comp["type"], comp["data"])

    # Widgets validation (optional)
    widgets = template_data.get("widgets", [])
    if widgets:
        if not isinstance(widgets, list):
            raise HTTPException(status_code=400, detail="'widgets' must be a list.")
        for widget in widgets:
            if not isinstance(widget, dict):
                raise HTTPException(status_code=400, detail="Each widget must be a dictionary.")
            for field in ("name", "type", "data"):
                if field not in widget:
                    raise HTTPException(status_code=400, detail=f"Widget missing required field: '{field}'.")
            if not isinstance(widget["name"], str) or not widget["name"]:
                raise HTTPException(status_code=400, detail="Widget 'name' must be a non-empty string.")
            if not isinstance(widget["type"], str) or not widget["type"]:
                raise HTTPException(status_code=400, detail="Widget 'type' must be a non-empty string.")
            if not isinstance(widget["data"], dict):
                raise HTTPException(status_code=400, detail="Widget 'data' must be a dictionary.")
            # Validate widget data matches its type
            validate_widget_data(widget["type"], widget["data"])

    # Category validation (optional)
    category = template_data.get("category")
    if category is not None and (not isinstance(category, str) or not category):
        raise HTTPException(status_code=400, detail="If provided, 'category' must be a non-empty string.")

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_custom_template(data: dict, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    name = data.get("name")
    template_data = data.get("data")
    description = data.get("description", "")
    category = data.get("category") or "Uncategorized"

    if not name or not template_data:
        raise HTTPException(status_code=400, detail="Name and data are required.")

    # Enhanced validation for template structure
    validate_template_structure(template_data)

    try:
        template = CustomTemplate_db(
            owner=current_user.id,
            name=name,
            description=description,
            data=template_data,
            category=category 
        )
        template.save()
        return {"message": "Custom template created successfully", "template": template.to_mongo().to_dict()}
    except NotUniqueError:
        raise HTTPException(status_code=409, detail="Template name already exists for this user.")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")

@router.get("/", status_code=status.HTTP_200_OK)
async def list_custom_templates(user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    templates = CustomTemplate_db.objects(owner=current_user.id)
    return [tpl.to_mongo().to_dict() for tpl in templates]

@router.put("/{template_id}", status_code=status.HTTP_200_OK)
async def update_custom_template(template_id: str, data: dict, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    template = CustomTemplate_db.objects(id=template_id, owner=current_user.id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    if "name" in data:
        template.name = data["name"]
    if "description" in data:
        template.description = data["description"]
    if "data" in data:
        validate_template_structure(data["data"])
        template.data = data["data"]

    try:
        template.save()
        return {"message": "Template updated successfully", "template": template.to_mongo().to_dict()}
    except NotUniqueError:
        raise HTTPException(status_code=409, detail="Template name already exists for this user.")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")

@router.delete("/{template_id}", status_code=status.HTTP_200_OK)
async def delete_custom_template(template_id: str, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    template = CustomTemplate_db.objects(id=template_id, owner=current_user.id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")
    template.delete()
    return {"message": "Template deleted successfully"}