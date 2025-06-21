import datetime
from models import Subject_db, Component_db
from models.arrayItem import Arrays

class HabitTrackerManager:
    @staticmethod
    async def get_or_create_habit_tracker(user_id: str):
        """Get or create the habit tracker subject for a user."""
        habit_tracker = Subject_db.objects(
            owner=user_id, 
            template="habit_tracker"
        ).first()
        
        if not habit_tracker:
            # Create habit tracker if it doesn't exist
            from models.subject import Subject
            subject = Subject(
                name="Habit Tracker",
                owner=user_id,
                template="habit_tracker",
                category="system"
            )
            await subject.apply_template("habit_tracker")
            subject.save_to_db()
            habit_tracker = Subject_db.objects(
                owner=user_id, 
                template="habit_tracker"
            ).first()
        
        return habit_tracker

    @staticmethod
    async def update_daily_status_for_new_day(user_id: str, new_date: str):
        """Update habit tracker when the day changes - memory efficient version."""
        habit_tracker = await HabitTrackerManager.get_or_create_habit_tracker(user_id)
        
        # Get current date component
        current_date_comp = None
        daily_status_comp = None
        habits_comp = None
        
        for comp in habit_tracker.components:
            if comp.name == "current_date":
                current_date_comp = comp
            elif comp.name == "daily_status":
                daily_status_comp = comp
            elif comp.name == "habits":
                habits_comp = comp
        
        if not all([current_date_comp, daily_status_comp, habits_comp]):
            raise ValueError("Habit tracker components not found")
        
        # Update current date
        current_date_comp.data["item"] = new_date
        current_date_comp.save()
        
        # Clear existing daily status
        Arrays.clear_array(
            user_id=user_id,
            host_id=habit_tracker.id,
            array_name="daily_status",
            host_type="subject"
        )
        
        await HabitTrackerManager._process_habits_in_batches(
            user_id, habit_tracker.id, 
            lambda habit_id: Arrays.append_to_array(
                user_id=user_id,
                host_id=habit_tracker.id,
                value={"key": habit_id, "value": False},
                host_type="subject",
                array_name="daily_status"
            )
        )

    @staticmethod
    async def _process_habits_in_batches(user_id: str, tracker_id: str, process_func):
        """Process habits in batches without loading all into memory."""
        skip = 0
        limit = 50
        
        while True:
            habits_result = Arrays.get_array_by_name(
                user_id=user_id,
                host_id=tracker_id,
                array_name="habits",
                host_type="subject",
                page=skip,
                page_size=limit
            )
            
            if not habits_result["success"] or not habits_result["array"]:
                break
            
            # Process each habit in the batch
            for item in habits_result["array"]:
                habit_id = item["value"]
                process_func(habit_id)
            
            # If we got less than the limit, we've reached the end
            if len(habits_result["array"]) < limit:
                break
                
            skip += limit

    @staticmethod
    async def _find_habit_in_array(user_id: str, tracker_id: str, array_name: str, habit_id: str):
        """Find a specific habit in an array without loading all elements."""
        skip = 0
        limit = 50
        
        while True:
            result = Arrays.get_array_by_name(
                user_id=user_id,
                host_id=tracker_id,
                array_name=array_name,
                host_type="subject",
                page=skip,
                page_size=limit
            )
            
            if not result["success"] or not result["array"]:
                break
            
            # Search in current batch
            for i, item in enumerate(result["array"]):
                if array_name == "daily_status":
                    if item["value"]["key"] == habit_id:
                        return skip + i, item["value"]
                else:  # habits array
                    if item["value"] == habit_id:
                        return skip + i, item["value"]
            
            # If we got less than the limit, we've reached the end
            if len(result["array"]) < limit:
                break
                
            skip += limit
        
        return None, None

    @staticmethod
    async def _get_habit_completion_percentage(habit_id: str, target_date: str):
        """Calculate completion percentage for a habit based on its daily todos."""
        try:
            habit_subject = Subject_db.objects.get(id=habit_id)
            
            # Find the daily_todo widget
            daily_todo_widget = None
            for widget in habit_subject.widgets:
                if widget.type == "daily_todo":
                    daily_todo_widget = widget
                    break
            
            if not daily_todo_widget:
                # No daily todos, habit is either 0% or 100% based on manual marking
                return None  # Will be handled by caller
            
            # Get todos for the target date
            from models.todos import Todo_db
            target_datetime = datetime.datetime.strptime(target_date, "%Y-%m-%d")
            next_day = target_datetime + datetime.timedelta(days=1)
            
            todos = Todo_db.objects(
                widget_id=daily_todo_widget.id,
                date__gte=target_datetime,
                date__lt=next_day
            )
            
            if not todos:
                return 0.0  # No todos for this date
            
            completed_count = todos.filter(completed=True).count()
            total_count = todos.count()
            completion_percentage = (completed_count / total_count) * 100
            
            return completion_percentage
            
        except Exception as e:
            print(f"Error calculating habit completion for {habit_id}: {e}")
            return 0.0

    @staticmethod
    async def mark_habit_done(user_id: str, habit_id: str, is_done: bool):
        """Mark a habit as done/undone for today - memory efficient version."""
        habit_tracker = await HabitTrackerManager.get_or_create_habit_tracker(user_id)
        
        # Check if we need to update for new day
        current_date_comp = None
        for comp in habit_tracker.components:
            if comp.name == "current_date":
                current_date_comp = comp
                break
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if current_date_comp.data.get("item") != today:
            await HabitTrackerManager.update_daily_status_for_new_day(user_id, today)
        
        # Find the habit in daily status
        index, current_value = await HabitTrackerManager._find_habit_in_array(
            user_id, habit_tracker.id, "daily_status", habit_id
        )
        
        if index is not None:
            # Update existing entry
            Arrays.update_at_index(
                user_id=user_id,
                host_id=habit_tracker.id,
                index=index,
                value={"key": habit_id, "value": is_done},
                host_type="subject",
                array_name="daily_status"
            )
            return True
        else:
            # Add new entry if not found
            Arrays.append_to_array(
                user_id=user_id,
                host_id=habit_tracker.id,
                value={"key": habit_id, "value": is_done},
                host_type="subject",
                array_name="daily_status"
            )
            return True

    @staticmethod
    async def get_daily_habits_status(user_id: str, target_date: str = None):
        """Get all habits status for a specific date - memory efficient version."""
        if not target_date:
            target_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        habit_tracker = await HabitTrackerManager.get_or_create_habit_tracker(user_id)
        
        # Check if we need to update for the target date
        current_date_comp = None
        for comp in habit_tracker.components:
            if comp.name == "current_date":
                current_date_comp = comp
                break
        
        if current_date_comp.data.get("item") != target_date:
            await HabitTrackerManager.update_daily_status_for_new_day(user_id, target_date)
        
        # Build status map from daily_status array
        status_map = {}
        await HabitTrackerManager._build_status_map(user_id, habit_tracker.id, status_map)
        
        # Process habits in batches and categorize
        done_habits = []
        not_done_habits = []
        
        await HabitTrackerManager._process_habits_in_batches(
            user_id, habit_tracker.id,
            lambda habit_id: HabitTrackerManager._process_single_habit(
                habit_id, status_map, target_date, done_habits, not_done_habits
            )
        )
        
        return {
            "done_habits": done_habits,
            "not_done_habits": not_done_habits,
            "total_habits": len(done_habits) + len(not_done_habits)
        }

    @staticmethod
    async def _build_status_map(user_id: str, tracker_id: str, status_map: dict):
        """Build status mapping from daily_status array in batches."""
        skip = 0
        limit = 50
        
        while True:
            status_result = Arrays.get_array_by_name(
                user_id=user_id,
                host_id=tracker_id,
                array_name="daily_status",
                host_type="subject",
                page=skip,
                page_size=limit
            )
            
            if not status_result["success"] or not status_result["array"]:
                break
            
            # Build mapping for current batch
            for item in status_result["array"]:
                value = item["value"]
                status_map[value["key"]] = value["value"]
            
            if len(status_result["array"]) < limit:
                break
                
            skip += limit

    @staticmethod
    async def _process_single_habit(habit_id: str, status_map: dict, target_date: str, done_habits: list, not_done_habits: list):
        """Process a single habit and add to appropriate list."""
        try:
            is_manually_done = status_map.get(habit_id, False)
            
            # Get habit subject details
            habit_subject = Subject_db.objects.get(id=habit_id)
            
            # Calculate completion percentage based on daily todos
            completion_percentage = await HabitTrackerManager._get_habit_completion_percentage(habit_id, target_date)
            
            # Determine if habit is considered "done"
            if completion_percentage is None:
                # No daily todos, use manual marking
                is_done = is_manually_done
                completion_percentage = 100.0 if is_manually_done else 0.0
            else:
                # Has daily todos, consider done if 100% completed or manually marked
                is_done = completion_percentage == 100.0 or is_manually_done
            
            habit_data = {
                "id": habit_subject.id,
                "name": habit_subject.name,
                "category": habit_subject.category or "Uncategorized",
                "created_at": habit_subject.created_at.isoformat() if habit_subject.created_at else None,
                "is_done": is_done,
                "completion_percentage": round(completion_percentage, 1),
                "manually_marked": is_manually_done
            }
            
            if is_done:
                done_habits.append(habit_data)
            else:
                not_done_habits.append(habit_data)
                
        except Exception as e:
            print(f"Error processing habit {habit_id}: {e}")

    @staticmethod
    async def get_habit_detailed_status(user_id: str, habit_id: str, target_date: str):
        """Get detailed status for a specific habit including todos."""
        try:
            habit_subject = Subject_db.objects.get(id=habit_id)
            
            # Get manual marking status efficiently
            habit_tracker = await HabitTrackerManager.get_or_create_habit_tracker(user_id)
            _, status_value = await HabitTrackerManager._find_habit_in_array(
                user_id, habit_tracker.id, "daily_status", habit_id
            )
            
            is_manually_done = status_value["value"] if status_value else False
            
            # Get completion percentage from todos
            completion_percentage = await HabitTrackerManager._get_habit_completion_percentage(habit_id, target_date)
            
            # Find daily todo widget and get todos
            daily_todo_widget = None
            todos_data = []
            
            for widget in habit_subject.widgets:
                if widget.type == "daily_todo":
                    daily_todo_widget = widget
                    break
            
            if daily_todo_widget:
                from models.todos import Todo_db
                target_datetime = datetime.datetime.strptime(target_date, "%Y-%m-%d")
                next_day = target_datetime + datetime.timedelta(days=1)
                
                todos = Todo_db.objects(
                    widget_id=daily_todo_widget.id,
                    date__gte=target_datetime,
                    date__lt=next_day
                ).only('id', 'task', 'completed', 'created_at')  # Only load needed fields
                
                todos_data = [{
                    "id": str(todo.id),
                    "task": todo.task,
                    "completed": todo.completed,
                    "created_at": todo.created_at.isoformat() if todo.created_at else None
                } for todo in todos]
            
            return {
                "habit_id": habit_id,
                "habit_name": habit_subject.name,
                "date": target_date,
                "manually_marked": is_manually_done,
                "completion_percentage": round(completion_percentage, 1) if completion_percentage is not None else (100.0 if is_manually_done else 0.0),
                "has_todos": daily_todo_widget is not None,
                "todos": todos_data,
                "is_done": (completion_percentage == 100.0 if completion_percentage is not None else is_manually_done) or is_manually_done
            }
            
        except Exception as e:
            raise Exception(f"Error getting habit detailed status: {str(e)}")

    @staticmethod
    async def get_habits_count(user_id: str):
        """Get total count of habits without loading them into memory."""
        try:
            habit_tracker = await HabitTrackerManager.get_or_create_habit_tracker(user_id)
            
            # Get count using a single query with limit=1 to check if array exists
            result = Arrays.get_array_by_name(
                user_id=user_id,
                host_id=habit_tracker.id,
                array_name="habits",
                host_type="subject",
                page=0,
                page_size=1
            )
            
            if not result["success"]:
                return 0
            
            # Use the total_count from the result if available, otherwise count manually
            if "total_count" in result:
                return result["total_count"]
            
            # Fallback: count by iterating (but don't load data)
            count = 0
            skip = 0
            limit = 100
            
            while True:
                batch_result = Arrays.get_array_by_name(
                    user_id=user_id,
                    host_id=habit_tracker.id,
                    array_name="habits",
                    host_type="subject",
                    page=skip,
                    page_size=limit
                )
                
                if not batch_result["success"] or not batch_result["array"]:
                    break
                
                count += len(batch_result["array"])
                
                if len(batch_result["array"]) < limit:
                    break
                    
                skip += limit
            
            return count
            
        except Exception as e:
            print(f"Error getting habits count: {e}")
            return 0