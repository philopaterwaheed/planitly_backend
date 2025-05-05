from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, IntField, ListField , DictField
from .tokens import RefreshToken
from .devices import Device_db
import datetime


class User(Document):
    id = StringField(primary_key=True, auto_generate=True)
    firebase_uid = StringField(required=True)  # firebase_id
    username = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    email_verified = BooleanField(required=True, default=False)
    admin = BooleanField(default=False, required=False)
    devices = ListField(StringField(), default=[], max_length=5)
    invalid_attempts = IntField(default=0)  # Count of invalid login attempts
    last_reset = DateTimeField(default=datetime.datetime.utcnow)  
    firstname = StringField(required=True)
    lastname = StringField(required=True)
    phone_number = StringField(required=True)
    birthday = DateTimeField(required=True)
    default_subjects = ListField(DictField())

    meta = {'collection': 'users'}

    def add_device(self, device_id):
        """Add a device to user's device list if not at limit"""
        if device_id not in self.devices:
            if len(self.devices) >= 5:  # Maximum 5 devices per user
                return False
            self.devices.append(device_id)
            self.save()
        return True

    async def remove_device(self, device_id):
        """Remove a device from user's device list"""
        if not device_id:
            return False, "Device ID cannot be empty."

        if device_id in self.devices:
            Device_db.objects(device_id=device_id, user_id=str(self.id)).delete()
            self.devices.remove(device_id)
            try:
                RefreshToken.objects(device_id=device_id).delete()
            except Exception as e:
                # Log or handle token deletion failure
                return False, f"Failed to delete refresh token for device {device_id}: {e}"
            self.save()
            return True, None
        else:
            return False, f"Device ID {device_id} not found in user's device list."

    def increment_invalid_attempts(self):
        """Increment the invalid attempts counter"""
        self.invalid_attempts += 1
        self.save()
        return self.invalid_attempts

    def reset_invalid_attempts(self):
        """Reset invalid attempts counter"""
        self.invalid_attempts = 0
        self.last_reset = datetime.datetime.utcnow()
        self.save()
