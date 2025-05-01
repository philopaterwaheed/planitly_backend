from mongoengine import Document, StringField, ReferenceField
from .user import User


class Category_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True, unique_with="owner")  # Unique per user
    owner = ReferenceField(User, required=True)  # Reference to the user who owns the category

    meta = {'collection': 'categories'}

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "owner": str(self.owner.id),
        }