from fastapi import APIRouter, Depends, HTTPException, status
from models import Subject_db
from middleWares import verify_device
from models import Category_db , Connection_db, TEMPLATES, CustomTemplate_db
import datetime
from utils.habit_tracker import HabitTrackerManager
from utils.subject import SubjectVisitManager

router = APIRouter(prefix="/home", tags=["Home"])

@router.get("/", status_code=status.HTTP_200_OK)
async def get_home_page_data(user_device: tuple = Depends(verify_device)):
    """Get comprehensive home page data including today's habits, connections, most visited subjects, recent categories, and templates."""
    current_user = user_device[0]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    try:
        await SubjectVisitManager.apply_visit_decay_to_subjects(current_user.id)

        # Get today's habits status with detailed progress
        habits_status = await HabitTrackerManager.get_daily_habits_status(current_user.id, today)
        habits_completion_rate = 0.0
        if habits_status["total_habits"] > 0:
            habits_completion_rate = len(habits_status["done_habits"]) / habits_status["total_habits"]

        # Get detailed progress for all tracked habits
        all_habits_progress = []
        
        # Combine done and not done habits for complete progress overview
        all_tracked_habits = habits_status["done_habits"] + habits_status["not_done_habits"]
        
        for habit in all_tracked_habits:
            # Get detailed status for each habit
            detailed_status = await HabitTrackerManager.get_habit_detailed_status(
                current_user.id, habit["id"], today
            )
            
            habit_progress = {
                "id": habit["id"],
                "name": habit["name"],
                "category": habit.get("category", "Uncategorized"),
                "is_done": habit["is_done"],
                "completion_percentage": habit["completion_percentage"],
                "manually_marked": habit.get("manually_marked", False),
                "has_todos": detailed_status.get("has_todos", False),
                "todos_count": len(detailed_status.get("todos", [])),
                "completed_todos_count": len([t for t in detailed_status.get("todos", []) if t.get("completed", False)]),
                "created_at": habit.get("created_at")
            }
            
            # Add todos breakdown if available
            if detailed_status.get("todos"):
                habit_progress["todos"] = detailed_status["todos"]
            
            all_habits_progress.append(habit_progress)

        # Sort habits by completion status (done first) and then by name
        all_habits_progress.sort(key=lambda x: (not x["is_done"], x["name"]))

        # Get today's connections (due today) - using end_date
        today_date = datetime.datetime.strptime(today, "%Y-%m-%d")
        tomorrow = today_date + datetime.timedelta(days=1)
        
        connections_query = Connection_db.objects(
            owner=current_user.id,
            end_date__gte=today_date,
            end_date__lt=tomorrow,
            done=False  # Only get connections that are not done yet
        ).order_by('end_date')
        
        connections_data = []
        for conn in connections_query[:10]:  # Limit to 10 connections
            conn_dict = conn.to_mongo().to_dict()
            connections_data.append({
                "id": conn_dict["id"],
                "con_type": conn_dict.get("con_type", "Unknown"),
                "end_date": conn_dict["end_date"].isoformat() if conn_dict.get("end_date") else None,
                "start_date": conn_dict["start_date"].isoformat() if conn_dict.get("start_date") else None,
                "source_subject": str(conn_dict.get("source_subject")) if conn_dict.get("source_subject") else None,
                "target_subject": str(conn_dict.get("target_subject")) if conn_dict.get("target_subject") else None,
                "done": conn_dict.get("done", False)
            })

        # Get most visited subjects (top 5) with decay already applied
        most_visited_result = SubjectVisitManager.get_most_visited_subjects(current_user.id, 0, 5)
        print (f"Most visited subjects: {most_visited_result}")
        most_visited_subjects = [
            SubjectVisitManager.format_subject_for_home(subject) 
            for subject in most_visited_result["subjects"]
        ]

        # Get recent categories (last 5 created)
        recent_categories_query = Category_db.objects(owner=current_user.id).order_by('-created_at')
        recent_categories = []
        for category in recent_categories_query[:5]:
            category_dict = category.to_mongo().to_dict()
            # Count subjects in this category
            subjects_count = Subject_db.objects(owner=current_user.id, category=category.name).count()
            recent_categories.append({
                "id": category_dict["id"],
                "name": category_dict["name"],
                "subjects_count": subjects_count,
                "created_at": category_dict.get("created_at").isoformat() if category_dict.get("created_at") else None
            })

        # Get available templates (predefined + recent custom templates)
        
        # Get predefined templates
        predefined_templates = []
        for template_name, template_data in TEMPLATES.items():
            predefined_templates.append({
                "name": template_name,
                "type": "predefined",
                "category": template_data.get("category", "General"),
                "description": f"Default {template_name} template"
            })
        
        # Get recent custom templates (last 3)
        custom_templates_query = CustomTemplate_db.objects(owner=current_user.id).order_by('-created_at')
        custom_templates = []
        for template in custom_templates_query[:3]:
            template_dict = template.to_mongo().to_dict()
            custom_templates.append({
                "id": template_dict["id"],
                "name": template_dict["name"],
                "type": "custom",
                "category": template_dict.get("category", "Uncategorized"),
                "description": template_dict.get("description", ""),
                "created_at": template_dict.get("created_at").isoformat() if template_dict.get("created_at") else None
            })

        # Get user statistics
        total_subjects = Subject_db.objects(owner=current_user.id).count()
        total_categories = Category_db.objects(owner=current_user.id).count()
        total_connections = Connection_db.objects(owner=current_user.id).count()

        # Get finance tracker full data from default subjects
        finance_tracker_data = None
        try:
            # Get the finance tracker ID from user's default subjects map
            default_subjects = current_user.default_subjects or {}
            finance_tracker_id = default_subjects["financial_tracker"] if "financial_tracker" in default_subjects else None
            
            if finance_tracker_id:
                # Fetch the finance tracker subject
                finance_subject_db = Subject_db.objects(id=finance_tracker_id, owner=current_user.id).first()
                if finance_subject_db:
                    from models import Subject
                    finance_subject = Subject.from_db(finance_subject_db)
                    finance_tracker_data = await finance_subject.get_full_data()
        except Exception as finance_error:
            print(f"Warning: Could not load finance tracker data: {finance_error}")
            finance_tracker_data = None

        return {
            "date": today,
            "user_stats": {
                "total_subjects": total_subjects,
                "total_categories": total_categories,
                "total_connections": total_connections
            },
            "habits": {
                "total_habits": habits_status["total_habits"],
                "done_today": len(habits_status["done_habits"]),
                "not_done_today": len(habits_status["not_done_habits"]),
                "completion_rate": round(habits_completion_rate, 2),
                "done_habits": habits_status["done_habits"][:5],  # Top 5 completed habits
                "not_done_habits": habits_status["not_done_habits"][:5],  # Top 5 pending habits
                "detailed_progress": all_habits_progress  # Complete progress for all tracked habits
            },
            "connections": {
                "total_today": len(connections_data),
                "connections": connections_data
            },
            "most_visited_subjects": most_visited_subjects,
            "recent_categories": recent_categories,
            "templates": {
                "predefined": predefined_templates[:5],  # Top 5 predefined
                "custom": custom_templates
            },
            "finance_tracker": finance_tracker_data
        }


    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


