from mongoengine import Document, StringField, DictField, ReferenceField, ListField, NULLIFY, BooleanField
import uuid
import datetime
from .arrayItem import ArrayItem_db

# Predefined data and widget types
PREDEFINED_COMPONENT_TYPES = {
    "int": {"item": 0},
    "str": {"item": ""},
    "bool": {"item": False},
    "date": {"item": datetime.datetime.now().isoformat()},
    "Array_type": {"items": [], "type": ""},
    "Array_generic": {"items": []},
    "pair": {"key": "", "value": ""},  # New pair type
    "Array_of_pairs": {"items": [], "type": "pair"},  # New array of pairs type
}


class Component_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    host_subject = ReferenceField("Subject_db", required=True)
    data = DictField()
    comp_type = StringField(required=True)
    owner = StringField(required=True)  # Store user ID
    is_deletable = BooleanField(default=True)
    meta = {'collection': 'components'}


class Component:
    def __init__(self, name, comp_type, data=None, id=None, host_subject=None, owner=None, is_deletable=True):
        self.name = name
        self.comp_type = comp_type
        self.data = data or PREDEFINED_COMPONENT_TYPES.get(comp_type, {})
        self.id = id or str(uuid.uuid4())
        self.host_subject = host_subject
        self.owner = owner
        self.is_deletable = is_deletable

    def to_json(self):
        return {
            "name": self.name,
            "id": self.id,
            "comp_type": self.comp_type,
            "data": self.data,
            "host_subject": self.host_subject,
            "owner": self.owner,
            "is_deletable": self.is_deletable
        }

    @staticmethod
    def from_json(data):
        return Component(
            name=data["name"],
            data=data["data"],
            id=data["id"],
            comp_type=data["type"],
            host_subject=data["host_subject"],
            owner=data.get("owner"),
            is_deletable=data.get("is_deletable", True)
        )

    def save_to_db(self):
        component_db = Component_db(
            id=self.id,
            name=self.name,
            host_subject=self.host_subject,
            data=self.data,
            comp_type=self.comp_type,
            owner=self.owner,
            is_deletable=self.is_deletable
        )
        component_db.save()

    @staticmethod
    def alter_search(id, value):
        component_db = Component_db.objects(id=id).first()
        if not (component_db.comp_type.startswith("Array") and isinstance(value, list)) or (component_db.comp_type not in ["Array_type", "Array_generic"]):
            component_db.data["item"] = value
        else:
            component_db.data["items"] = value
        component_db.save()

    def alter_data(self, value):
        if self.comp_type in ["Array_type", "Array_generic"]:
            # Clear existing array items
            ArrayItem_db.objects(component=self.id).delete()
            # Add new array items
            if isinstance(value, list):
                for item in value:
                    ArrayItem_db(component=self.id, value=str(item)).save()
        elif self.comp_type == "pair":
            if isinstance(value, dict) and "key" in value and "value" in value:
                self.data.update(value)
        else:
            self.data["item"] = value
        self.save_to_db()

    def get_array_items(self):
        if self.comp_type in ["Array_type", "Array_generic"]:
            return [item.value for item in ArrayItem_db.objects(component=self.id)]
        return None

    @staticmethod
    def load_from_db(comp_id):
        component_db = Component_db.objects(id=comp_id).first()
        if component_db:
            return Component.from_json({
                "name": component_db.name,
                "id": component_db.id,
                "data": component_db.data,
                "comp_type": component_db.comp_type,
                "host_subject": component_db.host_subject,
                "owner": component_db.owner,
                "is_deletable": component_db.is_deletable
            })
        return None
