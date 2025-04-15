from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, IntField, ListField
from werkzeug.security import generate_password_hash, check_password_hash
import datetime


class User(Document):
    id = StringField(primary_key=True, auto_generate=True)
    firebase_uid = StringField(required=True)  # firebase_id
    username = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    email_verified = BooleanField(required=True, default=False)
    password = StringField(required=True)
    admin = BooleanField(default=False, required=False)
    devices = ListField(StringField(), default=[], max_length=5)
    invalid_attempts = IntField(default=0)  # Count of invalid login attempts
    # For tracking reset timing
    last_reset = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'users'}

    def hash_password(self):
        self.password = generate_password_hash(self.password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def add_device(self, device_id):
        """Add a device to user's device list if not at limit"""
        if device_id not in self.devices:
            if len(self.devices) >= 5:  # Maximum 5 devices per user
                return False
            self.devices.append(device_id)
            self.save()
        return True

    def remove_device(self, device_id):
        """Remove a device from user's device list"""
        if device_id in self.devices:
            self.devices.remove(device_id)
            self.save()
            return True
        return False

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
