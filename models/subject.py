from .component import Component_db, Component, PREDEFINED_COMPONENT_TYPES
import uuid
from mongoengine import Document, StringField, DictField, ReferenceField, ListField, NULLIFY
from mongoengine.errors import DoesNotExist
from .templets import TEMPLATES


# use the Subject_db class to interact with the database directly without the helper
class Subject_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    components = ListField(ReferenceField(
        Component_db,  reverse_delete_rule=NULLIFY))
    owner = StringField(required=True)  # Store user ID
    # if the user will choose to create acording to a template
    template = StringField(Nulable=True)
    meta = {'collection': 'subjects'}


# Subject class helper to interact with the database
class Subject:
    def __init__(self, name, owner, template="", components=None, id=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.owner = owner
        self.template = template
        self.components = components or []

    async def add_component(self, component_name,  component_type, data=None):
        if component_type in PREDEFINED_COMPONENT_TYPES:
            component = Component(name=component_name,
                                  host_subject=self.id,
                                  owner=self.owner,
                                  comp_type=component_type, data=data)
            component.host_subject = self.id
            component.save_to_db()
            # add a reference to the component in the subject if saved
            self.components.append(component.id)
            self.save_to_db()
        else:
            print(f"Component type '{component_type}' is not defined.")
        return component

    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "components": self.components
        }

    async def apply_template(self, template):
        self.template = template
        for comp in TEMPLATES[template]["components"]:
            await self.add_component(comp["name"], comp["type"], comp["data"])

    @staticmethod
    def from_json(data):
        subject = Subject(name=data["name"], owner=data["owner"],
                          template=data["template"],  id=data["id"])
        for comp_id in data["components"]:
            subject.components.append(comp_id)
        return subject

    # save the subject to the database
    def save_to_db(self):
        subject_db = Subject_db(
            id=self.id,
            name=self.name,
            owner=self.owner,
            template=self.template,
            components=self.components
        )
        subject_db.save()

    @staticmethod
    def load_from_db(id):
        try:
            subject_db = Subject_db.objects(id=id).first()
            if subject_db:
                subject = Subject(
                    id=subject_db.id,
                    name=subject_db.name,
                    owner=subject_db.owner,
                    template=subject_db.template,
                    components=[
                        component.id for component in subject_db.components]
                )
                return subject
            else:
                print(f"Subject with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Subject with ID {id} does not exist.")
            return None
