# models/widget.py
import uuid
from datetime import datetime
from mongoengine import Document, StringField, DictField, ReferenceField, NULLIFY, DateTimeField , BooleanField
from mongoengine.errors import DoesNotExist, ValidationError
from .component import Component_db


class Widget_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)  
    widget_type = StringField(required=True)
    host_subject = ReferenceField(
        "Subject_db", required=True)
    data = DictField(null=True)
    reference_component = ReferenceField(
        Component_db, reverse_delete_rule=NULLIFY)
    owner = StringField(required=True)
    is_deletable = BooleanField(default="true")
    meta = {'collection': 'widgets'}


class Widget:
    def __init__(self, id=None, name=None, widget_type=None, host_subject=None, data=None, reference_component=None, owner=None, is_deletable=True):
        self.id = id or str(uuid.uuid4())
        self.name = name  # New field
        self.widget_type = widget_type
        self.host_subject = host_subject
        self.data = data
        self.reference_component = reference_component
        self.owner = owner
        self.is_deletable = is_deletable

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,  # Include name in JSON
            "widget_type": self.widget_type,
            "host_subject": self.host_subject,
            "data": self.data,
            "reference_component": self.reference_component,
            "owner": self.owner,
            "is_deletable": self.is_deletable,
        }

    @staticmethod
    def from_json(data):
        widget = Widget(
            id=data["id"],
            name=data["name"],  # Parse name from JSON
            widget_type=data["widget_type"],
            host_subject=data["host_subject"],
            data=data.get("data"),
            reference_component=data.get("reference_component"),
            owner=data.get("owner"),
            is_deletable=data.get("is_deletable", True)
        )
        return widget

    def save_to_db(self):
        widget_db = Widget_db(
            id=self.id,
            name=self.name,  # Save name to database
            widget_type=self.widget_type,
            host_subject=self.host_subject,
            data=self.data,
            reference_component=self.reference_component,
            owner=self.owner,
            is_deletable=self.is_deletable
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
                    name=widget_db.name,  # Load name from database
                    widget_type=widget_db.widget_type,
                    host_subject=widget_db.host_subject.id if widget_db.host_subject else None,
                    data=widget_db.data,
                    reference_component=widget_db.reference_component.id if widget_db.reference_component else None,
                    owner=widget_db.owner,
                    is_deletable=widget_db.is_deletable
                )
                return widget
            else:
                print(f"Widget with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Widget with ID {id} does not exist.")
            return None

    @staticmethod
    def validate_widget_type(widget_type, reference_component : Component_db=None, data=None):
        """Validates widget type and ensures correct data structure based on type"""
        from .arrayItem import Arrays
        
        valid_self_hosted_types = ["daily_todo", "table", "text_field", "calendar", "note", ]
        valid_component_ref_types = ["check_box", "chart", "text_field", "image","graph"]

        if widget_type in valid_self_hosted_types:
            if widget_type == "daily_todo":
                # For daily_todo, we now just need a selected_date in the data
                if not data or not isinstance(data, dict):
                    data = {}
                if "selected_date" not in data:
                    data["selected_date"] = datetime.utcnow().strftime("%Y-%m-%d")

            elif widget_type == "table":
                # Validate table structure - columns will be managed as arrays
                if not data or not isinstance(data, dict):
                    data = {}
                # Remove primitive arrays - will be created as Array components
                data.pop("columns", None)
                data.pop("rows", None)

            elif widget_type == "text_field":
                # Initialize text field structure
                if not data or not isinstance(data, dict):
                    data = {}
                if "content" not in data:
                    data["content"] = ""
                if "title" not in data:
                    data["title"] = ""
                if "format" not in data:
                    data["format"] = "plain"
                if "editable" not in data:
                    data["editable"] = True

            elif widget_type == "calendar":
                # Validate calendar structure - events will be managed as arrays
                if not data or not isinstance(data, dict):
                    data = {}
                if "view" not in data:
                    data["view"] = "month"
                # Remove primitive events array
                data.pop("events", None)

            elif widget_type == "note":
                # Validate note structure - tags will be managed as arrays
                if not data or not isinstance(data, dict):
                    data = {}
                if "content" not in data:
                    data["content"] = ""
                if "pinned" not in data:
                    data["pinned"] = False
                # Remove primitive tags array
                data.pop("tags", None)

            return data

        elif widget_type in valid_component_ref_types:
            return Widget.validate_component_referenced_type(widget_type, reference_component, data)

        else:
            raise ValidationError(f"Invalid widget type: {widget_type}")

    @staticmethod
    def validate_component_referenced_type(widget_type, reference_component, data=None):
        """Validates widgets that reference a component."""
        if not reference_component:
            raise ValidationError(
                f"Widget type {widget_type} requires a reference component"
            )

        if not data or not isinstance(data, dict):
            data = {}

        if widget_type == "text_field":
            # Validate text_field as a component reference
            if "format" not in data:
                data["format"] = "plain"  # Default format
            if "editable" not in data:
                data["editable"] = False  # Default to non-editable for references

        elif widget_type == "image":
            # Validate image widget structure
            if "url" not in data:
                raise ValidationError("Image widget requires a URL")
            if "alt_text" not in data:
                data["alt_text"] = ""  # Optional alt text for accessibility

        elif widget_type == "chart":
            # Validate chart widget structure
            if "chart_type" not in data:
                data["chart_type"] = "bar"  # Default chart type
            if "data_points" not in data:
                data["data_points"] = []  # Default to an empty list of data points

        elif widget_type == "check_box":
            # Validate check_box widget structure
            if "checked" not in data:
                data["checked"] = False  # Default to unchecked

        elif widget_type == "graph":
            # Validate graph widget referencing an Array_of_pairs component
            if reference_component.comp_type != "Array_of_pairs":
                raise ValidationError("Graph widget must reference a component of type Array_of_pairs")

            # Ensure the component's data type is valid
            if reference_component.data.get("type") != "pair":
                raise ValidationError("Graph widget can only reference an Array_of_pairs component with type 'pair'")

            # Set default graph data structure
            if "x_axis_key" not in data:
                data["x_axis_key"] = ""  # Key to use for x-axis values
            if "y_axis_key" not in data:
                data["y_axis_key"] = ""  # Key to use for y-axis values
            if "title" not in data:
                data["title"] = ""  # Optional title for the graph

            # Validate that x_axis_key and y_axis_key are provided
            if not data["x_axis_key"]:
                raise ValidationError("Graph widget requires an x_axis_key to map x-axis values")
            if not data["y_axis_key"]:
                raise ValidationError("Graph widget requires a y_axis_key to map y-axis values")

        else:
            raise ValidationError(f"Unsupported component-referenced widget type: {widget_type}")

        return data
