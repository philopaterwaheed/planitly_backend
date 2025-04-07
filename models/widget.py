import uuid
from mongoengine import Document, StringField, DictField, ReferenceField, NULLIFY
from mongoengine.errors import DoesNotExist
from .component import Component_db
from .subject import Subject_db


class Widget_db(Document):
    id = StringField(primary_key=True)
    type = StringField(required=True)
    host_subject = ReferenceField(Subject_db, reverse_delete_rule=NULLIFY, required=True)
    data = DictField(null=True)
    reference_component = ReferenceField(Component_db, reverse_delete_rule=NULLIFY)
    owner = StringField(required=True)
    meta = {'collection': 'widgets'}


class Widget:
    def __init__(self, id=None, type=None, host_subject=None, data=None, reference_component=None, owner=None):
        self.id = id or str(uuid.uuid4())
        self.type = type
        self.host_subject = host_subject
        self.data = data
        self.reference_component = reference_component
        self.owner = owner

    def to_json(self):
        return {
            "id": self.id,
            "type": self.type,
            "host_subject": self.host_subject,
            "data": self.data,
            "reference_component": self.reference_component,
            "owner" : self.owner,
        }

    @staticmethod
    def from_json(data):
        widget = Widget(
            id=data["id"],
            type=data["type"],
            host_subject=data["host_subject"],
            data=data.get("data"),
            reference_component=data.get("reference_component"),
            owner = data.get("owner")
        )
        return widget

    def save_to_db(self):
        widget_db = Widget_db(
            id=self.id,
            type=self.type,
            host_subject=Subject_db.objects(id=self.host_subject).first() if self.host_subject else None,
            data=self.data,
            reference_component=Component_db.objects(id=self.reference_component).first() if self.reference_component else None,
            owner=self.owner
        )
        widget_db.save()

    @staticmethod
    def load_from_db(id):
        try:
            widget_db = Widget_db.objects(id=id).first()
            if widget_db:
                widget = Widget(
                    id=widget_db.id,
                    type=widget_db.type,
                    host_subject=widget_db.host_subject.id if widget_db.host_subject else None,
                    data=widget_db.data,
                    reference_component=widget_db.reference_component.id if widget_db.reference_component else None,
                    owner=widget_db.owner
                )
                return widget
            else:
                print(f"Widget with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Widget with ID {id} does not exist.")
            return None
