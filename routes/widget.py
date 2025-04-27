# routers/widget.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from datetime import datetime, timedelta
from models import Widget_db, Widget, Component_db, User, Subject_db, Todo_db, Todo
from mongoengine.errors import DoesNotExist, ValidationError
from middleWares import verify_device
import uuid
from typing import Optional
from cloudinary.uploader import upload
from cloudinary.exceptions import Error as CloudinaryError
from cloud import dummy

router = APIRouter(prefix="/widgets", tags=["Widget"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_widget(data: dict, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    current_device = user_device[1]
    try:
        data_id = data.get('id', str(uuid.uuid4()))
        widget_type = data.get('type')
        host_subject_id = data.get('host_subject')
        reference_component_id = data.get('reference_component')
        data_value = data.get('data', {})

        if not widget_type or not host_subject_id:
            raise HTTPException(
                status_code=400, detail="Type and Host Subject are required"
            )

        host_subject = Subject_db.objects(id=host_subject_id).first()
        if not host_subject:
            raise HTTPException(
                status_code=404, detail="Host Subject not found")

        if current_user.id != host_subject.owner and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to create widget for this subject")

        reference_component = None
        if reference_component_id:
            reference_component = Component_db.objects(
                id=reference_component_id).first()
            if not reference_component:
                raise HTTPException(
                    status_code=404, detail="Reference Component not found")

            # Component specific type validation
            if widget_type == "component_reference":
                # You can add specific validations based on the component type
                component_type = reference_component.type
                # Example: Allow only certain component types
                allowed_types = ["data_source", "api_endpoint", "database"]
                if component_type not in allowed_types:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Component type '{
                            component_type}' not supported for this widget"
                    )

        # Validate widget type and data structure
        try:
            validated_data = Widget.validate_widget_type(
                widget_type,
                reference_component_id,
                data_value
            )
            data_value = validated_data  # Update with validated data
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))

        widget = Widget(
            id=data_id,
            type=widget_type,
            host_subject=host_subject_id,
            reference_component=reference_component_id,
            data=data_value,
            owner=current_user.id
        )
        widget.save_to_db()

        return {"message": "Widget created successfully", "id": str(widget.id)}
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/{widget_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_widget(widget_id: str, user_device: tuple  = Depends(verify_device)):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")
        return widget.to_mongo().to_dict()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_all_widgets(
    user_device: tuple =Depends(verify_device),
    host_subject: str = None,
    widget_type: str = None
):
    current_user = user_device[0]
    query = {"owner": current_user.id}

    if host_subject:
        query["host_subject"] = host_subject

    if widget_type:
        query["type"] = widget_type

    widgets = Widget_db.objects(**query)
    return [widget.to_mongo().to_dict() for widget in widgets]


@router.delete("/{widget_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def delete_widget(widget_id: str, user_device: tuple =Depends(verify_device)):
    current_user = current_user[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this widget")

        # If it's a daily_todo widget, also delete associated todos
        if widget.type == "daily_todo":
            Todo_db.objects(widget_id=widget_id).delete()

        widget.delete()
        return {"message": "Widget deleted successfully", "id": widget_id}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

# DAILY TODO WIDGET SPECIFIC ENDPOINTS


@router.put("/{widget_id}/daily-todo/date", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def update_daily_todo_date(
    widget_id: str,
    date_data: dict,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        new_date = date_data.get("selected_date")
        if not new_date:
            raise HTTPException(
                status_code=400, detail="selected_date is required")

        # Validate date format
        try:
            selected_date = datetime.strptime(new_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Update the widget's selected date
        widget_data = widget.data or {}
        widget_data["selected_date"] = new_date
        widget.data = widget_data
        widget.save()

        # Get todos for the selected date
        todos = Todo_db.objects(widget_id=widget_id,
                                date=selected_date).order_by('created_at')

        return {
            "message": "Date updated successfully",
            "widget": widget.to_mongo().to_dict(),
            "todos": [todo.to_dict() for todo in todos]
        }
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/{widget_id}/daily-todo/todos", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_todos(
    widget_id: str,
    date: Optional[str] = None,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        widget_data = widget.data or {}

        # If no date provided, use the widget's selected date
        if not date:
            date = widget_data.get("selected_date")
            if not date:
                date = datetime.utcnow().strftime("%Y-%m-%d")

        # Parse the date
        try:
            selected_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Get todos for the specified date
        todos = Todo_db.objects(widget_id=widget_id,
                                date=selected_date).order_by('created_at')

        return {
            "date": date,
            "todos": [todo.to_dict() for todo in todos]
        }
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.post("/{widget_id}/daily-todo/todos", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def add_todo_item(
    widget_id: str,
    todo_data: dict,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        todo_text = todo_data.get("text")
        if not todo_text:
            raise HTTPException(
                status_code=400, detail="Todo text is required")

        # Get the date for this todo (use widget's selected date)
        widget_data = widget.data or {}
        date_str = todo_data.get("date") or widget_data.get("selected_date")
        if not date_str:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            todo_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Create the todo in the separate collection
        todo = Todo(
            text=todo_text,
            completed=todo_data.get("completed", False),
            date=todo_date,
            widget_id=widget_id,
            owner=current_user.id
        )
        todo_db = todo.save_to_db()

        return {"message": "Todo added successfully", "todo": todo_db.to_dict()}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.put("/{widget_id}/daily-todo/todos/{todo_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def update_todo_item(
    widget_id: str,
    todo_id: str,
    todo_data: dict,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        # Get the todo from the database
        todo = Todo_db.objects.get(id=todo_id, widget_id=widget_id)

        # Update todo fields
        if "text" in todo_data:
            todo.text = todo_data["text"]

        if "completed" in todo_data:
            todo.completed = bool(todo_data["completed"])

        # If moving to a different date
        if "date" in todo_data:
            try:
                todo.date = datetime.strptime(todo_data["date"], "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        todo.save()

        return {"message": "Todo updated successfully", "todo": todo.to_dict()}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or todo not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.delete("/{widget_id}/daily-todo/todos/{todo_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def delete_todo_item(
    widget_id: str,
    todo_id: str,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        # Delete the todo
        result = Todo_db.objects(id=todo_id, widget_id=widget_id).delete()
        if result == 0:
            raise HTTPException(status_code=404, detail="Todo item not found")

        return {"message": "Todo deleted successfully"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

# Additional endpoint to get todos for a date range


@router.get("/{widget_id}/daily-todo/todos/range", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_todos_in_range(
    widget_id: str,
    start_date: str,
    end_date: str,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        # Parse dates
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            end = end + timedelta(days=1) - \
                timedelta(seconds=1)  # End of the day
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Get todos for the date range
        todos = Todo_db.objects(
            widget_id=widget_id, date__gte=start, date__lte=end).order_by('date', 'created_at')

        # Group todos by date
        result = {}
        for todo in todos:
            date_key = todo.date.strftime("%Y-%m-%d")
            if date_key not in result:
                result[date_key] = []
            result[date_key].append(todo.to_dict())

        return {
            "start_date": start_date,
            "end_date": end_date,
            "todos_by_date": result
        }
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
# TABLE WIDGET SPECIFIC ENDPOINTS


@router.put("/{widget_id}/table/columns", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def update_table_columns(
    widget_id: str,
    columns_data: dict,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "table":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for table widgets")

        columns = columns_data.get("columns")
        if not columns or not isinstance(columns, list):
            raise HTTPException(
                status_code=400, detail="Valid columns array is required")

        widget_data = widget.data or {}
        widget_data["columns"] = columns

        # Initialize rows if not present
        if "rows" not in widget_data:
            widget_data["rows"] = []

        widget.data = widget_data
        widget.save()

        return {"message": "Table columns updated successfully", "widget": widget.to_mongo().to_dict()}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.post("/{widget_id}/table/rows", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def add_table_row(
    widget_id: str,
    row_data: dict,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "table":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for table widgets")

        row = row_data.get("row")
        if not row or not isinstance(row, dict):
            raise HTTPException(
                status_code=400, detail="Valid row object is required")

        widget_data = widget.data or {}

        # Ensure columns exist
        if "columns" not in widget_data or not widget_data["columns"]:
            raise HTTPException(
                status_code=400, detail="Table must have columns defined before adding rows")

        # Initialize rows if not present
        if "rows" not in widget_data:
            widget_data["rows"] = []

        # Add row ID if not provided
        if "id" not in row:
            row["id"] = str(uuid.uuid4())

        widget_data["rows"].append(row)
        widget.data = widget_data
        widget.save()

        return {"message": "Table row added successfully", "row": row}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.put("/{widget_id}/table/rows/{row_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def update_table_row(
    widget_id: str,
    row_id: str,
    row_data: dict,
    user_device: tuple =Depends(verify_device)
):
    try:
        widget = Widget_db.objects.get(id=widget_id)

        current_user = user_device[0]
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "table":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for table widgets")

        row_updates = row_data.get("row")
        if not row_updates or not isinstance(row_updates, dict):
            raise HTTPException(
                status_code=400, detail="Valid row updates are required")

        widget_data = widget.data or {}
        rows = widget_data.get("rows", [])

        # Find the row by ID
        row_index = next((i for i, row in enumerate(
            rows) if row.get("id") == row_id), None)
        if row_index is None:
            raise HTTPException(status_code=404, detail="Row not found")

        # Preserve the row ID
        row_updates["id"] = row_id

        # Update the row
        rows[row_index] = row_updates
        widget.data = widget_data
        widget.save()

        return {"message": "Table row updated successfully", "row": rows[row_index]}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.delete("/{widget_id}/table/rows/{row_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def delete_table_row(
    widget_id: str,
    row_id: str,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "table":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for table widgets")

        widget_data = widget.data or {}
        rows = widget_data.get("rows", [])

        # Find and remove the row by ID
        original_length = len(rows)
        widget_data["rows"] = [row for row in rows if row.get("id") != row_id]

        if len(widget_data["rows"]) == original_length:
            raise HTTPException(status_code=404, detail="Row not found")

        widget.data = widget_data
        widget.save()

        return {"message": "Table row deleted successfully"}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

# COMPONENT REFERENCE WIDGET ENDPOINTS


@router.get("/{widget_id}/component-data", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_component_data(
    widget_id: str,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        if widget.type != "component_reference":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for component_reference widgets")

        if not widget.reference_component:
            raise HTTPException(
                status_code=400, detail="This widget does not reference a component")

        component_id = widget.reference_component

        component = Component_db.objects.get(id=component_id)
        return {
            "component_id": str(component.id),
            "component_type": component.type,
            "data": component.data
        }
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, widgitdetail=f"An unexpected error occurred: {str(e)}"
        )

# TEXT FIELD WIDGET SPECIFIC ENDPOINTS


@router.put("/{widget_id}/text-field/content", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def update_text_field_content(
    widget_id: str,
    content_data: dict,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "text_field":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for text_field widgets")

        # Check if the widget is editable
        widget_data = widget.data or {}
        if widget_data.get("editable") is False:
            raise HTTPException(
                status_code=400, detail="This text field is not editable")

        content = content_data.get("content")
        if content is None:  # Allow empty string as valid content
            raise HTTPException(
                status_code=400, detail="Content field is required")

        # Update the content in the widget data
        widget_data["content"] = content

        # Optional: update title if provided
        if "title" in content_data:
            widget_data["title"] = content_data["title"]

        # Optional: update format if provided
        if "format" in content_data:
            allowed_formats = ["plain", "markdown", "html"]
            if content_data["format"] not in allowed_formats:
                raise HTTPException(
                    status_code=400, detail=f"Format must be one of: {', '.join(allowed_formats)}")
            widget_data["format"] = content_data["format"]

        widget.data = widget_data
        widget.save()

        return {"message": "Text field content updated successfully", "widget": widget.to_mongo().to_dict()}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/{widget_id}/text-field", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_text_field_content(
    widget_id: str,
    user_device: tuple =Depends(verify_device)
):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        if widget.type != "text_field":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for text_field widgets")

        widget_data = widget.data or {}

        # For component reference text fields, fetch the content from the component
        if widget.reference_component:
            component = Component_db.objects.get(
                id=widget.reference_component.id)
            component_data = component.data or {}

            # Create a response that combines widget settings with component content
            response = {
                "content": component_data.get("content", ""),
                "format": widget_data.get("format", "plain"),
                "editable": widget_data.get("editable", False),
                "title": widget_data.get("title", ""),
                "is_component_reference": True,
                "component_id": str(component.id),
                "component_type": component.type
            }
        else:
            # For self-hosted text fields, return the widget data directly
            response = {
                "content": widget_data.get("content", ""),
                "format": widget_data.get("format", "plain"),
                "editable": widget_data.get("editable", True),
                "title": widget_data.get("title", ""),
                "is_component_reference": False
            }

        return response
    except DoesNotExist:
        raise HTTPException(
            status_code=404, detail="Widget or component not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.post("/photo-widget", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_photo_widget(
    data: dict,
    file: UploadFile = File(None),  # Optional photo upload
    user_device : tuple= Depends(verify_device)
):
    """Create a new photo widget."""
    current_user = user_device[0]
    try:
        host_subject_id = data.get("host_subject")
        if not host_subject_id:
            raise HTTPException(status_code=400, detail="Host subject is required")

        # Validate host subject
        host_subject = Subject_db.objects(id=host_subject_id).first()
        if not host_subject:
            raise HTTPException(status_code=404, detail="Host subject not found")

        if current_user.id != host_subject.owner and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to create widget for this subject")

        # Handle photo upload if provided
        photo_url = None
        if file:
            file_content = await file.read()
            result = upload(file_content, folder="photo_widgets")
            photo_url = result["secure_url"]

        # Create the widget
        widget = Widget_db(
            type="photo_widget",
            host_subject=host_subject,
            data={"photo_url": photo_url},
            owner=current_user.id
        )
        widget.save()

        return {"message": "Photo widget created successfully", "widget": widget.to_mongo().to_dict()}
    except CloudinaryError as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/{widget_id}/photo-widget", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_photo_widget(widget_id: str, user_device: tuple = Depends(verify_device)):
    """Retrieve a photo widget."""
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to access this widget")

        if widget.type != "photo_widget":
            raise HTTPException(status_code=400, detail="This endpoint is only for photo widgets")

        return widget.to_mongo().to_dict()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
