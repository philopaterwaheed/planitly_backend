from mongoengine import Document, StringField, DictField, ReferenceField
import uuid

# Predefined data and widget types
PREDEFINED_COMPONENT_TYPES = {
    "int": 0,
    "str": "",
    "bool": True,
    "Array_type": {"items": [], "type": ""},
    "Array_generic": {"items": []},
    "GraphWidget": {"type": "graph", "data": []},
}


class Component_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    host_subject = ReferenceField("Subject_db", required=True)
    data = DictField()
    comp_type = StringField(required=True)
    owner = StringField(required=True)  # Store user ID
    meta = {'collection': 'components'}


class Component:
    def __init__(self, name, comp_type, data=None, id=None, host_subject=None, owner=None):
        self.name = name
        self.comp_type = comp_type
        self.data = data or PREDEFINED_COMPONENT_TYPES.get(name, {})
        self.id = id or str(uuid.uuid4())
        self.host_subject = host_subject
        self.owner = owner

    def is_widget(self):
        """Check if the component is a widget based on predefined types."""
        return isinstance(self.data, dict) and "type" in self.data

    def to_json(self):
        return {
            "name": self.name,
            "id": self.id,
            "type": self.comp_type,
            "data": self.data,
            "host_subject": self.host_subject,
            "owner": self.owner
        }

    @staticmethod
    def from_json(data):
        return Component(
            name=data["name"],
            data=data["data"],
            id=data["id"],
            comp_type=data["type"],
            host_subject=data["host_subject"],
            owner=data.get("owner")
        )

    def save_to_db(self):
        component_db = Component_db(
            id=self.id,
            name=self.name,
            host_subject=self.host_subject,
            data=self.data,
            comp_type=self.comp_type,
            owner=self.owner
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
        if not (self.comp_type.startswith("Array") and isinstance(value, list)) or (self.comp_type not in ["Array_type", "Array_generic"]):
            print(value)
            self.data["item"] = value
        else:
            print(value)
            self.data["items"] = value
        self.save_to_db()

    @staticmethod
    def load_from_db(comp_id):
        component_db = Component_db.objects(id=comp_id).first()
        if component_db:
            return Component.from_json({
                "name": component_db.name,
                "id": component_db.id,
                "data": component_db.data,
                "type": component_db.comp_type,
                "host_subject": component_db.host_subject,
                "owner": component_db.owner
            })
        return None
