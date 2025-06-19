import datetime
from models import Subject_db

class SubjectVisitManager:
    @staticmethod
    async def apply_visit_decay_to_subjects(user_id, limit_days=7, decay_factor=0.9):
        """
        Apply exponential decay to subject visit counts for subjects that haven't been decayed recently.
        
        Args:
            user_id: The user's ID
            limit_days: Number of days before applying decay (default: 7)
            decay_factor: Decay factor per week (default: 0.9)
            
        Returns:
            Number of subjects that had decay applied
        """
        now = datetime.datetime.utcnow()
        limit_date = now - datetime.timedelta(days=limit_days)
        
        # Database-side decay update using aggregation pipeline
        decay_pipeline = [
            # Match user's subjects that need decay (older than limit_days)
            {
                "$match": {
                    "owner": user_id,
                    "times_visited.last_decay": {"$lt": limit_date}
                }
            },
            # Add calculated fields for decay
            {
                "$addFields": {
                    "days_since_decay": {
                        "$divide": [
                            {"$subtract": [now, "$times_visited.last_decay"]},
                            1000 * 60 * 60 * 24  # Convert milliseconds to days
                        ]
                    }
                }
            },
            {
                "$addFields": {
                    "weeks_since_decay": {
                        "$floor": {"$divide": ["$days_since_decay", limit_days]}
                    }
                }
            },
            # Apply exponential decay
            {
                "$addFields": {
                    "decay_factor": {
                        "$pow": [decay_factor, "$weeks_since_decay"]
                    }
                }
            },
            {
                "$addFields": {
                    "times_visited.count": {
                        "$floor": {
                            "$multiply": ["$times_visited.count", "$decay_factor"]
                        }
                    },
                    "times_visited.last_decay": now
                }
            },
            # Remove temporary fields
            {
                "$unset": ["days_since_decay", "weeks_since_decay", "decay_factor"]
            },
            # Merge back to collection (update in place)
            {
                "$merge": {
                    "into": "subjects",
                    "whenMatched": "replace"
                }
            }
        ]
        
        # Execute decay update
        decay_result = list(Subject_db._get_collection().aggregate(decay_pipeline))
        return len(decay_result) if decay_result else 0

    @staticmethod
    def get_most_visited_subjects(user_id, skip=0, limit=20):
        """
        Get user's most visited subjects ordered by visit count.
        
        Args:
            user_id: The user's ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with total count and subjects data
        """
        query = Subject_db.objects(owner=user_id).order_by('-times_visited.count', '-last_visited')
        total = query.count()
        subjects = query.skip(skip).limit(limit)
        
        # Convert to response format
        subjects_data = []
        for subject_db in subjects:
            subject_dict = subject_db.to_mongo().to_dict()
            # Ensure visit count is properly formatted
            times_visited = subject_dict.get('times_visited', {})
            if isinstance(times_visited, dict):
                subject_dict['times_visited'] = times_visited.get('count', 0)
            else:
                subject_dict['times_visited'] = 0
            subjects_data.append(subject_dict)

        return {
            "total": total,
            "subjects": subjects_data
        }

    @staticmethod
    def format_subject_for_home(subject_dict):
        """
        Format a subject dictionary for home page display.
        
        Args:
            subject_dict: Subject dictionary from MongoDB
            
        Returns:
            Formatted subject dictionary for home page
        """
        times_visited = subject_dict.get('times_visited', {})
        if isinstance(times_visited, dict):
            visit_count = times_visited.get('count', 0)
        else:
            visit_count = 0
        
        return {
            "id": subject_dict["_id"],
            "name": subject_dict["name"],
            "category": subject_dict.get("category", "Uncategorized"),
            "template": subject_dict.get("template"),
            "times_visited": visit_count,
            "last_visited": subject_dict.get("last_visited").isoformat() if subject_dict.get("last_visited") else None
        }