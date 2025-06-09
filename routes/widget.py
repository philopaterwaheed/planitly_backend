# routers/widget.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from datetime import datetime, timedelta
from models import Widget_db, Subject, Component_db, Subject_db, Todo_db, Todo, User
from mongoengine.errors import DoesNotExist, ValidationError
from middleWares import verify_device
from utils import decode_name_from_url, encode_name_for_url
import uuid
from typing import Optional
from cloudinary.uploader import upload
from cloudinary.exceptions import Error as CloudinaryError
from cloud import extract_public_id_from_url

router = APIRouter(prefix="/widgets", tags=["Widget"])


@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_widget(data: dict, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    try:
        widget_name = data.get("name")
        widget_type = data.get("type")
        host_subject_id = data.get("host_subject")
        reference_component_id = data.get("reference_component")
        widget_data = data.get("data", {})

        if not widget_name or not widget_type or not host_subject_id:
            raise HTTPException(
                status_code=400, detail="Name, Type, and Host Subject are required."
            )

        # Load the host subject
        subject = Subject.load_from_db(host_subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Host subject not found")
        
        # Check authorization
        if subject.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to create widgets for this subject"
            )

        # Get reference component if provided
        reference_component = None
        if reference_component_id:
            reference_component = Component_db.objects.get(id=reference_component_id)

        # Use subject's add_widget function
        widget = await subject.add_widget(
            widget_name=widget_name,
            widget_type=widget_type,
            data=widget_data,
            reference_component=reference_component_id,
            is_deletable=data.get("is_deletable", True)
        )

        if not widget:
            raise HTTPException(
                status_code=400, detail="Failed to create widget - validation error"
            )

        return {"message": "Widget created successfully", "id": widget.id}
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
async def delete_widget(widget_id: str, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this widget")

        # Check if the widget is deletable
        if widget.is_deletable == "false":
            raise HTTPException(
                status_code=400, detail="This widget cannot be deleted")

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
        from models.arrayItem import Arrays
        
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

        # Clear existing columns array and add new columns
        Arrays.delete_array(current_user.id, widget_id, "widget")
        columns_result = Arrays.create_array(
            user_id=current_user.id,
            host_id=widget_id,
            array_name=f"{widget.name}_columns",
            host_type="widget",
            initial_elements=columns
        )
        
        if not columns_result["success"]:
            raise HTTPException(
                status_code=500, detail=f"Failed to update columns: {columns_result['message']}")

        return {"message": "Table columns updated successfully", "widget": widget.to_mongo().to_dict()}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/{widget_id}/table/columns", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_table_columns(
    widget_id: str,
    page: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=1000),
    user_device: tuple = Depends(verify_device)
):
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays
        
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        if widget.type != "table":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for table widgets")

        # Get columns from array
        columns_result = Arrays.get_array(
            user_id=current_user.id,
            host_id=widget_id,
            host_type="widget",
            page=page,
            page_size=page_size
        )
        
        if not columns_result["success"]:
            raise HTTPException(
                status_code=500, detail=f"Failed to get columns: {columns_result['message']}")

        return {
            "columns": [item["value"] for item in columns_result["array"]],
            "pagination": columns_result["pagination"]
        }
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
        from models.arrayItem import Arrays
        
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

        # Add row ID if not provided
        if "id" not in row:
            row["id"] = str(uuid.uuid4())

        # Add row to rows array
        rows_result = Arrays.append_to_array(
            user_id=current_user.id,
            host_id=widget_id,
            value=row,
            host_type="widget"
        )
        
        if not rows_result["success"]:
            raise HTTPException(
                status_code=500, detail=f"Failed to add row: {rows_result['message']}")

        return {"message": "Table row added successfully", "row": row}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/{widget_id}/table/rows", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_table_rows(
    widget_id: str,
    page: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=1000),
    user_device: tuple = Depends(verify_device)
):
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays
        
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        if widget.type != "table":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for table widgets")

        # Get rows from array with pagination
        rows_result = Arrays.get_array(
            user_id=current_user.id,
            host_id=widget_id,
            host_type="widget",
            page=page,
            page_size=page_size
        )
        
        if not rows_result["success"]:
            raise HTTPException(
                status_code=500, detail=f"Failed to get rows: {rows_result['message']}")

        return {
            "rows": [item["value"] for item in rows_result["array"]],
            "pagination": rows_result["pagination"]
        }
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
        widget_name = data.get("name")
        if not host_subject_id:
            raise HTTPException(status_code=400, detail="Host subject is required")
        if not widget_name:
            raise HTTPException(status_code=400, detail="Widget name is required")
        if not file:
            raise HTTPException(status_code=400, detail="File is required")
        if not file.filename.endswith(('.jpg', '.jpeg', '.png')):
            raise HTTPException(status_code=400, detail="Invalid file type. Only JPG and PNG are allowed")
        if file.size > 5 * 1024 * 1024:  # 5 MB limit
            raise HTTPException(status_code=400, detail="File size exceeds 5 MB limit")
 
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
            name=widget_name,
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


