# models/widget.py
import uuid
from datetime import datetime
from mongoengine import Document, StringField, DictField, ReferenceField, NULLIFY, DateTimeField
from mongoengine.errors import DoesNotExist, ValidationError
from .component import Component_db


class Widget_db(Document):
    id = StringField(primary_key=True)
    type = StringField(required=True)
    host_subject = ReferenceField(
        "Subject_db", required=True)
    data = DictField(null=True)
    reference_component = ReferenceField(
        Component_db, reverse_delete_rule=NULLIFY)
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
            "owner": self.owner,
        }

    @staticmethod
    def from_json(data):
        widget = Widget(
            id=data["id"],
            type=data["type"],
            host_subject=data["host_subject"],
            data=data.get("data"),
            reference_component=data.get("reference_component"),
            owner=data.get("owner")
        )
        return widget

    def save_to_db(self):
        widget_db = Widget_db(
            id=self.id,
            type=self.type,
            host_subject=self.host_subject,
            data=self.data,
            reference_component=self.reference_component,
            owner=self.owner
        )
        widget_db.save()
        return widget_db

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

    @staticmethod
    def validate_widget_type(widget_type, reference_component=None, data=None):
        """Validates widget type and ensures correct data structure based on type"""
        # todo : add more types
        valid_self_hosted_types = ["daily_todo", "table", "text_field"]
        valid_component_ref_types = ["check_box", "chart", "text_field"]

        if widget_type in valid_self_hosted_types:
            if widget_type == "daily_todo":
                # For daily_todo, we now just need a selected_date in the data
                if not data or not isinstance(data, dict):
                    data = {}
                if "selected_date" not in data:
                    data["selected_date"] = datetime.utcnow().strftime("%Y-%m-%d")

            elif widget_type == "table":
                # Validate table structure
                if not data or not isinstance(data, dict):
                    raise ValidationError("Table widget requires data object")
                if "columns" not in data:
                    raise ValidationError(
                        "Table widget requires columns definition")
                if "rows" not in data:
                    data["rows"] = []

            elif widget_type == "text_field":
                # Initialize text field structure
                if not data or not isinstance(data, dict):
                    data = {}
                if "content" not in data:
                    data["content"] = ""
                # Optional fields with defaults
                if "title" not in data:
                    data["title"] = ""
                if "format" not in data:
                    data["format"] = "plain"  # Options: plain, markdown, html
                if "editable" not in data:
                    data["editable"] = True

            return data

        elif widget_type in valid_component_ref_types:
            if not reference_component:
                raise ValidationError(
                    f"Widget type {widget_type} requires a reference component")

            # For text_field as component reference, ensure basic structure
            if widget_type == "text_field":
                if not data or not isinstance(data, dict):
                    data = {}
                # These are widget-specific settings, separate from component data
                if "format" not in data:
                    data["format"] = "plain"
                if "editable" not in data:
                    # Default to false for component references
                    data["editable"] = False

            # Component type validation will happen in the router
            return data

        else:
            raise ValidationError(f"Invalid widget type: {widget_type}")
