from fastapi import APIRouter, Depends, status, HTTPException
from models import User, Subject_db, Subject, Connection_db , Connection, CustomTemplate_db, Component_db, Category_db, DataTransfer, DataTransfer_db, Widget , Widget_db , Todo_db , Todo, Notification, Notification_db, NotificationCount , TEMPLATES
from middleWares import verify_device
from models import AIMessage_db
from datetime import datetime, timezone
from models import Arrays
from datetime import timedelta

router = APIRouter(prefix="/chat", tags=["AI Messaging"])

async def execute_function_call(function_name: str, arguments: dict, user: User):
    """
    Execute function calls requested by the AI
    """
    try:
        if function_name == "create_subject":
            subject = Subject(
                name=arguments.get("name", ""),
                owner=user.id,
                template=arguments.get("template", ""),
                category=arguments.get("category", "Uncategorized")
            )
            subject.save_to_db()
            return {"success": True, "subject_id": str(subject.id), "message": f"Created subject: {subject.name}"}
        
        elif function_name == "add_component_to_subject":
            subject_id = arguments.get("subject_id")
            
            # Verify subject exists and belongs to user
            subject_db = Subject_db.objects(id=subject_id, owner=user.id).first()
            if not subject_db:
                return {"success": False, "message": "Subject not found or access denied"}
            
            # Load the subject using helper class
            subject = Subject.from_db(subject_db)
            if not subject:
                return {"success": False, "message": "Error loading subject"}
            
            # Add component using the helper method
            component = await subject.add_component(
                component_name=arguments.get("name", ""),
                component_type=arguments.get("type", "str"),
                data=arguments.get("data", None),
            )
            
            if component:
                return {"success": True, "component_id": str(component.id), "message": f"Added component to subject: {component.name}"}
            else:
                return {"success": False, "message": "Failed to create component"}
        
        elif function_name == "create_connection":
            # Create a new connection - fix field names
            from_subject_id = arguments.get("from_subject_id")
            to_subject_id = arguments.get("to_subject_id")
            
            # Verify both subjects exist and belong to user
            from_subject = Subject_db.objects(id=from_subject_id, owner=user.id).first()
            to_subject = Subject_db.objects(id=to_subject_id, owner=user.id).first()
            
            if not from_subject or not to_subject:
                return {"success": False, "message": "One or both subjects not found or access denied"}
            
            # Create connection using helper class with correct parameters
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")

            if not start_date:
                start_date_dt = datetime.utcnow()
            else:
                start_date_dt = datetime.fromisoformat(start_date)
            if not end_date:
                end_date_dt = start_date_dt + timedelta(hours=1)
            else:
                end_date_dt = datetime.fromisoformat(end_date)

            connection = Connection(
                source_subject=from_subject,
                target_subject=to_subject,
                con_type=arguments.get("type", "manual"),
                owner=user.id,
                start_date=start_date_dt.isoformat(),
                end_date=end_date_dt.isoformat(),
                done=arguments.get("done", False)
            )
            
            # Add data transfers if provided
            data_transfers = arguments.get("data_transfers", [])
            if data_transfers:
                for transfer in data_transfers:
                    source_component_id = transfer.get("source_component_id")
                    target_component_id = transfer.get("target_component_id")
                    
                    if not target_component_id:
                        return {"success": False, "message": "Target component is required for data transfer"}
                    
                    # Verify target component exists and belongs to user
                    target_component = Component_db.objects(id=target_component_id, owner=user.id).first()
                    if not target_component:
                        return {"success": False, "message": f"Target component {target_component_id} not found or access denied"}
                    
                    # Verify source component if provided
                    source_component = None
                    if source_component_id:
                        source_component = Component_db.objects(id=source_component_id, owner=user.id).first()
                        if not source_component:
                            return {"success": False, "message": f"Source component {source_component_id} not found or access denied"}
                    
                    # Add data transfer to connection using the helper method
                    await connection.add_data_transfer(
                        source_component=source_component,
                        target_component=target_component,
                        data_value=transfer.get("data_value"),
                        operation=transfer.get("operation", "replace"),
                        details=transfer.get("details")
                    )
            
            # Save connection to database
            connection.save_to_db()
            return {
                "success": True, 
                "connection_id": str(connection.id), 
                "message": f"Created connection between subjects with {len(data_transfers)} data transfers"
            }
        
        elif function_name == "create_category":
            # Create a new category - correct field names
            category_data = {
                "name": arguments.get("name", ""),
                "description": arguments.get("description", ""),
                "owner": user.id
            }
            category_db = Category_db(**category_data)
            category_db.save()
            return {"success": True, "category_id": str(category_db.id), "message": f"Created category: {category_data['name']}"}
        
        elif function_name == "create_data_transfer":
            # Create a new data transfer
            source_component_id = arguments.get("source_component_id")
            target_component_id = arguments.get("target_component_id")
            operation = arguments.get("operation", "replace")
            data_value = arguments.get("data_value")
            schedule_time = arguments.get("schedule_time")
            
            # Verify target component exists and belongs to user
            target_component = Component_db.objects(id=target_component_id, owner=user.id).first()
            if not target_component:
                return {"success": False, "message": "Target component not found or access denied"}
            
            # Verify source component if provided
            if source_component_id:
                source_component = Component_db.objects(id=source_component_id, owner=user.id).first()
                if not source_component:
                    return {"success": False, "message": "Source component not found or access denied"}
            
            # Create data transfer
            data_transfer = DataTransfer(
                source_component=source_component_id,
                target_component=target_component_id,
                data_value=data_value,
                operation=operation,
                owner=user.id,
            )
            
            # Execute immediately if no schedule_time provided or if schedule_time is in the past/now
            if not schedule_time or (data_transfer.schedule_time and datetime.now(timezone.utc) >= data_transfer.schedule_time):
                if data_transfer.execute():
                    return {
                        "success": True, 
                        "data_transfer_id": data_transfer.id, 
                        "message": f"Data transfer executed immediately: {operation} operation on {target_component.name}"
                    }
                else:
                    return {"success": False, "message": "Failed to execute data transfer"}
            else:
                # Save for future execution
                data_transfer.save_to_db()
                return {
                    "success": True, 
                    "data_transfer_id": data_transfer.id, 
                    "message": f"Data transfer scheduled for {data_transfer.schedule_time.isoformat()}: {operation} operation on {target_component.name}"
                }
        
        elif function_name == "create_widget":
            # Create a new widget
            widget_name = arguments.get("name", "")
            widget_type = arguments.get("type", "")
            host_subject_id = arguments.get("host_subject_id", "")
            reference_component_id = arguments.get("reference_component_id")
            widget_data = arguments.get("data", {})
            
            if not widget_name or not widget_type or not host_subject_id:
                return {"success": False, "message": "Name, type, and host_subject_id are required"}
            
            # Verify host subject exists and belongs to user
            host_subject = Subject_db.objects(id=host_subject_id, owner=user.id).first()
            if not host_subject:
                return {"success": False, "message": "Host subject not found or access denied"}
            
            # Verify reference component if provided
            reference_component = None
            if reference_component_id:
                reference_component = Component_db.objects(id=reference_component_id, owner=user.id).first()
                if not reference_component:
                    return {"success": False, "message": "Reference component not found or access denied"}
            
            # Create widget
            widget = Widget(
                name=widget_name,
                widget_type=widget_type,
                host_subject=host_subject_id,
                reference_component=reference_component_id,
                data=widget_data,
                owner=user.id
            )
            widget.save_to_db()
            return {"success": True, "widget_id": str(widget.id), "message": f"Created widget: {widget_name}"}
        
        elif function_name == "create_custom_template":
            # Create a custom template
            template_name = arguments.get("name", "")
            template_data = arguments.get("data", {})
            description = arguments.get("description", "")
            category = arguments.get("category", "Uncategorized")
            
            if not template_name or not template_data:
                return {"success": False, "message": "Name and data are required"}
            
            template = CustomTemplate_db(
                owner=user.id,
                name=template_name,
                description=description,
                data=template_data,
                category=category
            )
            template.save()
            return {"success": True, "template_id": str(template.id), "message": f"Created template: {template_name}"}
        
        elif function_name == "add_todo_to_widget":
            # Add a todo item to a daily_todo widget
            widget_id = arguments.get("widget_id", "")
            todo_text = arguments.get("text", "")
            todo_date = arguments.get("date")
            completed = arguments.get("completed", False)
            
            if not widget_id or not todo_text:
                return {"success": False, "message": "Widget ID and todo text are required"}
            
            # Verify widget exists and belongs to user
            widget = Widget_db.objects(id=widget_id, owner=user.id).first()
            if not widget:
                return {"success": False, "message": "Widget not found or access denied"}
            
            if widget.widget_type != "daily_todo":
                return {"success": False, "message": "This function only works with daily_todo widgets"}
            
            # Use current date if not provided
            if not todo_date:
                todo_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Create todo
            todo = Todo(
                text=todo_text,
                completed=completed,
                date=datetime.strptime(todo_date, "%Y-%m-%d"),
                widget_id=widget_id,
                owner=user.id
            )
            todo.save_to_db()
            return {"success": True, "todo_id": str(todo.id), "message": f"Added todo: {todo_text}"}
        
        elif function_name == "update_component_data":
            # Update component data
            component_id = arguments.get("component_id", "")
            new_data = arguments.get("data")
            new_name = arguments.get("name")
            
            if not component_id:
                return {"success": False, "message": "Component ID is required"}
            
            # Verify component exists and belongs to user
            component = Component_db.objects(id=component_id, owner=user.id).first()
            if not component:
                return {"success": False, "message": "Component not found or access denied"}
            
            # Update fields
            updated = False
            if new_data is not None:
                component.data = new_data
                updated = True
            if new_name:
                component.name = new_name
                updated = True
            
            if not updated:
                return {"success": False, "message": "No data provided to update"}
            
            component.save()
            return {"success": True, "component_id": str(component.id), "message": f"Updated component: {component.name}"}
        
        elif function_name == "get_subject_full_data":
            # Get full data for a subject (components and widgets)
            subject_id = arguments.get("subject_id", "")
            
            if not subject_id:
                return {"success": False, "message": "Subject ID is required"}
            
            # Verify subject exists and belongs to user  
            subject_db = Subject_db.objects(id=subject_id, owner=user.id).first()
            if not subject_db:
                return {"success": False, "message": "Subject not found or access denied"}
            
            # Load subject and get full data
            subject = Subject.from_db(subject_db)
            if not subject:
                return {"success": False, "message": "Error loading subject"}
            
            full_data = await subject.get_full_data()
            return {"success": True, "subject_data": full_data, "message": f"Retrieved full data for subject: {subject.name}"}
        
        elif function_name == "remove_ai_accessible_subject":
            # Remove a subject from AI accessible list
            subject_id = arguments.get("subject_id", "")
            
            if not subject_id:
                return {"success": False, "message": "Subject ID is required"}
            
            ai_list = user.settings.get("ai_accessible", [])
            if subject_id not in ai_list:
                return {"success": False, "message": "Subject not in AI-accessible list"}
            
            ai_list.remove(subject_id)
            user.settings["ai_accessible"] = ai_list
            user.save()
            return {"success": True, "message": f"Removed subject from AI-accessible list"}
        
        elif function_name == "delete_subject":
            # Delete a subject and its components/widgets
            subject_id = arguments.get("subject_id", "")
            
            if not subject_id:
                return {"success": False, "message": "Subject ID is required"}
            
            # Verify subject exists and belongs to user
            subject_db = Subject_db.objects(id=subject_id, owner=user.id).first()
            if not subject_db:
                return {"success": False, "message": "Subject not found or access denied"}
            
            # Check if subject is deletable
            if not subject_db.is_deletable:
                return {"success": False, "message": "This subject cannot be deleted"}
            
            # Delete associated widgets and components
            for widget in subject_db.widgets:
                widget.delete()
            for comp in subject_db.components:
                comp.delete()
            
            subject_name = subject_db.name
            subject_db.delete()
            return {"success": True, "message": f"Subject '{subject_name}' and all associated components and widgets deleted successfully"}
        
        elif function_name == "delete_component":
            # Delete a component and remove it from its host subject
            component_id = arguments.get("component_id", "")
            
            if not component_id:
                return {"success": False, "message": "Component ID is required"}
            
            # Verify component exists and belongs to user
            component = Component_db.objects(id=component_id, owner=user.id).first()
            if not component:
                return {"success": False, "message": "Component not found or access denied"}
            
            # Check if component is deletable
            if not component.is_deletable:
                return {"success": False, "message": "This component cannot be deleted"}
            
            # Handle deletion of array metadata for array types
            if component.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]:
                array_result = Arrays.delete_array(
                    user_id=user.id,
                    component_id=component_id
                )
                if not array_result["success"]:
                    return {"success": False, "message": f"Failed to delete array data: {array_result['message']}"}
            
            # Remove component from its host subject
            host_subject = Subject_db.objects(id=component.host_subject.id).first()
            if host_subject:
                host_subject.components.remove(component_id)
                host_subject.save()
            
            component_name = component.name
            component.delete()
            return {"success": True, "message": f"Component '{component_name}' deleted successfully"}
        
        elif function_name == "delete_widget":
            # Delete a widget and associated todos if applicable
            widget_id = arguments.get("widget_id", "")
            
            if not widget_id:
                return {"success": False, "message": "Widget ID is required"}
            
            # Verify widget exists and belongs to user
            widget = Widget_db.objects(id=widget_id, owner=user.id).first()
            if not widget:
                return {"success": False, "message": "Widget not found or access denied"}
            
            # Check if widget is deletable
            if widget.is_deletable == "false":
                return {"success": False, "message": "This widget cannot be deleted"}
            
            # If it's a daily_todo widget, delete associated todos
            if widget.widget_type == "daily_todo":
                Todo_db.objects(widget_id=widget_id).delete()
            
            widget_name = widget.name
            widget.delete()
            return {"success": True, "message": f"Widget '{widget_name}' deleted successfully"}
        
        elif function_name == "delete_connection":
            # Delete a connection
            connection_id = arguments.get("connection_id", "")
            
            if not connection_id:
                return {"success": False, "message": "Connection ID is required"}
            
            # Verify connection exists and belongs to user
            connection = Connection_db.objects(id=connection_id, owner=user.id).first()
            if not connection:
                return {"success": False, "message": "Connection not found or access denied"}
            
            connection.delete()
            return {"success": True, "message": "Connection deleted successfully"}
        
        elif function_name == "delete_category":
            # Delete a category and set associated subjects to 'Uncategorized'
            category_name = arguments.get("name", "")
            
            if not category_name:
                return {"success": False, "message": "Category name is required"}
            
            # Verify category exists and belongs to user
            category = Category_db.objects(name=category_name, owner=user.id).first()
            if not category:
                return {"success": False, "message": "Category not found or access denied"}
            
            # Update all subjects in this category to "Uncategorized"
            subjects_in_category = Subject_db.objects(category=category_name, owner=user.id)
            for subject in subjects_in_category:
                subject.update(category="Uncategorized")
            
            category.delete()
            return {"success": True, "message": f"Category '{category_name}' deleted and all associated subjects set to 'Uncategorized'"}
        
        elif function_name == "delete_data_transfer":
            # Delete a data transfer
            transfer_id = arguments.get("transfer_id", "")
            
            if not transfer_id:
                return {"success": False, "message": "Transfer ID is required"}
            
            # Verify data transfer exists and user has access
            data_transfer = DataTransfer_db.objects(id=transfer_id).first()
            if not data_transfer:
                return {"success": False, "message": "Data transfer not found"}
            
            # Check if user owns the source or target component
            user_has_access = False
            if data_transfer.source_component and data_transfer.source_component.owner == user.id:
                user_has_access = True
            if data_transfer.target_component and data_transfer.target_component.owner == user.id:
                user_has_access = True
            
            if not user_has_access and not user.admin:
                return {"success": False, "message": "Not authorized to delete this data transfer"}
            
            data_transfer.delete()
            return {"success": True, "message": "Data transfer deleted successfully"}
        
        elif function_name == "delete_custom_template":
            # Delete a custom template
            template_id = arguments.get("template_id", "")
            
            if not template_id:
                return {"success": False, "message": "Template ID is required"}
            
            # Verify template exists and belongs to user
            template = CustomTemplate_db.objects(id=template_id, owner=user.id).first()
            if not template:
                return {"success": False, "message": "Template not found or access denied"}
            
            template_name = template.name
            template.delete()
            return {"success": True, "message": f"Template '{template_name}' deleted successfully"}
        
        elif function_name == "delete_todo":
            # Delete a todo item
            todo_id = arguments.get("todo_id", "")
            widget_id = arguments.get("widget_id", "")
            
            if not todo_id:
                return {"success": False, "message": "Todo ID is required"}
            
            # Verify todo exists and belongs to user
            todo = Todo_db.objects(id=todo_id, owner=user.id).first()
            if not todo:
                return {"success": False, "message": "Todo not found or access denied"}
            
            # If widget_id provided, verify it matches
            if widget_id and todo.widget_id != widget_id:
                return {"success": False, "message": "Todo does not belong to specified widget"}
            
            todo_text = todo.text
            todo.delete()
            return {"success": True, "message": f"Todo '{todo_text}' deleted successfully"}
        
        elif function_name == "delete_notification":
            # Delete a notification
            notification_id = arguments.get("notification_id", "")
            
            if not notification_id:
                return {"success": False, "message": "Notification ID is required"}
            
            # Verify notification exists and belongs to user
            notification = Notification_db.objects(id=notification_id, user_id=str(user.id)).first()
            if not notification:
                return {"success": False, "message": "Notification not found or access denied"}
            
            # Update notification count
            count_obj, _ = NotificationCount.objects.get_or_create(user_id=user.id)
            count_obj.count = str(int(count_obj.count) + 1)
            count_obj.save()
            
            notification.delete()
            return {"success": True, "message": "Notification deleted successfully"}
        
        else:
            return {"success": False, "message": f"Unknown function: {function_name}"}
    
    except Exception as e:
        return {"success": False, "message": f"Error executing {function_name}: {str(e)}"}

