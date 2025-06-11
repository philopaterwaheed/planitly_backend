from typing import Optional, Dict, List
from firebase_admin import messaging
from jose import jwt, JWTError, ExpiredSignatureError
from mongoengine.errors import ValidationError, NotUniqueError
from mongoengine import Document, StringField, DateTimeField
from datetime import datetime
from models import User


class FCMToken_db(Document):
    """Model for storing Firebase Cloud Messaging tokens"""
    user_id = StringField(required=True, index=True)  # User ID this token belongs to
    device_id = StringField(required=True)            # Device identifier
    token = StringField(required=True)                # FCM token
    created_at = DateTimeField(default=datetime.utcnow)  # When the token was created
    updated_at = DateTimeField(default=datetime.utcnow)  # When token was last updated

    meta = {
        'collection': 'fcm_tokens',
        'indexes': [
            {'fields': ['user_id', 'device_id'], 'unique': True},
            {'fields': ['token']},
            {'fields': ['user_id']}  # Add index for quick lookup by token
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
    async def remove_token(user_id: str, device_id: str) -> tuple[bool, Optional[str]]:
        """Remove an FCM token for a user and device"""
        try:
            FCMToken_db.objects(user_id=user_id, device_id=device_id).delete()
            return True, None
        except Exception as e:
            return False, f"Error removing FCM token: {str(e)}"

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
    async def send_notification(user_id: str, title: str, body: str, data: Optional[Dict] = None, save_to_db: bool = True) -> Dict:
        """Send notification to all user devices and optionally save to database"""
        try:
            # Save notification to database if requested
            db_result = None
            if save_to_db:
                from .notifications import Notification
                db_result = Notification.create_notification(user_id, title, body)
                if not db_result["success"]:
                    print(f"Warning: Failed to save notification to database: {db_result['error']}")

            # Get all tokens for the user
            tokens_data = await FCMManager.get_user_tokens(user_id)
            if not tokens_data:
                return {
                    "success": 0, 
                    "failure": 0, 
                    "message": "No tokens found",
                    "db_notification": db_result
                }

            success_count = 0
            failure_count = 0
            failed_tokens = []

            # Add notification ID to data if saved to database
            if db_result and db_result["success"]:
                if data is None:
                    data = {}
                data["notification_id"] = db_result["notification"]["id"]

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
                    failed_tokens.append(token_data["device_id"])
                    if isinstance(e.cause, messaging.UnregisteredError):
                        # Token is no longer valid, remove it
                        await FCMManager.remove_token(user_id, token_data["device_id"])

            return {
                "success": success_count,
                "failure": failure_count,
                "message": "Notifications sent",
                "failed_tokens": failed_tokens,
                "db_notification": db_result
            }
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return {
                "success": 0, 
                "failure": 0, 
                "message": f"Error: {str(e)}",
                "db_notification": None
            }

    @staticmethod
    async def send_login_notification(user: User, device_id: str, location: Optional[str] = None) -> Dict:
        """Send login notification to all other devices"""
        try:
            if not user:
                return {"success": 0, "failure": 0, "message": "User not found"}

            # Prepare notification content
            device_info = location or "Unknown location"
            title = "New Login Detected"
            body = f"Your account was just accessed from {device_info}"
            data = {
                "type": "login_notification",
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "location": device_info
            }

            # Get all tokens except the current device
            tokens_data = await FCMManager.get_user_tokens(str(user.id))
            other_devices = [t for t in tokens_data if t["device_id"] != device_id]

            if not other_devices:
                return {"success": 0, "failure": 0, "message": "No other devices to notify"}

            success_count = 0
            failure_count = 0
            failed_tokens = []

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
                    failed_tokens.append(token_data["device_id"])
                    if isinstance(e.cause, messaging.UnregisteredError):
                        # Token is no longer valid, remove it
                        await FCMManager.remove_token(str(user.id), token_data["device_id"])

            return {
                "success": success_count,
                "failure": failure_count,
                "message": "Login notifications sent",
                "failed_tokens": failed_tokens
            }

        except Exception as e:
            print(f"Error sending login notification: {str(e)}")
            return {"success": 0, "failure": 0, "message": f"Error: {str(e)}"}

    @staticmethod
    async def send_password_change_notification(user_id: str, current_device_id: str) -> Dict:
        """Send password change notification to all devices"""
        try:
            title = "Password Changed"
            body = "Your password was changed. All other devices have been logged out for security."
            data = {
                "type": "password_change",
                "action": "logout",
                "timestamp": datetime.utcnow().isoformat()
            }

            # Send to all devices (they will be logged out after this)
            return await FCMManager.send_notification(
                user_id=user_id,
                title=title,
                body=body,
                data=data,
                save_to_db=True
            )

        except Exception as e:
            print(f"Error sending password change notification: {str(e)}")
            return {"success": 0, "failure": 0, "message": f"Error: {str(e)}"}
