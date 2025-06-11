from mongoengine import Document, StringField, BooleanField, DateTimeField
from datetime import datetime
from firebase_admin import messaging


class NotificationCount(Document):
    user_id = StringField(required=True)
    count = StringField(default='0')
    meta = {'collection': 'notification_counts'}


class Notification_db(Document):
    # ID of the user receiving the notification
    user_id = StringField(required=True)
    title = StringField(required=True)  # Title of the notification
    message = StringField(required=True)  # Notification message
    # Whether the notification has been read
    is_read = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)  # Timestamp of creation
    meta = {'collection': 'notifications'}

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat()
        }


class Notification:
    @staticmethod
    def create_notification(user_id: str, title: str, message: str) -> dict:
        """Create a notification in the database and update the count"""
        try:
            # Create notification
            notification = Notification_db(
                user_id=user_id,
                title=title,
                message=message
            )
            notification.save()
            
            # Update notification count
            count_obj = NotificationCount.objects(user_id=user_id).first()
            if not count_obj:
                count_obj = NotificationCount(user_id=user_id, count="1")
            else:
                count_obj.count = str(int(count_obj.count) + 1)
            count_obj.save()
            
            return {
                "success": True,
                "notification": notification.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create notification: {str(e)}"
            }