@router.put("/{widget_id}/daily-todo/mark-all-done", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def mark_all_todos_done_for_date(
    widget_id: str,
    data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Mark all todos as done for a specific date."""
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        # Get the date
        date_str = data.get("date")
        if not date_str:
            raise HTTPException(status_code=400, detail="Date is required")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Get all todos for this date
        todos = Todo_db.objects(widget_id=widget_id, date=target_date)

        # Mark all as completed
        completed_count = 0
        for todo in todos:
            if not todo.completed:
                todo.completed = True
                todo.save()
                completed_count += 1

        return {
            "message": f"All todos marked as done for {date_str}",
            "date": date_str,
            "todos_completed": completed_count,
            "total_todos": len(todos)
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.put("/{widget_id}/daily-todo/mark-all-undone", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def mark_all_todos_undone_for_date(
    widget_id: str,
    data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Mark all todos as undone for a specific date."""
    current_user = user_device[0]
    try:
        widget = Widget_db.objects.get(id=widget_id)

        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        if widget.type != "daily_todo":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for daily_todo widgets")

        # Get the date
        date_str = data.get("date")
        if not date_str:
            raise HTTPException(status_code=400, detail="Date is required")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Get all todos for this date
        todos = Todo_db.objects(widget_id=widget_id, date=target_date)

        # Mark all as incomplete
        uncompleted_count = 0
        for todo in todos:
            if todo.completed:
                todo.completed = False
                todo.save()
                uncompleted_count += 1

        return {
            "message": f"All todos marked as undone for {date_str}",
            "date": date_str,
            "todos_uncompleted": uncompleted_count,
            "total_todos": len(todos)
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

# GENERIC ARRAY WIDGET ENDPOINTS BY WIDGET ID ONLY

@router.put("/{widget_id}/array/{array_name}/element/{index}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def update_array_element_by_widget_id(
    widget_id: str,
    array_name: str,
    index: int,
    element_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Update a single element in a widget's array by index using only widget ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_name)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Get the new value from request data
        new_value = element_data.get("value")
        if new_value is None:
            raise HTTPException(
                status_code=400, detail="Value field is required")

        # Update the element using Arrays class with decoded array_name parameter
        result = Arrays.update_at_index(
            user_id=current_user.id,
            host_id=widget_id,
            index=index,
            value=new_value,
            host_type="widget",
            array_name=decoded_array_name
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=f"Failed to update element: {result['message']}")

        return {
            "message": f"Element at index {index} updated successfully",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_name": decoded_array_name,
            "index": index,
            "new_value": new_value
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.delete("/{widget_id}/array/{array_name}/element/{index}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def delete_array_element_by_widget_id(
    widget_id: str,
    array_name: str,
    index: int,
    user_device: tuple = Depends(verify_device)
):
    """Delete a single element from a widget's array by index using only widget ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_name)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Remove the element using Arrays class with decoded array_name parameter
        result = Arrays.remove_at_index(
            user_id=current_user.id,
            host_id=widget_id,
            index=index,
            host_type="widget",
            array_name=decoded_array_name
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=f"Failed to delete element: {result['message']}")

        return {
            "message": f"Element at index {index} deleted successfully",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_name": decoded_array_name,
            "index": index
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post("/{widget_id}/array/{array_name}/element", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def add_array_element_by_widget_id(
    widget_id: str,
    array_name: str,
    element_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Add a single element to a widget's array using only widget ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_name)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Get the new value from request data
        new_value = element_data.get("value")
        if new_value is None:
            raise HTTPException(
                status_code=400, detail="Value field is required")

        # Check if we should insert at specific index or append
        index = element_data.get("index")
        
        if index is not None:
            # Insert at specific index
            result = Arrays.insert_at_index(
                user_id=current_user.id,
                host_id=widget_id,
                index=index,
                value=new_value,
                host_type="widget",
                array_name=decoded_array_name
            )
        else:
            # Append to end
            result = Arrays.append_to_array(
                user_id=current_user.id,
                host_id=widget_id,
                value=new_value,
                host_type="widget",
                array_name=decoded_array_name
            )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=f"Failed to add element: {result['message']}")

        return {
            "message": "Element added successfully",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_name": decoded_array_name,
            "value": new_value,
            "index": index if index is not None else "appended"
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/{widget_id}/array/{array_name}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_widget_array_by_id(
    widget_id: str,
    array_name: str,
    page: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=1000),
    user_device: tuple = Depends(verify_device)
):
    """Get a widget's array by name using only widget ID with pagination."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayMetadata
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_name)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        # Get array by name using enhanced function
        result = Arrays.get_array_by_name(
            user_id=current_user.id,
            host_id=widget_id,
            array_name=decoded_array_name,
            host_type="widget",
            page=page,
            page_size=page_size
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=404, detail=f"Array not found: {result['message']}")

        return {
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_name": decoded_array_name,
            "elements": [item["value"] for item in result["array"]],
            "pagination": result["pagination"]
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.put("/{widget_id}/array/{array_name}/bulk-update", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def bulk_update_array_elements_by_widget_id(
    widget_id: str,
    array_name: str,
    bulk_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Bulk update multiple elements in a widget's array using only widget ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_name)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Get the updates from request data
        updates = bulk_data.get("updates")
        if not updates or not isinstance(updates, list):
            raise HTTPException(
                status_code=400, detail="Updates field with list of updates is required")

        successful_updates = 0
        failed_updates = []

        # Process each update
        for update in updates:
            index = update.get("index")
            value = update.get("value")
            
            if index is None or value is None:
                failed_updates.append({
                    "update": update,
                    "error": "Both index and value are required"
                })
                continue

            # Update the element using enhanced function
            result = Arrays.update_at_index(
                user_id=current_user.id,
                host_id=widget_id,
                index=index,
                value=value,
                host_type="widget",
                array_name=decoded_array_name
            )
            
            if result["success"]:
                successful_updates += 1
            else:
                failed_updates.append({
                    "update": update,
                    "error": result["message"]
                })

        return {
            "message": f"Bulk update completed",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_name": decoded_array_name,
            "successful_updates": successful_updates,
            "failed_updates": len(failed_updates),
            "failed_details": failed_updates
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.delete("/{widget_id}/array/{array_name}/bulk-delete", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def bulk_delete_array_elements_by_widget_id(
    widget_id: str,
    array_name: str,
    bulk_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Bulk delete multiple elements from a widget's array using only widget ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_name)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Get the indices from request data
        indices = bulk_data.get("indices")
        if not indices or not isinstance(indices, list):
            raise HTTPException(
                status_code=400, detail="Indices field with list of indices is required")

        # Sort indices in descending order to avoid index shifting issues
        indices.sort(reverse=True)

        successful_deletions = 0
        failed_deletions = []

        # Process each deletion
        for index in indices:
            if not isinstance(index, int):
                failed_deletions.append({
                    "index": index,
                    "error": "Index must be an integer"
                })
                continue

            # Delete the element using enhanced function
            result = Arrays.remove_at_index(
                user_id=current_user.id,
                host_id=widget_id,
                index=index,
                host_type="widget",
                array_name=decoded_array_name
            )
            
            if result["success"]:
                successful_deletions += 1
            else:
                failed_deletions.append({
                    "index": index,
                    "error": result["message"]
                })

        return {
            "message": f"Bulk deletion completed",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_name": decoded_array_name,
            "successful_deletions": successful_deletions,
            "failed_deletions": len(failed_deletions),
            "failed_details": failed_deletions
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/{widget_id}/array/{array_name}/search", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def search_in_widget_array(
    widget_id: str,
    array_name: str,
    search_value: str = Query(..., description="Value to search for"),
    user_device: tuple = Depends(verify_device)
):
    """Search for a value in a widget's array using only widget ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayItem_db, ArrayMetadata
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_name)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        # Get user object
        user = User.objects(id=current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get array metadata by name
        array_metadata = Arrays._get_array_metadata_by_name(user, widget_id, "widget", decoded_array_name)
        if not array_metadata:
            raise HTTPException(
                status_code=404, detail=f"Array '{decoded_array_name}' not found for widget")

        # Search for elements containing the search value
        # For exact match
        exact_matches = ArrayItem_db.objects(
            user=user,
            array_metadata=array_metadata,
            value=search_value
        )

        # For partial matches (if value is string)
        partial_matches = []
        if isinstance(search_value, str):
            # This is a simplified search - you might want to implement more sophisticated search
            all_elements = ArrayItem_db.objects(
                user=user,
                array_metadata=array_metadata
            )
            
            for element in all_elements:
                if isinstance(element.value, str) and search_value.lower() in element.value.lower():
                    if element not in exact_matches:  # Avoid duplicates
                        partial_matches.append(element)

        exact_results = [{"index": elem.index, "value": elem.value} for elem in exact_matches]
        partial_results = [{"index": elem.index, "value": elem.value} for elem in partial_matches]

        return {
            "widget_id": widget_id,
            "widget_name": widget.name,
            "array_name": decoded_array_name,
            "search_value": search_value,
            "exact_matches": exact_results,
            "partial_matches": partial_results,
            "total_matches": len(exact_results) + len(partial_results)
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

# ARRAY WIDGET ENDPOINTS BY WIDGET ID AND ARRAY ID

@router.put("/{widget_id}/array/id/{array_id}/element/{index}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def update_array_element_by_array_id(
    widget_id: str,
    array_id: str,
    index: int,
    element_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Update a single element in a widget's array by index using widget ID and array ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayMetadata
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Verify array metadata exists and belongs to this widget and user
        array_metadata = ArrayMetadata.objects.get(
            id=array_id,
            user=current_user.id,
            host_widget=widget_id
        )

        # Get the new value from request data
        new_value = element_data.get("value")
        if new_value is None:
            raise HTTPException(
                status_code=400, detail="Value field is required")

        # Update the element using enhanced function with array_id
        result = Arrays.update_at_index(
            user_id=current_user.id,
            host_id=widget_id,
            index=index,
            value=new_value,
            host_type="widget",
            array_id=array_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=f"Failed to update element: {result['message']}")

        return {
            "message": f"Element at index {index} updated successfully",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_id": array_id,
            "array_name": array_metadata.name,
            "index": index,
            "new_value": new_value
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or array not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.delete("/{widget_id}/array/id/{array_id}/element/{index}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def delete_array_element_by_array_id(
    widget_id: str,
    array_id: str,
    index: int,
    user_device: tuple = Depends(verify_device)
):
    """Delete a single element from a widget's array by index using widget ID and array ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayMetadata
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Verify array metadata exists and belongs to this widget and user
        array_metadata = ArrayMetadata.objects.get(
            id=array_id,
            user=current_user.id,
            host_widget=widget_id
        )

        # Remove the element using Arrays class
        result = Arrays.remove_at_index(
            user_id=current_user.id,
            host_id=widget_id,
            index=index,
            host_type="widget",
            array_id=array_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=f"Failed to delete element: {result['message']}")

        return {
            "message": f"Element at index {index} deleted successfully",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_id": array_id,
            "array_name": array_metadata.name,
            "index": index
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or array not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post("/{widget_id}/array/id/{array_id}/element", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def add_array_element_by_array_id(
    widget_id: str,
    array_id: str,
    element_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Add a single element to a widget's array using widget ID and array ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayMetadata
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Verify array metadata exists and belongs to this widget and user
        array_metadata = ArrayMetadata.objects.get(
            id=array_id,
            user=current_user.id,
            host_widget=widget_id
        )

        # Get the new value from request data
        new_value = element_data.get("value")
        if new_value is None:
            raise HTTPException(
                status_code=400, detail="Value field is required")

        # Check if we should insert at specific index or append
        index = element_data.get("index")
        
        if index is not None:
            # Insert at specific index
            result = Arrays.insert_at_index(
                user_id=current_user.id,
                host_id=widget_id,
                index=index,
                value=new_value,
                host_type="widget",
                array_id=array_id
            )
        else:
            # Append to end
            result = Arrays.append_to_array(
                user_id=current_user.id,
                host_id=widget_id,
                value=new_value,
                host_type="widget",
                array_id=array_id
            )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=f"Failed to add element: {result['message']}")

        return {
            "message": "Element added successfully",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_id": array_id,
            "array_name": array_metadata.name,
            "value": new_value,
            "index": index if index is not None else "appended"
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or array not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/{widget_id}/array/id/{array_id}", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def get_widget_array_by_array_id(
    widget_id: str,
    array_id: str,
    page: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=1000),
    user_device: tuple = Depends(verify_device)
):
    """Get a widget's array using widget ID and array ID with pagination."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayMetadata
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        # Verify array metadata exists and belongs to this widget and user
        array_metadata = ArrayMetadata.objects.get(
            id=array_id,
            user=current_user.id,
            host_widget=widget_id
        )

        # Get array by ID using enhanced function
        result = Arrays.get_array_by_name(
            user_id=current_user.id,
            host_id=widget_id,
            host_type="widget",
            page=page,
            page_size=page_size,
            array_id=array_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=404, detail=f"Array not found: {result['message']}")

        return {
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_id": array_id,
            "array_name": array_metadata.name,
            "elements": [item["value"] for item in result["array"]],
            "pagination": result["pagination"]
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or array not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.put("/{widget_id}/array/id/{array_id}/bulk-update", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def bulk_update_array_elements_by_array_id(
    widget_id: str,
    array_id: str,
    bulk_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Bulk update multiple elements in a widget's array using widget ID and array ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayMetadata
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Verify array metadata exists and belongs to this widget and user
        array_metadata = ArrayMetadata.objects.get(
            id=array_id,
            user=current_user.id,
            host_widget=widget_id
        )

        # Get the updates from request data
        updates = bulk_data.get("updates")
        if not updates or not isinstance(updates, list):
            raise HTTPException(
                status_code=400, detail="Updates field with list of updates is required")

        successful_updates = 0
        failed_updates = []

        # Process each update
        for update in updates:
            index = update.get("index")
            value = update.get("value")
            
            if index is None or value is None:
                failed_updates.append({
                    "update": update,
                    "error": "Both index and value are required"
                })
                continue

            # Update the element using enhanced function
            result = Arrays.update_at_index(
                user_id=current_user.id,
                host_id=widget_id,
                index=index,
                value=value,
                host_type="widget",
                array_id=array_id
            )
            
            if result["success"]:
                successful_updates += 1
            else:
                failed_updates.append({
                    "update": update,
                    "error": result["message"]
                })

        return {
            "message": f"Bulk update completed",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_id": array_id,
            "array_name": array_metadata.name,
            "successful_updates": successful_updates,
            "failed_updates": len(failed_updates),
            "failed_details": failed_updates
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or array not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.delete("/{widget_id}/array/id/{array_id}/bulk-delete", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def bulk_delete_array_elements_by_array_id(
    widget_id: str,
    array_id: str,
    bulk_data: dict,
    user_device: tuple = Depends(verify_device)
):
    """Bulk delete multiple elements from a widget's array using widget ID and array ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayMetadata
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this widget")

        # Verify array metadata exists and belongs to this widget and user
        array_metadata = ArrayMetadata.objects.get(
            id=array_id,
            user=current_user.id,
            host_widget=widget_id
        )

        # Get the indices from request data
        indices = bulk_data.get("indices")
        if not indices or not isinstance(indices, list):
            raise HTTPException(
                status_code=400, detail="Indices field with list of indices is required")

        # Sort indices in descending order to avoid index shifting issues
        indices.sort(reverse=True)

        successful_deletions = 0
        failed_deletions = []

        # Process each deletion
        for index in indices:
            if not isinstance(index, int):
                failed_deletions.append({
                    "index": index,
                    "error": "Index must be an integer"
                })
                continue

            # Delete the element using enhanced function
            result = Arrays.remove_at_index(
                user_id=current_user.id,
                host_id=widget_id,
                index=index,
                host_type="widget",
                array_id=array_id
            )
            
            if result["success"]:
                successful_deletions += 1
            else:
                failed_deletions.append({
                    "index": index,
                    "error": result["message"]
                })

        return {
            "message": f"Bulk deletion completed",
            "widget_id": widget_id,
            "widget_name": widget.name,
            "widget_type": widget.widget_type,
            "array_id": array_id,
            "array_name": array_metadata.name,
            "successful_deletions": successful_deletions,
            "failed_deletions": len(failed_deletions),
            "failed_details": failed_deletions
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or array not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/{widget_id}/array/id/{array_id}/search", dependencies=[Depends(verify_device)], status_code=status.HTTP_200_OK)
async def search_in_widget_array_by_array_id(
    widget_id: str,
    array_id: str,
    search_value: str = Query(..., description="Value to search for"),
    user_device: tuple = Depends(verify_device)
):
    """Search for a value in a widget's array using widget ID and array ID."""
    current_user = user_device[0]
    try:
        from models.arrayItem import Arrays, ArrayItem_db, ArrayMetadata
        
        # Decode the array name from URL
        decoded_array_name = decode_name_from_url(array_id)
        
        # Verify widget exists and user has access
        widget = Widget_db.objects.get(id=widget_id)
        
        if widget.owner != current_user.id and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this widget")

        # Verify array metadata exists and belongs to this widget and user
        array_metadata = ArrayMetadata.objects.get(
            id=array_id,
            user=current_user.id,
            host_widget=widget_id
        )

        # Search for elements containing the search value
        # For exact match
        exact_matches = ArrayItem_db.objects(
            user=current_user.id,
            array_metadata=array_metadata,
            value=search_value
        )

        # For partial matches (if value is string)
        partial_matches = []
        if isinstance(search_value, str):
            # This is a simplified search - you might want to implement more sophisticated search
            all_elements = ArrayItem_db.objects(
                user=current_user.id,
                array_metadata=array_metadata
            )
            
            for element in all_elements:
                if isinstance(element.value, str) and search_value.lower() in element.value.lower():
                    if element not in exact_matches:  # Avoid duplicates
                        partial_matches.append(element)

        exact_results = [{"index": elem.index, "value": elem.value} for elem in exact_matches]
        partial_results = [{"index": elem.index, "value": elem.value} for elem in partial_matches]

        return {
            "widget_id": widget_id,
            "widget_name": widget.name,
            "array_id": array_id,
            "array_name": array_metadata.name,
            "search_value": search_value,
            "exact_matches": exact_results,
            "partial_matches": partial_results,
            "total_matches": len(exact_results) + len(partial_results)
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Widget or array not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
