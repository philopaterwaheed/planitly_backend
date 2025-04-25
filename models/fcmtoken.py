from typing import Optional, Dict, List
from firebase_admin import messaging
from jose import jwt, JWTError, ExpiredSignatureError
from mongoengine.errors import ValidationError, NotUniqueError
from mongoengine import Document, StringField, DateTimeField
from datetime import datetime
from models import User


class FCMToken_db(Document):
    """Model for storing Firebase Cloud Messaging tokens"""
    user_id = StringField(
        required=True, index=True)  # User ID this token belongs to
    device_id = StringField(required=True)            # Device identifier
    token = StringField(required=True)                # FCM token
    # When the token was created
    created_at = DateTimeField(default=datetime.utcnow)
    # When token was last updated
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'fcm_tokens',
        'indexes': [
            {'fields': ['user_id', 'device_id'], 'unique': True},
            {'fields': ['token']},
            # Add index for quick lookup by token
            {'fields': ['user_id']}
        ]
    }


class FCMManager:
    """Manage Firebase Cloud Messaging tokens for users"""

    @staticmethod
    async def register_token(user_id: str, device_id: str, fcm_token: str) -> bool:
        """Register an FCM token for a user and device"""
        try:
            # Check if token already exists for this device
            existing_token = FCMToken_db.objects(
                user_id=user_id,
                device_id=device_id
            ).first()

            if existing_token:
                # Update the token if it changed
                if existing_token.token != fcm_token:
                    existing_token.token = fcm_token
                    existing_token.updated_at = datetime.utcnow()
                    existing_token.save()
                return True

            # Create new token
            token = FCMToken_db(
                user_id=user_id,
                device_id=device_id,
                token=fcm_token
            )
            token.save()
            return True
        except (ValidationError, NotUniqueError) as e:
            print(f"Error registering FCM token: {str(e)}")
            return False

    @staticmethod
    async def remove_token(user_id: str, device_id: str) -> bool:
        """Remove an FCM token for a user and device"""
        try:
            FCMToken_db.objects(user_id=user_id, device_id=device_id).delete()
            return True, None
        except Exception as e:
            return False, (f"Error removing FCM token: {str(e)}")

    @staticmethod
    async def remove_all_tokens(user_id: str, except_device_id: Optional[str] = None) -> bool:
        """Remove all FCM tokens for a user except for the specified device"""
        try:
            if except_device_id:
                FCMToken_db.objects(
                    user_id=user_id, device_id__ne=except_device_id).delete()
            else:
                FCMToken_db.objects(user_id=user_id).delete()
            return True
        except Exception as e:
            print(f"Error removing FCM tokens: {str(e)}")
            return False

    @staticmethod
    async def get_user_tokens(user_id: str) -> List[Dict]:
        """Get all FCM tokens for a user"""
        try:
            tokens = FCMToken_db.objects(user_id=user_id)
            return [{"device_id": token.device_id, "token": token.token} for token in tokens]
        except Exception as e:
            print(f"Error retrieving FCM tokens: {str(e)}")
            return []

    @staticmethod
    async def send_notification(user_id: str, title: str, body: str, data: Optional[Dict] = None) -> Dict:
        """Send notification to all user devices, one message per token"""
        try:
            # Get all tokens for the user
            tokens_data = await FCMManager.get_user_tokens(user_id)
            if not tokens_data:
                return {"success": 0, "failure": 0, "message": "No tokens found"}

            success_count = 0
            failure_count = 0

            for token_data in tokens_data:
                token = token_data["token"]

                # Create message for each token
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body
                    ),
                    data=data or {},
                    token=token
                )

                # Send the message
                try:
                    messaging.send(message)
                    success_count += 1
                except messaging.FirebaseError as e:
                    failure_count += 1
                    if isinstance(e.cause, messaging.UnregisteredError):
                        # Token is no longer valid, remove it
                        await FCMManager.remove_token(user_id, token_data["device_id"])

            return {
                "success": success_count,
                "failure": failure_count,
                "message": "Notifications sent"
            }
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return {"success": 0, "failure": 0, "message": f"Error: {str(e)}"}

    @staticmethod
    async def send_login_notification(user: User, device_id: str, location: Optional[str] = None) -> Dict:
        """Send login notification to all other devices, one message per token"""
        try:
            # Get user
            # todo insted of search pass the user from login
            if not user:
                return {"success": 0, "failure": 0, "message": "User not found"}

            # Prepare notification content
            device_info = location or "Unknown location"
            title = "New Login Detected"
            body = f"Your account was just accessed from a {device_info}"
            data = {
                "type": "login_notification",
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Get all tokens except the current device
            tokens_data = await FCMManager.get_user_tokens(user.id)
            other_devices = [
                t for t in tokens_data if t["device_id"] != device_id]

            if not other_devices:
                return {"success": 0, "failure": 0, "message": "No other devices to notify"}

            success_count = 0
            failure_count = 0

            for token_data in other_devices:
                token = token_data["token"]

                # Create message for each token
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body
                    ),
                    data=data,
                    token=token
                )

                # Send the message
                try:
                    messaging.send(message)
                    success_count += 1
                except messaging.FirebaseError as e:
                    failure_count += 1
                    if isinstance(e.cause, messaging.UnregisteredError):
                        # Token is no longer valid, remove it
                        await FCMManager.remove_token(user.id, token_data["device_id"])

            return {
                "success": success_count,
                "failure": failure_count,
                "message": "Login notifications sent"
            }

        except Exception as e:
            print(f"Error sending login notification: {str(e)}")
            return {"success": 0, "failure": 0, "message": f"Error: {str(e)}"}
