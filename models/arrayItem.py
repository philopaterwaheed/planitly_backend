from mongoengine import Document, StringField, ReferenceField, NULLIFY
import uuid

class ArrayItem_db(Document):
    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    component = ReferenceField("Component_db", reverse_delete_rule=NULLIFY, required=True)
    value = StringField(required=True)  # Store the value of the array item
    meta = {'collection': 'array_items'}