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
            return True
        except Exception as e:
            print(f"Error removing FCM token: {str(e)}")
            return False

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
        """Send notification to all user devices"""
        try:
            # Get all tokens for the user
            tokens_data = await FCMManager.get_user_tokens(user_id)
            if not tokens_data:
                return {"success": 0, "failure": 0, "message": "No tokens found"}

            # Extract just the tokens
            tokens = [t["token"] for t in tokens_data]

            # Create message
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                tokens=tokens
            )

            # Send the message
            response = messaging.send_multicast(message)

            # Process responses and remove invalid tokens
            if response.failure_count > 0:
                for idx, result in enumerate(response.responses):
                    if not result.success:
                        error = result.exception
                        if hasattr(error, 'cause') and isinstance(error.cause, messaging.UnregisteredError):
                            # Token is no longer valid, find and remove it
                            invalid_token = tokens[idx]
                            # Find the device_id for this token
                            token_doc = FCMToken_db.objects(
                                token=invalid_token).first()
                            if token_doc:
                                await FCMManager.remove_token(user_id, token_doc.device_id)

            return {
                "success": response.success_count,
                "failure": response.failure_count,
                "message": "Notification sent"
            }
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return {"success": 0, "failure": 0, "message": f"Error: {str(e)}"}

    @staticmethod
    async def send_login_notification(user_id: str, device_id: str, location: Optional[str] = None) -> bool:
        """Send login notification to all other devices"""
        try:
            # Get user
            user = User.objects(id=user_id).first()
            if not user:
                return False

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
            tokens_data = await FCMManager.get_user_tokens(user_id)
            other_devices = [
                t for t in tokens_data if t["device_id"] != device_id]

            if not other_devices:
                return True  # No other devices to notify

            tokens = [t["token"] for t in other_devices]

            # Create message
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data,
                tokens=tokens
            )

            # Send the message
            response = messaging.send_multicast(message)
            return response.success_count > 0

        except Exception as e:
            print(f"Error sending login notification: {str(e)}")
            return False
