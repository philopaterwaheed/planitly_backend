from .component import Component_db, Component, PREDEFINED_COMPONENT_TYPES
import uuid
from mongoengine import Document, StringField, DictField, ReferenceField, ListField, NULLIFY
from mongoengine.errors import DoesNotExist


class Subject_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    components = ListField(ReferenceField(
        Component_db, reverse_delete_rule=NULLIFY))
    owner = StringField(required=True)  # Store user ID
    meta = {'collection': 'subjects'}


class Subject:
    def __init__(self, name, id=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.components = {}

    def add_component(self, component_name,  component_type):
        if component_type in PREDEFINED_COMPONENT_TYPES:
            component = Component(name=component_name,
                                  comp_type=component_type)
            component.host_subject = self.id
            self.components[component.id] = component
            component.save_to_db()
        else:
            print(f"Component type '{component_type}' is not defined.")
        return component

    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "components": list(self.components.keys())
        }

    @staticmethod
    def from_json(data):
        subject = Subject(name=data["name"], id=data["id"])
        for comp_id in data["components"]:
            component = Component.load_from_file(comp_id)
            subject.components[comp_id] = component
        return subject

    def save_to_db(self):
        subject_db = Subject_db(
            id=self.id,
            name=self.name,
            components=[component.id for component in self.components.values()]
        )
        subject_db.save()

    @staticmethod
    def load_from_db(id):
        try:
            subject_db = Subject_db.objects(id=id).first()
            if subject_db:
                subject = Subject.from_json({
                    "id": subject_db.id,
                    "name": subject_db.name,
                    "components": subject_db.components
                })
                return subject
            else:
                print(f"Subject with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Subject with ID {id} does not exist.")
            return None
