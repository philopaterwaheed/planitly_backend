from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from middleWares import verify_device, admin_required
from models import  Subject, Category_db ,Widget_db, Component_db , TEMPLATES , CustomTemplate_db 
from mongoengine.queryset.visitor import Q
from mongoengine.errors import DoesNotExist, ValidationError , NotUniqueError
import datetime
from utils.habit_tracker import HabitTrackerManager
from utils.subject import SubjectVisitManager

router = APIRouter(prefix="/subjects", tags=["Subjects"])

@router.post("/", dependencies=[Depends(verify_device)], status_code=status.HTTP_201_CREATED)
async def create_subject(data: dict, user_device: tuple = Depends(verify_device)):
    """Create a new subject with an optional category."""
    current_user = user_device[0]
    try:
        sub_name = data.get("name") or None
        sub_tem = data.get("template") or None
        category_name = data.get("category") or None
        if not sub_name:
            raise HTTPException(status_code=400, detail="Subject name is required.")

        # Validate subject name length
        if len(sub_name) > 50:
            raise HTTPException(status_code=400, detail="Subject name must be 50 characters or less.")

        # Check for uniqueness of subject name for this user
        existing_subject = Subject_db.objects(name=sub_name, owner=current_user.id).first()
        if existing_subject:
            raise HTTPException(
                status_code=409,
                detail=f"Subject with name '{sub_name}' already exists for this user."
            )

        # Validate the category name
        if category_name:
            category = Category_db.objects(name=category_name, owner=current_user.id).first()
            if not category:
                raise HTTPException(status_code=404, detail=f"Category '{category_name}' not found.")

        subject = Subject(
            name=sub_name,
            owner=current_user.id,
            template=sub_tem,
            category=category_name, 
        )
        if sub_tem:
            await subject.apply_template(sub_tem)
        subject.save_to_db()
        return subject.to_json()
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# get all subjects route
@router.get("/all", dependencies=[Depends(verify_device), Depends(admin_required)], status_code=status.HTTP_200_OK)
async def get_all_subjects():
    """Retrieve all subjects (Admin Only)."""
    try:
        subjects = Subject_db.objects()
        return [subj.to_mongo() for subj in subjects]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")



# get by User_id subjects route
@router.get("/user/{user_id}", status_code=status.HTTP_200_OK)
async def get_user_subjects(user_id: str, user_device: tuple =Depends(verify_device)):
    current_user = user_device[0]
    try:
        """Retrieve subjects for a specific user."""
        if str(current_user.id) == user_id or current_user.admin:
            subjects = Subject_db.objects(owner=user_id).order_by('-created_at') 
            return [subj.to_mongo() for subj in subjects]
        raise HTTPException(
            status_code=403, detail="Not authorized to access these subjects")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# get current user's subjects route with pagination and max limit
