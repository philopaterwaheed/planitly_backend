from datetime import datetime, timedelta
from mongoengine import Document, StringField, DateTimeField, IntField


class RateLimit(Document):
    key = StringField(required=True, unique=True)  # IP address or user ID
    count = IntField(default=0)
    reset_at = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'rate_limits',
        'indexes': [
            {'fields': ['key']},
            {'fields': ['reset_at'], 'expireAfterSeconds': 0}  # TTL index
        ]
    }
