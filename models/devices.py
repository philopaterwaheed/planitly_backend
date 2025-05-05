from mongoengine import Document, StringField, DateTimeField, DictField
from datetime import datetime

class Device_db(Document):
    user_id = StringField(required=True)  # Reference to the user
    device_id = StringField(required=True, unique = True)  # Unique device identifier
    device_name = StringField(required=False)  # Optional device name
    user_agent = StringField(required=False)  # User agent string
    location = DictField(required=False)  # Location data (e.g., {"country": "US", "city": "New York"})
    last_used = DateTimeField(default=datetime.utcnow)  # Last used timestamp

    meta = {'collection': 'devices'}