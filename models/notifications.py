from mongoengine import Document, StringField, BooleanField, DateTimeField
from datetime import datetime

class Notification_DB(Document):
    user_id = StringField(required=True)  # ID of the user receiving the notification
    title = StringField(required=True)  # Title of the notification
    message = StringField(required=True)  # Notification message
    is_read = BooleanField(default=False)  # Whether the notification has been read
    created_at = DateTimeField(default=datetime.utcnow)  # Timestamp of creation

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
    def push_notification(user_id: str, title: str, message: str) -> dict:
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message
            )
            notification.save()
            return notification.to_dict()
        except Exception as e:
            raise Exception(f"Failed to push notification: {str(e)}")