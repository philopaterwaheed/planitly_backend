from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, IntField, ListField , DictField
from .tokens import RefreshToken
from .devices import Device_db
import datetime
import re


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
    phone_number = DictField(default=lambda: {"country_code": "", "number": ""})
    birthday = DateTimeField(required=True)
    profile_image = StringField(required=False)  # Cloudinary URL for profile image
    default_subjects = DictField(default={})
    settings = DictField(default=lambda: {"ai_accessible": []})

    meta = {'collection': 'users'}

    @staticmethod
    def validate_phone_number(phone_data):
        """Validate phone number dictionary structure and content"""
        if not isinstance(phone_data, dict):
            raise ValueError("Phone number must be a dictionary")
        
        # Only allow specific keys
        allowed_keys = {"country_code", "number"}
        if not set(phone_data.keys()).issubset(allowed_keys):
            raise ValueError(f"Phone number can only contain keys: {allowed_keys}")
        
        country_code = phone_data.get("country_code", "")
        number = phone_data.get("number", "")
        
        # Validate country code
        if country_code and not re.match(r"^\+?[1-9]\d{0,3}$", country_code):
            raise ValueError("Invalid country code format. Must be 1-4 digits, optionally starting with +")
        
        # Validate phone number
        if number and not re.match(r"^[0-9]{4,14}$", number):
            raise ValueError("Invalid phone number format. Must be 4-14 digits")
        
        # Validate total length
        full_number = f"{country_code.replace('+', '')}{number}"
        if full_number and (len(full_number) < 5 or len(full_number) > 15):
            raise ValueError("Complete phone number must be between 5-15 digits")
        
        return True

    def set_phone_number(self, phone_data):
        """Set phone number with validation"""
        if phone_data is None:
            self.phone_number = {"country_code": "", "number": ""}
            return
            
        self.validate_phone_number(phone_data)
        
        # Clean and format the data
        cleaned_data = {
            "country_code": phone_data.get("country_code", "").strip(),
            "number": phone_data.get("number", "").strip()
        }
        
        self.phone_number = cleaned_data

    def get_full_phone_number(self):
        """Get the complete phone number as a dictionary with formatted versions"""
        if not self.phone_number or not self.phone_number.get("number"):
            return {
                "country_code": "",
                "number": "",
                "formatted": "",
                "international": ""
            }
        
        country_code = self.phone_number.get("country_code", "")
        number = self.phone_number.get("number", "")
        
        # Create formatted versions
        formatted_local = number
        formatted_international = ""
        
        if country_code:
            # Ensure country code starts with +
            if not country_code.startswith("+"):
                country_code_formatted = f"+{country_code}"
            else:
                country_code_formatted = country_code
            
            formatted_international = f"{country_code_formatted}{number}"
            formatted_local = f"{country_code_formatted} {number}"
        else:
            formatted_international = number
        
        return {
            "country_code": country_code,
            "number": number,
            "formatted": formatted_local,
            "international": formatted_international
        }

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
