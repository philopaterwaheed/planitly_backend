from mongoengine import Document, StringField, BooleanField, DateTimeField
from datetime import datetime
from firebase_admin import messaging


class NotificationCount(Document):
    user_id = StringField(required=True)
    count = StringField(default='0')
    meta = {'collection': 'notification_counts'
            }


class Notification_db(Document):
    # ID of the user receiving the notification
    user_id = StringField(required=True)
    title = StringField(required=True)  # Title of the notification
    message = StringField(required=True)  # Notification message
    # Whether the notification has been read
    is_read = BooleanField(default=False)
    created_at = DateTimeField(
        default=datetime.utcnow)  # Timestamp of creation
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

    @staticmethod
    def push_notification(self, user_id: str, title: str, message: str) -> dict:
        try:
            notification = Notification_db(
                user_id=user_id,
                title=title,
                message=message
            )
            notification.save()
            return notification.to_dict()
        except Exception as e:
            raise Exception(f"Failed to push notification: {str(e)}")
