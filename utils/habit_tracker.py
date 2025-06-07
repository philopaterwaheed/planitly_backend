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
        """Update habit tracker when the day changes."""
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
        
        # Reset daily status for all habits
        from models.arrayItem import Arrays
        
        # Get all habit IDs
        habits_result = Arrays.get_array_by_name(
            user_id=user_id,
            host_id=habit_tracker.id,
            array_name="habits",
            host_type="subject"
        )
        
        if habits_result["success"]:
            habit_ids = [item["value"] for item in habits_result["array"]]
            
            # Clear existing daily status
            Arrays.clear_array(
                user_id=user_id,
                host_id=habit_tracker.id,
                array_name="daily_status",
                host_type="subject"
            )
            
            # Add new daily status entries (all false initially)
            for habit_id in habit_ids:
                Arrays.append_to_array(
                    user_id=user_id,
                    host_id=habit_tracker.id,
                    value={"key": habit_id, "value": False},
                    host_type="subject",
                    array_name="daily_status"
                )

    @staticmethod
    async def mark_habit_done(user_id: str, habit_id: str, is_done: bool):
        """Mark a habit as done/undone for today."""
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
        
        # Update the specific habit status
        daily_status_result = Arrays.get_array_by_name(
            user_id=user_id,
            host_id=habit_tracker.id,
            array_name="daily_status",
            host_type="subject"
        )
        
        if daily_status_result["success"]:
            for i, item in enumerate(daily_status_result["array"]):
                if item["value"]["key"] == habit_id:
                    # Update the status
                    Arrays.update_at_index(
                        user_id=user_id,
                        host_id=habit_tracker.id,
                        index=i,
                        value={"key": habit_id, "value": is_done},
                        host_type="subject",
                        array_name="daily_status"
                    )
                    return True
            
            # If habit not found in daily status, add it
            Arrays.append_to_array(
                user_id=user_id,
                host_id=habit_tracker.id,
                value={"key": habit_id, "value": is_done},
                host_type="subject",
                array_name="daily_status"
            )
            return True
        
        return False

    @staticmethod
    async def get_daily_habits_status(user_id: str, target_date: str = None):
        """Get all habits status for a specific date."""
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
        
        # Get habits and their status
        habits_result = Arrays.get_array_by_name(
            user_id=user_id,
            host_id=habit_tracker.id,
            array_name="habits",
            host_type="subject"
        )
        
        daily_status_result = Arrays.get_array_by_name(
            user_id=user_id,
            host_id=habit_tracker.id,
            array_name="daily_status",
            host_type="subject"
        )
        
        if not (habits_result["success"] and daily_status_result["success"]):
            return {"done_habits": [], "not_done_habits": [], "total_habits": 0}
        
        # Create status mapping
        status_map = {}
        for item in daily_status_result["array"]:
            status_map[item["value"]["key"]] = item["value"]["value"]
        
        # Get habit details and categorize
        done_habits = []
        not_done_habits = []
        
        for item in habits_result["array"]:
            habit_id = item["value"]
            is_done = status_map.get(habit_id, False)
            
            # Get habit subject details
            try:
                habit_subject = Subject_db.objects.get(id=habit_id)
                habit_data = {
                    "id": habit_subject.id,
                    "name": habit_subject.name,
                    "category": habit_subject.category or "Uncategorized",
                    "created_at": habit_subject.created_at.isoformat() if habit_subject.created_at else None,
                    "is_done": is_done
                }
                
                if is_done:
                    done_habits.append(habit_data)
                else:
                    not_done_habits.append(habit_data)
            except:
                # Handle case where habit subject no longer exists
                continue
        
        return {
            "done_habits": done_habits,
            "not_done_habits": not_done_habits,
            "total_habits": len(done_habits) + len(not_done_habits)
        }