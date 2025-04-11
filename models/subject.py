from .component import Component_db, Component, PREDEFINED_COMPONENT_TYPES
from .widget import Widget_db, Widget
import uuid
from mongoengine import Document, StringField, DictField, ReferenceField, ListField, BooleanField, NULLIFY
from mongoengine.errors import DoesNotExist, ValidationError
from .templets import TEMPLATES


# use the Subject_db class to interact with the database directly without the helper
class Subject_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    components = ListField(ReferenceField(
        Component_db, reverse_delete_rule=NULLIFY))
    widgets = ListField(ReferenceField(
        Widget_db, reverse_delete_rule=NULLIFY))
    owner = StringField(required=True)  # Store user ID
    template = StringField(required=False)
    is_deletable = BooleanField(default=True)
    meta = {'collection': 'subjects'}


# Subject class helper to interact with the database
class Subject:
    def __init__(self, name, owner, template="", components=None, widgets=None, id=None, is_deletable=True):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.owner = owner
        self.template = template
        self.components = components or []
        self.widgets = widgets or []
        self.is_deletable = is_deletable

    async def add_component(self, component_name, component_type, data=None, is_deletable=True):
        if component_type in PREDEFINED_COMPONENT_TYPES:
            component = Component(name=component_name,
                                  host_subject=self.id,
                                  owner=self.owner,
                                  comp_type=component_type,
                                  data=data,
                                  is_deletable=is_deletable)
            component.host_subject = self.id
            component.save_to_db()
            # add a reference to the component in the subject if saved
            self.components.append(component.id)
            self.save_to_db()
        else:
            print(f"Component type '{component_type}' is not defined.")
        return component

    async def add_widget(self, widget_type, data=None, reference_component=None, is_deletable=True):
        try:
            # Validate widget type and data
            validated_data = Widget.validate_widget_type(
                widget_type, reference_component, data)

            widget = Widget(
                type=widget_type,
                host_subject=self.id,
                data=validated_data,
                reference_component=reference_component,
                owner=self.owner
            )

            widget.save_to_db()
            # Add reference to the widget in the subject
            self.widgets.append(widget.id)
            self.save_to_db()
            return widget
        except ValidationError as e:
            print(f"Widget validation error: {e}")
            return None

    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def get_widget(self, widget_id):
        try:
            return Widget.load_from_db(widget_id)
        except DoesNotExist:
            print(f"Widget with ID {widget_id} not found.")
            return None

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "components": self.components,
            "widgets": self.widgets,
            "is_deletable": self.is_deletable,
            "owner": self.owner,
            "template": self.template
        }

    async def apply_template(self, template):
        self.template = template
        for comp in TEMPLATES[template]["components"]:
            is_comp_deletable = comp.get("is_deletable", True)
            await self.add_component(comp["name"], comp["type"], comp["data"], is_deletable=is_comp_deletable)

        # Add widgets from template if they exist
        if "widgets" in TEMPLATES[template]:
            for widget in TEMPLATES[template]["widgets"]:
                reference_component = widget.get("reference_component", None)
                await self.add_widget(
                    widget["type"],
                    widget.get("data", {}),
                    reference_component,
                    widget.get("is_deletable", True)
                )

    @staticmethod
    def from_json(data):
        subject = Subject(name=data["name"],
                          owner=data["owner"],
                          template=data["template"],
                          id=data["id"],
                          is_deletable=data.get("is_deletable", True))
        for comp_id in data["components"]:
            subject.components.append(comp_id)
        for widget_id in data.get("widgets", []):
            subject.widgets.append(widget_id)
        return subject

    # save the subject to the database
    def save_to_db(self):
        subject_db = Subject_db(
            id=self.id,
            name=self.name,
            owner=self.owner,
            template=self.template,
            components=self.components,
            widgets=self.widgets,
            is_deletable=self.is_deletable
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
                        component.id for component in subject_db.components],
                    widgets=[widget.id for widget in subject_db.widgets],
                    is_deletable=subject_db.is_deletable
                )
                return subject
            else:
                print(f"Subject with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Subject with ID {id} does not exist.")
            return None