@router.get("/", status_code=status.HTTP_200_OK)
async def get_my_subjects(
    user_device: tuple = Depends(verify_device),
    skip: int = 0,
    limit: int = 40
):
    MAX_LIMIT = 40
    current_user = user_device[0]
    try:
        if limit > MAX_LIMIT:
            limit = MAX_LIMIT
        query = Subject_db.objects(owner=current_user.id).order_by('-created_at')
        total = query.count()
        subjects = query.skip(skip).limit(limit)
        return {
            "total": total,
            "subjects": [subj.to_mongo() for subj in subjects]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.put("/{subject_id}", status_code=status.HTTP_200_OK)
async def update_subject(subject_id: str, data: dict, user_device: tuple = Depends(verify_device)):
    """Update a subject by its ID. Prevent editing reference arrays (widgets, components)."""
    current_user = user_device[0]
    try:
        subject = Subject_db.objects.get(id=subject_id)
        if str(current_user.id) == str(subject.owner) or current_user.admin:
            # Prevent editing reference arrays
            for forbidden_field in ["widgets", "components" , "owner" , "template" , "is_deletable" ,  "created_at"  ]:
                if forbidden_field in data:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Editing '{forbidden_field}' is not allowed via this endpoint."
                    )
            subject.update(**data)
            return {"message": f"Subject with ID {subject_id} updated successfully."}
        raise HTTPException(
            status_code=403, detail="Not authorized to update this subject")
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{subject_id}/change-category", status_code=status.HTTP_200_OK)
async def change_subject_category(subject_id: str, data: dict, user_device: tuple = Depends(verify_device)):
    """Change the category of a subject."""
    current_user = user_device[0]
    try:
        new_category_name = data.get("category")
        if not new_category_name:
            raise HTTPException(status_code=400, detail="New category name is required.")

        # Fetch the subject
        subject = Subject_db.objects.get(id=subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found.")

        # Check if the subject has a template
        if subject.template:
            raise HTTPException(
                status_code=403,
                detail="Subjects with templates cannot have their category changed."
            )

        # Validate the new category
        new_category = Category_db.objects(name=new_category_name, owner=current_user.id).first()
        if not new_category:
            raise HTTPException(status_code=404, detail=f"Category '{new_category_name}' not found.")

        # Update the subject's category
        subject.update(category=new_category_name)
        return {"message": f"Subject category updated to '{new_category_name}'."}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{subject_id}/remove-category", status_code=status.HTTP_200_OK)
async def remove_subject_category(subject_id: str, user_device: tuple = Depends(verify_device)):
    """Remove a subject from its category (set to 'Uncategorized')."""
    current_user = user_device[0]
    try:
        # Fetch the subject
        subject = Subject_db.objects.get(id=subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found.")

        # Check if the subject has a template
        if subject.template:
            raise HTTPException(
                status_code=403,
                detail="Subjects with templates cannot be removed from their category."
            )

        # Update the subject's category to 'Uncategorized'
        subject.update(category="Uncategorized")
        return {"message": "Subject category removed and set to 'Uncategorized'."}
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete("/{subject_id}", status_code=status.HTTP_200_OK)
async def delete_subject(subject_id: str, user_device: tuple = Depends(verify_device)):
    current_user = user_device[0]
    try:
        subject = Subject_db.objects.get(id=subject_id)
        
        if not subject.is_deletable:
            raise HTTPException(
                status_code=403, detail="This subject cannot be deleted")

        if str(current_user.id) == str(subject.owner) or current_user.admin:
            # Get all component and widget IDs for bulk deletion
            component_ids = [comp.id for comp in subject.components]
            widget_ids = [widget.id for widget in subject.widgets]
            
            # Bulk delete components
            if component_ids:
                Component_db.objects(id__in=component_ids).delete()
            
            # Bulk delete widgets
            if widget_ids:
                Widget_db.objects(id__in=widget_ids).delete()
            
            # Delete the subject
            subject.delete()
            
            return {
                "message": f"Subject with ID {subject_id} and {len(component_ids)} components and {len(widget_ids)} widgets deleted successfully."
            }
        else:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this subject")
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}")



@router.get("/create-info", status_code=status.HTTP_200_OK)
async def get_subject_creation_info(user_device: tuple = Depends(verify_device)):
    """Get all information needed to create a subject: categories, built-in templates, and custom templates."""
    current_user = user_device[0]
    try:
        # Get user's categories
        categories = Category_db.objects(owner=current_user.id).order_by('name')
        categories_data = [
            {
                "name": category.name,
                "description": category.description or ""
            }
            for category in categories
        ]

        builtin_templates = []
        for template_key, template_data in TEMPLATES.items():
            builtin_templates.append({
                "name": template_key,
                "type": "built-in",
                "category": template_data.get("category", "Uncategorized"),
                "description": f"{template_key.replace('_', ' ').title()} template with {len(template_data.get('components', []))} components and {len(template_data.get('widgets', []))} widgets"
            })

        # Get user's custom templates
        custom_templates = CustomTemplate_db.objects(owner=current_user.id).order_by('name')
        custom_templates_data = []
        for template in custom_templates:
            components_count = len(template.data.get("components", []))
            widgets_count = len(template.data.get("widgets", []))
            custom_templates_data.append({
                "id": str(template.id),
                "name": template.name,
                "type": "custom",
                "category": template.category or "Uncategorized",
                "description": template.description or f"Custom template with {components_count} components and {widgets_count} widgets"
            })

        # Combine all templates
        all_templates = builtin_templates + custom_templates_data

        # Sort templates by category and then by name
        all_templates.sort(key=lambda x: (x["category"], x["name"]))

        # Group templates by category
        templates_by_category = {}
        for template in all_templates:
            category = template["category"]
            if category not in templates_by_category:
                templates_by_category[category] = []
            templates_by_category[category].append(template)

        return {
            "categories": categories_data,
            "templates": {
                "total": len(all_templates),
                "built_in_count": len(builtin_templates),
                "custom_count": len(custom_templates_data),
                "by_category": templates_by_category,
                "all": all_templates
            },
            "creation_rules": {
                "subject_name_required": True,
                "unique_name_per_user": True,
                "template_optional": True,
                "category_optional": True,
                "max_name_length": 50,
                "allowed_characters": "Letters, numbers, spaces, hyphens, and underscores"
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/most-visited", status_code=status.HTTP_200_OK)
async def get_most_visited_subjects(
    user_device: tuple = Depends(verify_device),
    skip: int = 0,
    limit: int = 20
):
    """Get user's most visited subjects with database-side decay calculation."""
    MAX_LIMIT = 50
    current_user = user_device[0]
    try:
        if limit > MAX_LIMIT:
            limit = MAX_LIMIT

        # Apply decay to subjects that need it
        updated_count = await SubjectVisitManager.apply_visit_decay_to_subjects(current_user.id)

        # Get most visited subjects
        result = SubjectVisitManager.get_most_visited_subjects(current_user.id, skip, limit)
        
        return {
            "total": result["total"],
            "subjects": result["subjects"],
            "decay_updates_applied": updated_count
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/visit-stats", status_code=status.HTTP_200_OK)
async def get_visit_statistics(user_device: tuple = Depends(verify_device)):
    """Get visit statistics for the current user's subjects."""
    current_user = user_device[0]
    try:
        subjects = Subject_db.objects(owner=current_user.id)
        
        total_subjects = subjects.count()
        total_visits = 0
        most_visited = None
        most_visited_count = 0
        recently_visited = []
        
        for subject in subjects:
            visit_count = 0
            if isinstance(subject.times_visited, dict):
                visit_count = subject.times_visited.get('count', 0)
            
            total_visits += visit_count
            
            # Track most visited
            if visit_count > most_visited_count:
                most_visited_count = visit_count
                most_visited = {
                    "id": subject.id,
                    "name": subject.name,
                    "visit_count": visit_count
                }
            
            # Track recently visited (last 7 days)
            if subject.last_visited:
                days_ago = (datetime.datetime.utcnow() - subject.last_visited).days
                if days_ago <= 7:
                    recently_visited.append({
                        "id": subject.id,
                        "name": subject.name,
                        "last_visited": subject.last_visited.isoformat(),
                        "days_ago": days_ago
                    })
        
        # Sort recently visited by last_visited date
        recently_visited.sort(key=lambda x: x['last_visited'], reverse=True)
        
        return {
            "total_subjects": total_subjects,
            "total_visits": total_visits,
            "average_visits": round(total_visits / total_subjects, 2) if total_subjects > 0 else 0,
            "most_visited": most_visited,
            "recently_visited": recently_visited[:10]  # Top 10 recently visited
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/habits", status_code=status.HTTP_200_OK)
async def get_user_habit_subjects(
    user_device: tuple = Depends(verify_device),
    skip: int = 0,
    limit: int = 20
):
    """Get user's habit subjects that can be added to Habit Tracker."""
    MAX_LIMIT = 50
    current_user = user_device[0]
    try:
        if limit > MAX_LIMIT:
            limit = MAX_LIMIT

        # Query subjects with "habit" template
        query = Subject_db.objects(owner=current_user.id, template="habit").order_by('-created_at')
        total = query.count()
        subjects = query.skip(skip).limit(limit)
        
        # Convert to response format
        subjects_data = []
        for subject_db in subjects:
            subject_dict = subject_db.to_mongo().to_dict()
            subjects_data.append({
                "id": subject_dict["id"],
                "name": subject_dict["name"],
                "created_at": subject_dict.get("created_at"),
                "template": subject_dict["template"],
                "category": subject_dict.get("category", "Uncategorized")
            })

        return {
            "total": total,
            "habits": subjects_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.put("/{subject_id}/habit/mark-done", status_code=status.HTTP_200_OK)
async def mark_habit_done_for_day(
    subject_id: str, 
    data: dict, 
    user_device: tuple = Depends(verify_device)
):
    """Mark a habit subject as done for a specific day and complete all its daily todos."""
    current_user = user_device[0]
    try:
        # Validate input
        date_str = data.get("date")
        if not date_str:
            raise HTTPException(status_code=400, detail="Date is required")
        
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Fetch the subject
        subject_db = Subject_db.objects.get(id=subject_id)
        if not subject_db:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check authorization
        if str(current_user.id) != str(subject_db.owner) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this subject"
            )

        # Verify this is a habit subject
        if subject_db.template != "habit":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for habit subjects"
            )

        # Find the daily_todo widget in this habit subject
        daily_todo_widget = None
        for widget in subject_db.widgets:
            if widget.type == "daily_todo":
                daily_todo_widget = widget
                break
        
        if not daily_todo_widget:
            raise HTTPException(
                status_code=404, detail="No daily todo widget found in this habit subject"
            )

        # Import Todo_db here to avoid circular imports
        from models.todos import Todo_db

        # Get all todos for this widget and date
        todos = Todo_db.objects(
            widget_id=daily_todo_widget.id,
            date=target_date
        )

        # Mark all todos as completed
        completed_count = 0
        for todo in todos:
            if not todo.completed:
                todo.completed = True
                todo.save()
                completed_count += 1

        return {
            "message": f"Habit marked as done for {date_str}",
            "subject_id": subject_id,
            "subject_name": subject_db.name,
            "date": date_str,
            "todos_completed": completed_count,
            "total_todos": len(todos)
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.put("/{subject_id}/habit/mark-undone", status_code=status.HTTP_200_OK)
async def mark_habit_undone_for_day(
    subject_id: str, 
    data: dict, 
    user_device: tuple = Depends(verify_device)
):
    """Mark a habit subject as undone for a specific day and mark all its daily todos as incomplete."""
    current_user = user_device[0]
    try:
        # Validate input
        date_str = data.get("date")
        if not date_str:
            raise HTTPException(status_code=400, detail="Date is required")
        
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Fetch the subject
        subject_db = Subject_db.objects.get(id=subject_id)
        if not subject_db:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check authorization
        if str(current_user.id) != str(subject_db.owner) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this subject"
            )

        # Verify this is a habit subject
        if subject_db.template != "habit":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for habit subjects"
            )

        # Find the daily_todo widget in this habit subject
        daily_todo_widget = None
        for widget in subject_db.widgets:
            if widget.type == "daily_todo":
                daily_todo_widget = widget
                break
        
        if not daily_todo_widget:
            raise HTTPException(
                status_code=404, detail="No daily todo widget found in this habit subject"
            )

        # Import Todo_db here to avoid circular imports
        from models.todos import Todo_db

        # Get all todos for this widget and date
        todos = Todo_db.objects(
            widget_id=daily_todo_widget.id,
            date=target_date
        )

        # Mark all todos as incomplete
        uncompleted_count = 0
        for todo in todos:
            if todo.completed:
                todo.completed = False
                todo.save()
                uncompleted_count += 1

        return {
            "message": f"Habit marked as undone for {date_str}",
            "subject_id": subject_id,
            "subject_name": subject_db.name,
            "date": date_str,
            "todos_uncompleted": uncompleted_count,
            "total_todos": len(todos)
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/{subject_id}/habit/status", status_code=status.HTTP_200_OK)
async def get_habit_status(
    subject_id: str,
    start_date: str,
    end_date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get habit completion status for a date range."""
    current_user = user_device[0]
    try:
        # Validate dates
        try:
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Fetch the subject
        subject_db = Subject_db.objects.get(id=subject_id)
        if not subject_db:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check authorization
        if str(current_user.id) != str(subject_db.owner) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this subject"
            )

        # Verify this is a habit subject
        if subject_db.template != "habit":
            raise HTTPException(
                status_code=400, detail="This endpoint is only for habit subjects"
            )

        # Find the daily_todo widget
        daily_todo_widget = None
        for widget in subject_db.widgets:
            if widget.type == "daily_todo":
                daily_todo_widget = widget
                break
        
        if not daily_todo_widget:
            return {
                "subject_id": subject_id,
                "subject_name": subject_db.name,
                "start_date": start_date,
                "end_date": end_date,
                "status_by_date": {},
                "completion_rate": 0.0
            }

        # Import Todo_db here to avoid circular imports
        from models.todos import Todo_db

        # Get all todos in the date range
        end_of_day = end + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
        todos = Todo_db.objects(
            widget_id=daily_todo_widget.id,
            date__gte=start,
            date__lte=end_of_day
        ).order_by('date')

        # Group todos by date and calculate completion status
        status_by_date = {}
        current_date = start
        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            date_todos = [todo for todo in todos if todo.date.strftime("%Y-%m-%d") == date_str]
            
            if date_todos:
                completed_todos = [todo for todo in date_todos if todo.completed]
                status_by_date[date_str] = {
                    "completed": len(completed_todos),
                    "total": len(date_todos),
                    "completion_rate": len(completed_todos) / len(date_todos),
                    "is_complete": len(completed_todos) == len(date_todos) and len(date_todos) > 0
                }
            else:
                status_by_date[date_str] = {
                    "completed": 0,
                    "total": 0,
                    "completion_rate": 0.0,
                    "is_complete": False
                }
            
            current_date += datetime.timedelta(days=1)

        # Calculate overall completion rate
        total_days = len(status_by_date)
        completed_days = sum(1 for status in status_by_date.values() if status["is_complete"])
        overall_completion_rate = completed_days / total_days if total_days > 0 else 0.0

        return {
            "subject_id": subject_id,
            "subject_name": subject_db.name,
            "start_date": start_date,
            "end_date": end_date,
            "status_by_date": status_by_date,
            "completion_rate": round(overall_completion_rate, 2),
            "completed_days": completed_days,
            "total_days": total_days
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/habits/daily-status/{date}", status_code=status.HTTP_200_OK)
async def get_daily_habits_status_optimized(
    date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get all user's habits categorized as done/not done for a specific date (optimized version)."""
    current_user = user_device[0]
    try:
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Use optimized habit tracker
        status = await HabitTrackerManager.get_daily_habits_status(current_user.id, date)
        
        completion_rate = 0.0
        if status["total_habits"] > 0:
            completion_rate = len(status["done_habits"]) / status["total_habits"]

        return {
            "date": date,
            "total_habits": status["total_habits"],
            "done_habits": {
                "count": len(status["done_habits"]),
                "habits": status["done_habits"]
            },
            "not_done_habits": {
                "count": len(status["not_done_habits"]),
                "habits": status["not_done_habits"]
            },
            "completion_rate": round(completion_rate, 2)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/habits/done/{date}", status_code=status.HTTP_200_OK)
async def get_done_habits_for_date_optimized(
    date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get all user's habits that are marked as done for a specific date (optimized version)."""
    current_user = user_device[0]
    try:
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        status = await HabitTrackerManager.get_daily_habits_status(current_user.id, date)

        return {
            "date": date,
            "count": len(status["done_habits"]),
            "done_habits": status["done_habits"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/habits/not-done/{date}", status_code=status.HTTP_200_OK)
async def get_not_done_habits_for_date_optimized(
    date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get all user's habits that are not marked as done for a specific date (optimized version)."""
    current_user = user_device[0]
    try:
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        status = await HabitTrackerManager.get_daily_habits_status(current_user.id, date)

        return {
            "date": date,
            "count": len(status["not_done_habits"]),
            "not_done_habits": status["not_done_habits"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/{subject_id}/habit/detailed-status/{date}", status_code=status.HTTP_200_OK)
async def get_habit_detailed_status(
    subject_id: str,
    date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get detailed status for a specific habit including todos and completion percentage."""
    current_user = user_device[0]
    try:
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Verify subject exists and user has access
        subject_db = Subject_db.objects.get(id=subject_id)
        if not subject_db:
            raise HTTPException(status_code=404, detail="Subject not found")

        if str(current_user.id) != str(subject_db.owner) and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to access this subject")

        if subject_db.template != "habit":
            raise HTTPException(status_code=400, detail="This endpoint is only for habit subjects")

        # Get detailed status
        detailed_status = await HabitTrackerManager.get_habit_detailed_status(
            current_user.id, subject_id, date
        )

        return detailed_status

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/habits/daily-status/{date}", status_code=status.HTTP_200_OK)
async def get_daily_habits_status_optimized(
    date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get all user's habits categorized as done/not done for a specific date (optimized version)."""
    current_user = user_device[0]
    try:
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Use optimized habit tracker
        status = await HabitTrackerManager.get_daily_habits_status(current_user.id, date)
        
        completion_rate = 0.0
        if status["total_habits"] > 0:
            completion_rate = len(status["done_habits"]) / status["total_habits"]

        return {
            "date": date,
            "total_habits": status["total_habits"],
            "done_habits": {
                "count": len(status["done_habits"]),
                "habits": status["done_habits"]
            },
            "not_done_habits": {
                "count": len(status["not_done_habits"]),
                "habits": status["not_done_habits"]
            },
            "completion_rate": round(completion_rate, 2)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/habits/done/{date}", status_code=status.HTTP_200_OK)
async def get_done_habits_for_date_optimized(
    date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get all user's habits that are marked as done for a specific date (optimized version)."""
    current_user = user_device[0]
    try:
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        status = await HabitTrackerManager.get_daily_habits_status(current_user.id, date)

        return {
            "date": date,
            "count": len(status["done_habits"]),
            "done_habits": status["done_habits"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/habits/not-done/{date}", status_code=status.HTTP_200_OK)
async def get_not_done_habits_for_date_optimized(
    date: str,
    user_device: tuple = Depends(verify_device)
):
    """Get all user's habits that are not marked as done for a specific date (optimized version)."""
    current_user = user_device[0]
    try:
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        status = await HabitTrackerManager.get_daily_habits_status(current_user.id, date)

        return {
            "date": date,
            "count": len(status["not_done_habits"]),
            "not_done_habits": status["not_done_habits"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.put("/{subject_id}/habit/mark-done-optimized", status_code=status.HTTP_200_OK)
async def mark_habit_done_optimized(
    subject_id: str, 
    data: dict, 
    user_device: tuple = Depends(verify_device)
):
    """Mark a habit as done using optimized habit tracker."""
    current_user = user_device[0]
    try:
        # Validate that the subject exists and is a habit
        subject_db = Subject_db.objects.get(id=subject_id)
        if not subject_db:
            raise HTTPException(status_code=404, detail="Subject not found")

        if str(current_user.id) != str(subject_db.owner) and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to update this subject")

        if subject_db.template != "habit":
            raise HTTPException(status_code=400, detail="This endpoint is only for habit subjects")

        # Use optimized habit tracker
        success = await HabitTrackerManager.mark_habit_done(current_user.id, subject_id, True)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to mark habit as done")

        return {
            "message": "Habit marked as done",
            "subject_id": subject_id,
            "subject_name": subject_db.name,
            "status": "done"
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{subject_id}/habit/mark-undone-optimized", status_code=status.HTTP_200_OK)
async def mark_habit_undone_optimized(
    subject_id: str, 
    data: dict, 
    user_device: tuple = Depends(verify_device)
):
    """Mark a habit as undone using optimized habit tracker."""
    current_user = user_device[0]
    try:
        # Validate that the subject exists and is a habit
        subject_db = Subject_db.objects.get(id=subject_id)
        if not subject_db:
            raise HTTPException(status_code=404, detail="Subject not found")

        if str(current_user.id) != str(subject_db.owner) and not current_user.admin:
            raise HTTPException(status_code=403, detail="Not authorized to update this subject")

        if subject_db.template != "habit":
            raise HTTPException(status_code=400, detail="This endpoint is only for habit subjects")

        # Use optimized habit tracker
        success = await HabitTrackerManager.mark_habit_done(current_user.id, subject_id, False)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to mark habit as undone")

        return {
            "message": "Habit marked as undone",
            "subject_id": subject_id,
            "subject_name": subject_db.name,
            "status": "not_done"
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

#todo check the security of this route
@router.get("/{subject_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_subject(subject_id: str):
    """Retrieve a subject by its ID."""
    try:
        subject = Subject_db.objects.get(id=subject_id)
        return subject.to_mongo()
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")


@router.get("/{subject_id}/full-data", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def get_subject_full_data(subject_id: str, user_device: tuple = Depends(verify_device)):
    """Retrieve all data inside a subject, including its components and widgets, and record the visit."""
    current_user = user_device[0]
    try:
        # Fetch the subject
        subject_db = Subject_db.objects.get(id=subject_id)
        if not subject_db:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Check if the user is authorized to access the subject
        if str(current_user.id) != str(subject_db.owner) and not current_user.admin:
            raise HTTPException(
                status_code=403, detail="Not authorized to access this subject"
            )

        # Convert to Subject instance to use the increment method and get full data
        subject = Subject.from_db(subject_db)
        
        # Record the visit (increment visit count with decay mechanism)
        subject.increment_visit_count()
        
        # Update the database with visit data
        subject_db.update(
            times_visited=subject.times_visited,
            last_visited=subject.last_visited
        )
        
        # Get the full data
        full_data = await subject.get_full_data()
        
        # Add visit information to the response
        full_data["visit_info"] = {
            "times_visited": subject.times_visited.get('count', 0) if isinstance(subject.times_visited, dict) else 0,
            "last_visited": subject.last_visited.isoformat() if subject.last_visited else None,
            "visit_recorded": True
        }
        
        return full_data

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Subject not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )