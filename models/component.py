from mongoengine import Document, StringField, DictField, ReferenceField, NULLIFY, BooleanField, ListField
import uuid
import datetime
from .arrayItem import ArrayItem_db, ArrayMetadata, Arrays

# Predefined data and widget types
PREDEFINED_COMPONENT_TYPES = {
    "int": {"item": 0},
    "double": {"item": 0.0},
    "str": {"item": ""},
    "bool": {"item": False},
    "date": {"item": datetime.datetime.now().isoformat()},
    "phone": {
        "item": {
            "country_code": "",
            "number": ""
        }
    },
    "Array_type": {"type": "int"},  # Array of integers
    "Array_generic": {"type": "any"},  # Array of any type
    "pair": {"key": "str", "value": "any"},  # Pair with string key and any type value
    "Array_of_pairs": {"type": {"key": "str", "value": "any"}},  # Array of pairs with string key and any type value
    "Array_of_strings": {"type": "str"},  # Array of strings
    "Array_of_booleans": {"type": "bool"},  # Array of booleans
    "Array_of_dates": {"type": "date"},  # Array of dates
    "Array_of_objects": {"type": "object"},  # Array of objects
}


class Component_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    host_subject = ReferenceField("Subject_db", required=True)
    data = DictField(null=True , required=False) 
    comp_type = StringField(required=True)  # Component type (e.g., Array_type, str, etc.)
    owner = StringField(required=True)
    is_deletable = BooleanField(default=True)
    # Track which widgets reference this component
    referenced_by_widgets = ListField(StringField(), default=list)
    allowed_widget_type = StringField(required=True, default="any")  # Type of widgets that can reference this component

    meta = {'collection': 'components'}

    def add_widget_reference(self, widget_id, widget_type):
        """Add a widget reference to this component."""
        # Check if the widget type is allowed to reference this component
        if self.allowed_widget_type != "any" and widget_type != self.allowed_widget_type:
            raise ValueError(f"Widget type '{widget_type}' is not allowed to reference this component. Only '{self.allowed_widget_type}' widgets are allowed.")
        
        reference_info = f"{widget_id}:{widget_type}"
        if reference_info not in self.referenced_by_widgets:
            self.referenced_by_widgets.append(reference_info)
            self.save()

    def remove_widget_reference(self, widget_id):
        """Remove a widget reference from this component."""
        self.referenced_by_widgets = [
            ref for ref in self.referenced_by_widgets 
            if not ref.startswith(f"{widget_id}:")
        ]
        self.save()

    def get_referencing_widgets(self):
        """Get list of widgets that reference this component."""
        widgets = []
        for ref in self.referenced_by_widgets:
            if ":" in ref:
                widget_id, widget_type = ref.split(":", 1)
                widgets.append({"widget_id": widget_id, "widget_type": widget_type})
        return widgets

    def can_be_referenced_by_widget_type(self, widget_type):
        """Check if a widget type can reference this component."""
        return self.allowed_widget_type == "any" or self.allowed_widget_type == widget_type


class Component:
    def __init__(self, name, comp_type, data=None, id=None, host_subject=None, owner=None, is_deletable=True, allowed_widget_type="any", referenced_by_widgets=None):
        self.name = name
        self.comp_type = comp_type
        self.data = data or PREDEFINED_COMPONENT_TYPES.get(comp_type, {})
        self.id = id or str(uuid.uuid4())
        self.host_subject = host_subject
        self.owner = owner
        self.is_deletable = is_deletable
        self.allowed_widget_type = allowed_widget_type
        self.referenced_by_widgets = referenced_by_widgets or []

    def to_json(self):
        return {
            "name": self.name,
            "id": self.id,
            "comp_type": self.comp_type,
            "data": self.data,
            "host_subject": self.host_subject,
            "owner": self.owner,
            "is_deletable": self.is_deletable,
            "allowed_widget_type": self.allowed_widget_type,
            "referenced_by_widgets": self.referenced_by_widgets
        }

    @staticmethod
    def from_json(data):
        return Component(
            name=data["name"],
            data=data["data"],
            id=data["id"],
            comp_type=data["comp_type"],
            host_subject=data["host_subject"],
            owner=data.get("owner"),
            is_deletable=data.get("is_deletable", True),
            allowed_widget_type=data.get("allowed_widget_type", "any"),
            referenced_by_widgets=data.get("referenced_by_widgets", [])
        )

    def save_to_db(self):
        component_db = Component_db(
            id=self.id,
            name=self.name,
            host_subject=self.host_subject,
            data=self.data,
            comp_type=self.comp_type,
            owner=self.owner,
            is_deletable=self.is_deletable,
            allowed_widget_type=self.allowed_widget_type,
            referenced_by_widgets=self.referenced_by_widgets
        )
        component_db.save()

    def alter_data(self, value):
        if self.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]:
            # Use ArrayMetadata and Arrays for managing array data
            array_metadata = ArrayMetadata.objects(host_component=self.id).first()
            if not array_metadata:
                array_metadata = ArrayMetadata(
                    user=self.owner,
                    name=f"{self.name}_array",
                    host_component=self.id
                )
                array_metadata.save()

            # Clear existing array items
            Arrays.delete_array(self.owner, self.id)

            # Add new array items
            if isinstance(value, list):
                Arrays.create_array(self.owner, self.id, array_metadata.name, initial_elements=value)
        elif self.comp_type == "pair":
            if isinstance(value, dict) and "key" in value and "value" in value:
                self.data.update(value)
        else:
            self.data["item"] = value
        self.save_to_db()

    def get_array_items(self):
        if self.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]:
            result = Arrays.get_array(self.owner, self.id, host_type='component')
            if result["success"]:
                print("Array items retrieved successfully.")
                return result
        return None

    @staticmethod
    def load_from_db(comp_id):
        component_db = Component_db.objects(id=str(comp_id)).first()
        print (component_db)
        if component_db:
            print ("returning")
            return Component.from_json({
                "name": component_db.name,
                "id": component_db.id,
                "data": component_db.data,
                "comp_type": component_db.comp_type,
                "host_subject": component_db.host_subject,
                "owner": component_db.owner,
                "is_deletable": component_db.is_deletable,
                "allowed_widget_type": component_db.allowed_widget_type,
                "referenced_by_widgets": component_db.referenced_by_widgets
            })
        return None
    
    #todo there is no more than the first page of items
    def get_component(self):
        if (self.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]):
            array_result = self.get_array_items()
            print (array_result)
            if not array_result["success"]:
                raise Exception(f"Error: {array_result['message']}")
            self.data = {**(self.data or {}), "items": array_result["array"] , "pagination": array_result["pagination"]}
        
        # Get referencing widgets info
        component_db = Component_db.objects(id=self.id).first()
        referencing_widgets = component_db.get_referencing_widgets() if component_db else []
        
        return {
            "name": self.name,
            "id": self.id,
            "data": self.data,
            "comp_type": self.comp_type,
            "host_subject": self.host_subject.id,
            "owner": self.owner,
            "is_deletable": self.is_deletable,
            "referenced_by_widgets": referencing_widgets,
            "allowed_widget_type": self.allowed_widget_type
        }
