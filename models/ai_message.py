from mongoengine import Document, StringField, DateTimeField
import datetime

class AIMessage_db(Document):
    user_message = StringField(required=True)
    ai_response = StringField(required=True)
    user_id = StringField(required=True)
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    meta = {
        'collection': 'ai_messages',
        'indexes': [
            {'fields': ['created_at'], 'expireAfterSeconds': 60 * 60 * 24 * 7},  # 7 days
            {'fields': ['user_id']}, 
        ]
    }