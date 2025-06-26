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

@router.post("/{template_id}/components", status_code=status.HTTP_201_CREATED)
async def add_component_to_template(
    template_id: str, 
    component_data: dict, 
    user_device: tuple = Depends(verify_device)
):
    """Add a component to a custom template with validation."""
    current_user = user_device[0]
    
    try:
        # Get the template
        template = CustomTemplate_db.objects(id=template_id, owner=current_user.id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Validate required fields
        component_name = component_data.get("name")
        component_type = component_data.get("type")
        component_data_field = component_data.get("data", {})
        is_deletable = component_data.get("is_deletable", True)
        
        if not component_name or not component_type:
            raise HTTPException(status_code=400, detail="Name and type are required")
        
        # Validate component type and data
        validate_component_data(component_type, component_data_field)
        
        # Check if component name already exists in template
        existing_components = template.data.get("components", [])
        if any(comp["name"] == component_name for comp in existing_components):
            raise HTTPException(status_code=409, detail=f"Component '{component_name}' already exists in template")
        
        # Create new component structure
        new_component = {
            "name": component_name,
            "type": component_type,
            "data": component_data_field,
            "is_deletable": is_deletable
        }
        
        # Add component to template
        existing_components.append(new_component)
        template.data["components"] = existing_components
        template.save()
        
        return {
            "message": "Component added to template successfully",
            "component": new_component
        }
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.post("/{template_id}/widgets", status_code=status.HTTP_201_CREATED)
async def add_widget_to_template(
    template_id: str,
    widget_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Add a widget to a custom template with validation."""
    current_user = user_device[0]
    
    try:
        # Get the template
        template = CustomTemplate_db.objects(id=template_id, owner=current_user.id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Validate required fields
        widget_name = widget_data.get("name")
        widget_type = widget_data.get("type")
        widget_data_field = widget_data.get("data", {})
        reference_component_name = widget_data.get("reference_component")
        is_deletable = widget_data.get("is_deletable", True)
        
        if not widget_name or not widget_type:
            raise HTTPException(status_code=400, detail="Name and type are required")
        
        # Check if widget name already exists in template
        existing_widgets = template.data.get("widgets", [])
        if any(widget["name"] == widget_name for widget in existing_widgets):
            raise HTTPException(status_code=409, detail=f"Widget '{widget_name}' already exists in template")
        
        # Validate reference component if provided
        reference_component = None
        if reference_component_name:
            existing_components = template.data.get("components", [])
            reference_component = next(
                (comp for comp in existing_components if comp["name"] == reference_component_name), 
                None
            )
            if not reference_component:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Reference component '{reference_component_name}' not found in template"
                )
        
        # Validate widget type and data
        validate_widget_data_for_template(widget_type, widget_data_field, reference_component)
        
        # Create new widget structure
        new_widget = {
            "name": widget_name,
            "type": widget_type,
            "data": widget_data_field,
            "is_deletable": is_deletable
        }
        
        if reference_component_name:
            new_widget["reference_component"] = reference_component_name
        
        # Add widget to template
        existing_widgets.append(new_widget)
        template.data["widgets"] = existing_widgets
        template.save()
        
        return {
            "message": "Widget added to template successfully",
            "widget": new_widget
        }
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{template_id}/components/{component_name}", status_code=status.HTTP_200_OK)
async def remove_component_from_template(
    template_id: str,
    component_name: str,
    user_device: tuple = Depends(verify_device)
):
    """Remove a component from a custom template."""
    current_user = user_device[0]
    
    try:
        # Get the template
        template = CustomTemplate_db.objects(id=template_id, owner=current_user.id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Find and remove the component
        existing_components = template.data.get("components", [])
        component_to_remove = None
        updated_components = []
        
        for comp in existing_components:
            if comp["name"] == component_name:
                component_to_remove = comp
                # Check if component is deletable
                if not comp.get("is_deletable", True):
                    raise HTTPException(status_code=400, detail="Component is not deletable")
            else:
                updated_components.append(comp)
        
        if not component_to_remove:
            raise HTTPException(status_code=404, detail="Component not found in template")
        
        # Check if any widgets reference this component
        existing_widgets = template.data.get("widgets", [])
        referencing_widgets = [
            widget["name"] for widget in existing_widgets 
            if widget.get("reference_component") == component_name
        ]
        
        if referencing_widgets:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete component '{component_name}' - it is referenced by widgets: {', '.join(referencing_widgets)}"
            )
        
        # Update template
        template.data["components"] = updated_components
        template.save()
        
        return {"message": f"Component '{component_name}' removed from template successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{template_id}/widgets/{widget_name}", status_code=status.HTTP_200_OK)
async def remove_widget_from_template(
    template_id: str,
    widget_name: str,
    user_device: tuple = Depends(verify_device)
):
    """Remove a widget from a custom template."""
    current_user = user_device[0]
    
    try:
        # Get the template
        template = CustomTemplate_db.objects(id=template_id, owner=current_user.id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Find and remove the widget
        existing_widgets = template.data.get("widgets", [])
        widget_to_remove = None
        updated_widgets = []
        
        for widget in existing_widgets:
            if widget["name"] == widget_name:
                widget_to_remove = widget
                # Check if widget is deletable
                if not widget.get("is_deletable", True):
                    raise HTTPException(status_code=400, detail="Widget is not deletable")
            else:
                updated_widgets.append(widget)
        
        if not widget_to_remove:
            raise HTTPException(status_code=404, detail="Widget not found in template")
        
        # Update template
        template.data["widgets"] = updated_widgets
        template.save()
        
        return {"message": f"Widget '{widget_name}' removed from template successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


def validate_widget_data_for_template(widget_type, data, reference_component=None):
    """Validate widget data for template context with reference component validation."""
    from models.widget import Widget
    from models.component import PREDEFINED_COMPONENT_TYPES
    
    # Create a mock component object for validation if reference_component is provided
    mock_reference_component = None
    if reference_component:
        class MockComponent:
            def __init__(self, comp_data):
                self.comp_type = comp_data["type"]
                self.data = comp_data["data"]
                self.name = comp_data["name"]
        
        mock_reference_component = MockComponent(reference_component)
    
    try:
        # Use the existing widget validation logic
        Widget.validate_widget_type(widget_type, mock_reference_component, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Widget validation failed: {str(e)}")


@router.get("/{template_id}/structure", status_code=status.HTTP_200_OK)
async def get_template_structure(
    template_id: str,
    user_device: tuple = Depends(verify_device)
):
    """Get detailed structure of a custom template including components and widgets."""
    current_user = user_device[0]
    
    try:
        template = CustomTemplate_db.objects(id=template_id, owner=current_user.id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        components = template.data.get("components", [])
        widgets = template.data.get("widgets", [])
        
        # Add validation status for each component and widget
        validated_components = []
        for comp in components:
            try:
                validate_component_data(comp["type"], comp["data"])
                validated_components.append({**comp, "valid": True, "error": None})
            except Exception as e:
                validated_components.append({**comp, "valid": False, "error": str(e)})
        
        validated_widgets = []
        for widget in widgets:
            try:
                reference_component = None
                if widget.get("reference_component"):
                    reference_component = next(
                        (comp for comp in components if comp["name"] == widget["reference_component"]), 
                        None
                    )
                validate_widget_data_for_template(widget["type"], widget["data"], reference_component)
                validated_widgets.append({**widget, "valid": True, "error": None})
            except Exception as e:
                validated_widgets.append({**widget, "valid": False, "error": str(e)})
        
        return {
            "id": str(template.id),
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "components": validated_components,
            "widgets": validated_widgets,
            "component_count": len(components),
            "widget_count": len(widgets)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")