@router.post("/", status_code=status.HTTP_200_OK)
async def message_ai(
    request: dict,
    user_device: tuple = Depends(verify_device)
):
    """
    Send a message to the AI, providing AI-accessible subjects (full data), not-done connections, templates, and user id.
    Supports function calling for AI to perform actions.
    """
    user = user_device[0]
    message = request.get("message", "")
    
    # fetching will be moved to the AI server code in the future to avoid performance issues
    # Bulk fetch all user data in parallel using list comprehension and single queries
    ai_subject_ids = user.settings.get("ai_accessible", [])
    
    # Single query for all subjects
    all_subjects = list(Subject_db.objects(owner=user.id))
    all_subjects_dict = {str(subj.id): subj for subj in all_subjects}
    
    # Get AI-accessible subjects (full data) - only for specified IDs
    ai_subjects_full_data = []
    for subj_id in ai_subject_ids:
        if subj_id in all_subjects_dict:
            subj = Subject.from_db(all_subjects_dict[subj_id])
            if subj:
                full_data = await subj.get_full_data()
                ai_subjects_full_data.append(full_data)
    
    # Bulk fetch all other data with single queries
    connections = list(Connection_db.objects(owner=user.id, done=False))
    templates = list(CustomTemplate_db.objects(owner=user.id))
    categories = list(Category_db.objects(owner=user.id))
    
    # Process data in memory (faster than multiple DB queries)
    connections_data = [conn.to_json() for conn in connections]
    templates_data = [tpl.to_mongo().to_dict() for tpl in templates]
    
    
    # Format default templates for AI
    default_templates_data = []
    for template_key, template_info in TEMPLATES.items():
        default_templates_data.append({
            "id": template_key,
            "name": template_key.replace("_", " ").title(),
            "category": template_info.get("category", "General"),
            "type": "default",
            "data": template_info
        })
    
    
    # Format custom templates for AI
    custom_templates_data = []
    for tpl in templates_data:
        custom_templates_data.append({
            "id": str(tpl["_id"]),
            "name": tpl["name"],
            "category": tpl.get("category", "Uncategorized"),
            "type": "custom",
            "description": tpl.get("description", ""),
            "data": tpl["data"]
        })
    
    # Combine all templates
    all_templates_data = default_templates_data + custom_templates_data
    
    subjects_info = [
        {
            "id": str(subj.id),
            "name": subj.name,
        }
        for subj in all_subjects
    ]
    categories_data = [
        {
            "id": str(cat.id),
            "name": cat.name,
            "description": cat.description,
            "color": cat.color
        }
        for cat in categories
    ]

    # Handle function calls if present in request
    function_results = []
    if "function_calls" in request:
        for func_call in request["function_calls"]:
            function_name = func_call.get("name")
            arguments = func_call.get("arguments", {})
            result = await execute_function_call(function_name, arguments, user)
            function_results.append({
                "function": function_name,
                "result": result
            })

    response_data = {
        "message": message,
        "user_id": str(user.id),
        "ai_accessible_subjects": ai_subjects_full_data,
        "not_done_connections": connections_data,
        "custom_templates": templates_data, 
        "all_templates": all_templates_data,
        "all_subjects_info": subjects_info,
        "categories": categories_data,
        # this list will be removed in the future I will put it in the AI server code 
        "available_functions": [
            {
                "name": "create_subject",
                "description": "Create a new subject",
                "parameters": {
                    "name": "Subject name (required)",
                    "category": "Subject category (optional, defaults to 'Uncategorized')",
                    "template": "Template name to apply (optional, defaults to None)"
                }
            },
            {
                "name": "add_component_to_subject",
                "description": "Add a component to an existing subject",
                "parameters": {
                    "subject_id": "ID of the subject to add component to (required)",
                    "name": "Component name (required)",
                    "type": "Component type: int, str, bool, date, Array_type, Array_generic, pair, Array_of_pairs, Array_of_strings, Array_of_booleans, Array_of_dates, Array_of_objects (required)",
                    "data": "Component data structure (optional). Data formats by type: int: {'item': 0}, str: {'item': ''}, bool: {'item': false}, date: {'item': 'ISO_date_string'}, pair: {'item': {'key': 'string', 'value': any}, 'type': {'key': 'str', 'value': 'any'}}, Array_type: {'type': 'int'}, Array_generic: {'type': 'any'}, Array_of_pairs: {'type': {'key': 'str', 'value': 'any'}}, Array_of_strings: {'type': 'str'}, Array_of_booleans: {'type': 'bool'}, Array_of_dates: {'type': 'date'}, Array_of_objects: {'type': 'object'}. Array types store items separately in ArrayMetadata.",
                }
            },
            {
                "name": "create_connection",
                "description": "create a connection between two subjects with optional data transfers",
                "parameters": {
                    "from_subject_id": "source subject id (required)",
                    "to_subject_id": "target subject id (required)",
                    "type": "connection type (optional, defaults to 'manual')",
                    "start_date": "connection start date (iso datetime string, optional)",
                    "end_date": "connection end date (iso datetime string, optional)",
                    "done": "whether connection is completed (boolean, optional)",
                    "data_transfers": "array of data transfer objects (optional). each object should contain: target_component_id (required), operation (optional, defaults to 'replace'), source_component_id (optional), data_value (optional), details (optional)"
                }
            },
            {
                "name": "create_category",
                "description": "create a new category",
                "parameters": {
                    "name": "category name (required)",
                    "description": "category description (optional)",
                }
            },
            {
                "name": "create_data_transfer",
                "description": "Create a data transfer operation between components",
                "parameters": {
                    "target_component_id": "ID of the target component (required)",
                    "operation": "Operation type. Valid operations by component type: pair=['update_key', 'update_value'], Array_of_pairs=['append', 'remove_back', 'remove_front', 'delete_at', 'push_at', 'update_pair'], Array types=['append', 'remove_back', 'remove_front', 'delete_at', 'push_at', 'update_at'], scalar types (int/str/bool/date)=['replace', 'add', 'multiply', 'toggle']",
                    "source_component_id": "ID of the source component (optional)",
                    "data_value": "Data value for the operation (optional, used when no source component). Format depends on operation: replace={'item': value}, update_key={'item': {'key': new_key}}, update_value={'item': {'value': new_value}}, append={'item': value_to_append}, update_pair={'item': {'key': key, 'value': value}}, update_at={'item': value, 'index': position}, push_at={'item': value, 'index': position}, delete_at={'index': position}",
                    "schedule_time": "When to execute the transfer (ISO datetime string, optional)"
                }
            },
            {
                "name": "create_widget",
                "description": "create a new widget in a subject",
                "parameters": {
                    "name": "widget name (required)",
                    "type": "widget type: daily_todo, table, note, calendar, text_field, component_reference (required)",
                    "host_subject_id": "ID of the subject to host the widget (required)",
                    "reference_component_id": "ID of component to reference (optional, for component_reference widgets)",
                    "data": "Widget-specific data structure (optional)"
                }
            },
            {
                "name": "create_custom_template",
                "description": "Create a reusable template",
                "parameters": {
                    "name": "Template name (required)",
                    "data": "Template structure with components and widgets (required)",
                    "description": "Template description (optional)",
                    "category": "Template category (optional, defaults to 'Uncategorized')"
                }
            },
            {
                "name": "add_todo_to_widget",
                "description": "Add a todo item to a daily_todo widget",
                "parameters": {
                    "widget_id": "ID of the daily_todo widget (required)",
                    "text": "Todo text (required)",
                    "date": "Todo date in YYYY-MM-DD format (optional, defaults to today)",
                    "completed": "Whether todo is completed (boolean, optional)"
                }
            },
            {
                "name": "update_component_data",
                "description": "Update component data or name",
                "parameters": {
                    "component_id": "ID of the component to update (required)",
                    "data": "New component data (optional). Must match component type structure: scalar types need {'item': value}, pair needs {'item': {'key': string, 'value': any}}, array types need {'type': element_type} and items are managed separately",
                    "name": "New component name (optional)"
                }
            },
            {
                "name": "get_subject_full_data",
                "description": "Get complete data for a subject including all components and widgets",
                "parameters": {
                    "subject_id": "ID of the subject (required)"
                }
            },
            {
                "name": "remove_ai_accessible_subject",
                "description": "Remove a subject from the AI-accessible list",
                "parameters": {
                    "subject_id": "ID of the subject to remove from AI-accessible list (required)"
                }
            },
            {
                "name": "delete_subject",
                "description": "Delete a subject and all its components and widgets",
                "parameters": {
                    "subject_id": "ID of the subject to delete (required)"
                }
            },
            {
                "name": "delete_component",
                "description": "Delete a component and remove it from its host subject",
                "parameters": {
                    "component_id": "ID of the component to delete (required)"
                }
            },
            {
                "name": "delete_widget",
                "description": "Delete a widget and associated data",
                "parameters": {
                    "widget_id": "ID of the widget to delete (required)"
                }
            },
            {
                "name": "delete_connection",
                "description": "Delete a connection between subjects",
                "parameters": {
                    "connection_id": "ID of the connection to delete (required)"
                }
            },
            {
                "name": "delete_category",
                "description": "Delete a category and set associated subjects to 'Uncategorized'",
                "parameters": {
                    "name": "Name of the category to delete (required)"
                }
            },
            {
                "name": "delete_data_transfer",
                "description": "Delete a data transfer operation",
                "parameters": {
                    "transfer_id": "ID of the data transfer to delete (required)"
                }
            },
            {
                "name": "delete_custom_template",
                "description": "Delete a custom template",
                "parameters": {
                    "template_id": "ID of the template to delete (required)"
                }
            },
            {
                "name": "delete_todo",
                "description": "Delete a todo item",
                "parameters": {
                    "todo_id": "ID of the todo to delete (required)",
                    "widget_id": "ID of the widget (optional, for verification)"
                }
            },
            {
                "name": "delete_notification",
                "description": "Delete a notification",
                "parameters": {
                    "notification_id": "ID of the notification to delete (required)"
                }
            }
        ]
    }

    if function_results:
        response_data["function_results"] = function_results

    return response_data

@router.get("/messages", status_code=status.HTTP_200_OK)
async def get_user_messages(user_device: tuple = Depends(verify_device)):
    """
    Get all AI messages for the current user.
    """
    user = user_device[0]
    messages = list(AIMessage_db.objects(user_id=str(user.id)).order_by("-created_at"))
    messages_data = [
        {
            "user_message": msg.user_message,
            "ai_response": msg.ai_response,
            "created_at": msg.created_at
        }
        for msg in messages
    ]
    return {"messages": messages_data}