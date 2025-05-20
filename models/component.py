from mongoengine import Document, StringField, DictField, ReferenceField, NULLIFY, BooleanField
import uuid
import datetime
from .arrayItem import ArrayItem_db, ArrayMetadata, Arrays

# Predefined data and widget types
PREDEFINED_COMPONENT_TYPES = {
    "int": {"item": 0},
    "str": {"item": ""},
    "bool": {"item": False},
    "date": {"item": datetime.datetime.now().isoformat()},
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
            comp_type=data["comp_type"],
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
            result = Arrays.get_array(self.owner, self.id)
            if result["success"]:
                print ("Array items retrieved successfully.")
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
                "is_deletable": component_db.is_deletable
            })
        return None
    
    def get_component(self):
        if (self.comp_type in ["Array_type", "Array_generic", "Array_of_pairs"]):
            array_result = self.get_array_items()
            print (array_result)
            if not array_result["success"]:
                raise Exception(f"Error: {array_result['message']}")
            self.data = {**(self.data or {}), "items": array_result["array"] , "pagination": array_result["pagination"]}
        return {
            "name": self.name,
            "id": self.id,
            "data": self.data,
            "comp_type": self.comp_type,
            "host_subject": self.host_subject.id,
            "owner": self.owner,
            "is_deletable": self.is_deletable,
        }
