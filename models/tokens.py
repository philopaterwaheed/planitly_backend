from mongoengine import Document, StringField, DateTimeField, BooleanField
from datetime import datetime

class RefreshToken(Document):
    """Model for storing refresh tokens for revocation capability"""
    token_id = StringField(required=True, unique=True)  # Unique identifier for the token
    user_id = StringField(required=True, index=True)    # User ID this token belongs to
    device_id = StringField(required=True)              # Device identifier
    created_at = DateTimeField(default=datetime.utcnow) # When the token was created
    expires_at = DateTimeField(required=True)           # When the token expires
    revoked = BooleanField(default=False)               # Whether the token has been revoked
    
    meta = {
        'collection': 'refresh_tokens',  # Collection name in MongoDB
        'indexes': [
            {'fields': ['user_id', 'device_id']},
            {'fields': ['token_id']},
            # todo worker to delete expired tokens
        ]
    }
