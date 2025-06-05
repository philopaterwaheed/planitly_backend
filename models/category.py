from mongoengine import Document, StringField, ReferenceField, DateTimeField
from .user import User
from datetime import datetime, timezone


class Category_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True, unique_with="owner")  # Unique per user
    owner = ReferenceField(User, required=True)  # Reference to the user who owns the category
    created_at = DateTimeField(default=datetime.now(timezone.utc))

    meta = {'collection': 'categories'}

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "owner": str(self.owner.id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }