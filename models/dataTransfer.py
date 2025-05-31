from .component import Component_db
from .arrayItem import Arrays
from mongoengine import Document, StringField, DictField, ReferenceField, DateTimeField, NULLIFY
import uuid
from pytz import UTC  # type: ignore
from datetime import datetime
from dateutil import parser as date_parser
import pytz

ACCEPTED_OPERATIONS = {
    "pair": ["update_key", "update_value"],
    "Array_of_pairs": ["append", "remove_back", "remove_front", "delete_at", "push_at", "update_pair"],
    "Array_type": ["append", "remove_back", "remove_front", "delete_at", "push_at", "update_at"],
    "Array_generic": ["append", "remove_back", "remove_front", "delete_at", "push_at", "update_at"],
    "Array_of_strings": ["append", "remove_back", "remove_front", "delete_at", "push_at", "update_at"],
    "Array_of_booleans": ["append", "remove_back", "remove_front", "delete_at", "push_at", "update_at"],
    "Array_of_dates": ["append", "remove_back", "remove_front", "delete_at", "push_at", "update_at"],
    "Array_of_objects": ["append", "remove_back", "remove_front", "delete_at", "push_at", "update_at"],
    "int": ["replace", "add", "multiply"],
    "str": ["replace"],
    "bool": ["replace", "toggle"],
    "date": ["replace"]
}


def parse_schedule_time(schedule_time):
    if isinstance(schedule_time, str) and schedule_time:
        try:
            dt = date_parser.parse(schedule_time)
            if dt.tzinfo is None:
                raise ValueError("schedule_time must include timezone information.")
            return dt.astimezone(UTC)
        except Exception as e:
            print(f"Error parsing schedule_time '{schedule_time}': {e}")
            return None
    elif isinstance(schedule_time, datetime):
        if schedule_time.tzinfo is None:
            raise ValueError("schedule_time datetime object must be timezone-aware.")
        return schedule_time.astimezone(UTC)
    return None


class DataTransfer_db(Document):
    id = StringField(primary_key=True)
    source_component = ReferenceField(
        Component_db, reverse_delete_rule=NULLIFY, required=False)
    target_component = ReferenceField(
        Component_db, reverse_delete_rule=NULLIFY, required=True)
    data_value = DictField(null=True)
    operation = StringField(required=True)
    schedule_time = DateTimeField()
    details = DictField(null=True)
    owner = StringField(required=True)  # Store user ID
    meta = {'collection': 'data_transfers'}
    # todo add host connection


class DataTransfer:
    def __init__(self, id=None, source_component=None, target_component=None, data_value=None, operation="replace", owner=None, details=None, schedule_time=None):
        self.id = id or str(uuid.uuid4())
        self.source_component = source_component
        self.target_component = target_component
        self.data_value = data_value
        self.operation = operation
        self.schedule_time = parse_schedule_time(schedule_time) if schedule_time else None
        self.details = details or {}
        self.details["done"] = False
        self.owner = owner
        self.timestamp = datetime.now(UTC).isoformat()

    def execute(self):
        # Check if operation was already completed
        if self.details and self.details.get("done"):
            return

        # Fetch source and target components
        source_component = target_component = None
        if self.source_component:
            source_component = Component_db.objects(id=self.source_component).first()
            if self.source_component and not source_component:
                print(f"Source component with ID {self.source_component} not found.")
                return
                
        if self.target_component:
            target_component = Component_db.objects(id=self.target_component).first()
        
        if not target_component:
            print(f"Target component with ID {self.target_component} not found.")
            return

        # Validate operation type for target component
        if self.operation not in ACCEPTED_OPERATIONS.get(target_component.comp_type, []):
            print(f"Operation '{self.operation}' not supported for component type '{target_component.comp_type}'.")
            return

        # Type check data_value if it's being used
        if not source_component and self.operation not in ["remove_back", "remove_front", "toggle"]:
            if not hasattr(self, 'data_value') or self.data_value is None:
                print("No source component or data_value provided for operation that requires input.")
                return
                
        # Use source component data if available, else use unbound data_value
        source_value = None
        if source_component:
            if not isinstance(source_component.data, dict) or "item" not in source_component.data:
                print("Invalid source component data structure.")
                return
            source_value = source_component.data.get("item")
        elif hasattr(self, 'data_value') and self.data_value is not None:
            # For direct data_value, we should check if it contains "item" key
            # But for certain operations like delete_at, push_at, update_pair, the structure is different
            if self.operation in ["delete_at", "push_at", "update_pair", "update_at"] and isinstance(self.data_value, dict):
                source_value = self.data_value  # Use the whole data_value for special operations
            elif not isinstance(self.data_value, dict) or "item" not in self.data_value:
                print("Invalid data_value structure. Expected {'item': value}.")
                return
            else:
                source_value = self.data_value.get("item")

        # Validate target component data structure
        if not isinstance(target_component.data, dict):
            print(f"Invalid target component data structure for '{target_component.comp_type}'.")
            return
            
        # For array types, we need to initialize the item if it doesn't exist
        if target_component.comp_type.startswith("Array_") and "item" not in target_component.data:
            target_component.data["item"] = []
        elif "item" not in target_component.data and target_component.comp_type != "Array_of_pairs":
            print(f"Invalid target component data structure for '{target_component.comp_type}'. Missing 'item' key.")
            return

        # Handle operations based on target component type
        if target_component.comp_type == "pair":
            return self._execute_pair_operation(target_component, source_value)
        elif target_component.comp_type == "Array_of_pairs":
            return self._execute_array_of_pairs_operation(target_component, source_value)
        elif target_component.comp_type in ["Array_type", "Array_generic", "Array_of_strings", 
                                        "Array_of_booleans", "Array_of_dates", "Array_of_objects"]:
            return self._execute_array_operation(target_component, source_value)
        else:
            return self._execute_scalar_operation(target_component, source_value)

    def _execute_pair_operation(self, target_component, source_value):
        """Handle operations specific to pair component type"""
        # Initialize item if it doesn't exist
        if "item" not in target_component.data:
            target_component.data["item"] = {"key": "", "value": ""}
        
        # Validate pair structure
        if not isinstance(target_component.data["item"], dict) or \
        "key" not in target_component.data["item"] or \
        "value" not in target_component.data["item"]:
            print("Invalid target component data structure for 'pair'. Expected {'item': {'key': key, 'value': value}}.")
            return

        if self.operation == "update_key":
            # Check if data_value has the right structure
            if not hasattr(self, 'data_value') or not isinstance(self.data_value, dict) or \
            "item" not in self.data_value or not isinstance(self.data_value["item"], dict) or \
            "key" not in self.data_value["item"]:
                print("Invalid data_value structure for 'update_key' operation. Expected {'item': {'key': new_key}}.")
                return
            
            new_key = self.data_value["item"]["key"]
            # Type check the new key if necessary (e.g., if key should be string)
            if target_component.data.get("type", {}).get("key") == "str" and not isinstance(new_key, str):
                print(f"Type mismatch: Expected string for key, got {type(new_key).__name__}.")
                return
                
            target_component.data["item"]["key"] = new_key
            
        elif self.operation == "update_value":
            # Check if data_value has the right structure
            if not hasattr(self, 'data_value') or not isinstance(self.data_value, dict) or \
            "item" not in self.data_value or not isinstance(self.data_value["item"], dict) or \
            "value" not in self.data_value["item"]:
                print("Invalid data_value structure for 'update_value' operation. Expected {'item': {'value': new_value}}.")
                return
                
            new_value = self.data_value["item"]["value"]
            # Type check the new value if necessary
            value_type = target_component.data.get("type", {}).get("value")
            if value_type and value_type != "any":
                if value_type == "int" and not isinstance(new_value, int):
                    print(f"Type mismatch: Expected int for value, got {type(new_value).__name__}.")
                    return
                elif value_type == "str" and not isinstance(new_value, str):
                    print(f"Type mismatch: Expected string for value, got {type(new_value).__name__}.")
                    return
                elif value_type == "bool" and not isinstance(new_value, bool):
                    print(f"Type mismatch: Expected boolean for value, got {type(new_value).__name__}.")
                    return
                    
            target_component.data["item"]["value"] = new_value
            
        else:
            print(f"Unsupported operation '{self.operation}' for pair.")
            return

        self._mark_as_done(target_component)
        return True

    def _execute_array_of_pairs_operation(self, target_component, source_value):
        """Handle operations specific to Array_of_pairs component type"""
        # Initialize the item array if it doesn't exist
        if "item" not in target_component.data:
            target_component.data["item"] = []
        
        # Ensure we have a valid type specification
        if not isinstance(target_component.data.get("type"), dict) or "key" not in target_component.data["type"] or "value" not in target_component.data["type"]:
            print("Invalid target component data structure for 'Array_of_pairs'. Expected {'type': {'key': key_type, 'value': value_type}}.")
            return

        # Check pair type requirements
        key_type = target_component.data["type"].get("key")
        value_type = target_component.data["type"].get("value")

        if self.operation == "append":
            # Validate source_value structure for append operation
            if not source_value or not isinstance(source_value, dict) or "key" not in source_value or "value" not in source_value:
                print("Invalid source value for 'append' operation on Array_of_pairs. Expected {'key': key, 'value': value}.")
                return
                
            # Type check the pair if necessary
            if key_type == "str" and not isinstance(source_value["key"], str):
                print(f"Type mismatch: Expected string for key, got {type(source_value['key']).__name__}.")
                return
            if value_type and value_type != "any":
                if value_type == "int" and not isinstance(source_value["value"], int):
                    print(f"Type mismatch: Expected int for value, got {type(source_value['value']).__name__}.")
                    return
                elif value_type == "str" and not isinstance(source_value["value"], str):
                    print(f"Type mismatch: Expected string for value, got {type(source_value['value']).__name__}.")
                    return
                elif value_type == "bool" and not isinstance(source_value["value"], bool):
                    print(f"Type mismatch: Expected boolean for value, got {type(source_value['value']).__name__}.")
                    return

            result = Arrays.append_to_array(
                user_id=target_component.owner,
                component_id=target_component.id,
                value=source_value
            )
            
        elif self.operation == "remove_back":
            if not target_component.data["item"]:
                print("Cannot remove from empty array.")
                return
                
            result = Arrays.remove_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=-1
            )
            
        elif self.operation == "remove_front":
            if not target_component.data["item"]:
                print("Cannot remove from empty array.")
                return
                
            result = Arrays.remove_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=0
            )
            
        elif self.operation == "delete_at":
            # Validate index parameter
            if not isinstance(source_value, dict) or "index" not in source_value:
                print("Missing 'index' in data_value for 'delete_at' operation.")
                return
                
            index = source_value.get("index")
            if not isinstance(index, int):
                print(f"Invalid index type: expected int, got {type(index).__name__}.")
                return
                
            result = Arrays.remove_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=index
            )
            
        elif self.operation == "push_at":
            # Validate parameters
            if not isinstance(source_value, dict):
                print("Invalid data_value structure for 'push_at' operation.")
                return
                
            if "index" not in source_value:
                print("Missing 'index' in data_value for 'push_at' operation.")
                return
                
            if "item" not in source_value:
                print("Missing 'pair' in data_value for 'push_at' operation.")
                return
                
            index = source_value.get("index")
            pair = source_value.get("item")
            
            if not isinstance(index, int):
                print(f"Invalid index type: expected int, got {type(index).__name__}.")
                return
                
            # Type check the pair
            if not isinstance(pair, dict) or "key" not in pair or "value" not in pair:
                print("Invalid pair structure. Expected {'key': key, 'value': value}.")
                return
                
            if key_type == "str" and not isinstance(pair["key"], str):
                print(f"Type mismatch: Expected string for key, got {type(pair['key']).__name__}.")
                return
                
            if value_type and value_type != "any":
                if value_type == "int" and not isinstance(pair["value"], int):
                    print(f"Type mismatch: Expected int for value, got {type(pair['value']).__name__}.")
                    return
                elif value_type == "str" and not isinstance(pair["value"], str):
                    print(f"Type mismatch: Expected string for value, got {type(pair['value']).__name__}.")
                    return
                elif value_type == "bool" and not isinstance(pair["value"], bool):
                    print(f"Type mismatch: Expected boolean for value, got {type(pair['value']).__name__}.")
                    return
                    
            result = Arrays.insert_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=index,
                value=pair
            )
            
        elif self.operation == "update_pair":
            # Validate parameters
            if not isinstance(source_value, dict):
                print("Invalid data_value structure for 'update_pair' operation.")
                return
                
            if "index" not in source_value:
                print("Missing 'index' in data_value for 'update_pair' operation.")
                return
                
            if "item" not in source_value:
                print("Missing 'pair' in data_value for 'update_pair' operation.")
                return
                
            index = source_value.get("index")
            pair = source_value.get("item")
            
            if not isinstance(index, int):
                print(f"Invalid index type: expected int, got {type(index).__name__}.")
                return
                
            # Type check the pair
            if not isinstance(pair, dict) or "key" not in pair or "value" not in pair:
                print("Invalid pair structure. Expected {'key': key, 'value': value}.")
                return
                
            if key_type == "str" and not isinstance(pair["key"], str):
                print(f"Type mismatch: Expected string for key, got {type(pair['key']).__name__}.")
                return
                
            if value_type and value_type != "any":
                if value_type == "int" and not isinstance(pair["value"], int):
                    print(f"Type mismatch: Expected int for value, got {type(pair['value']).__name__}.")
                    return
                elif value_type == "str" and not isinstance(pair["value"], str):
                    print(f"Type mismatch: Expected string for value, got {type(pair['value']).__name__}.")
                    return
                elif value_type == "bool" and not isinstance(pair["value"], bool):
                    print(f"Type mismatch: Expected boolean for value, got {type(pair['value']).__name__}.")
                    return
                    
            result = Arrays.update_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=index,
                value=pair
            )
            
        else:
            print(f"Unsupported operation '{self.operation}' for Array_of_pairs.")
            return

        if not result.get("success", False):
            print(f"Array_of_pairs operation failed: {result.get('message', 'Unknown error')}")
            return

        self._mark_as_done(target_component)
        return True

    def _execute_array_operation(self, target_component, source_value):
        """Handle operations specific to array component types"""
        # Initialize item if it doesn't exist
        if "item" not in target_component.data:
            target_component.data["item"] = []
            
        # Validate array structure
        if not isinstance(target_component.data["item"], list):
            print(f"Invalid target component data structure for '{target_component.comp_type}'. Expected {'item': [values]}.")
            return

        # Check array element type requirement - handle both simple string type and dict with "type" key
        array_type = None
        if "type" in target_component.data:
            if isinstance(target_component.data["type"], str):
                array_type = target_component.data["type"]
            elif isinstance(target_component.data["type"], dict) and "type" in target_component.data["type"]:
                array_type = target_component.data["type"]["type"]
        
        if self.operation == "append":
            # Type check the value based on array type
            if array_type and array_type != "any":
                if array_type == "int" and not isinstance(source_value, int):
                    print(f"Type mismatch: Expected int, got {type(source_value).__name__}.")
                    return
                elif array_type == "str" and not isinstance(source_value, str):
                    print(f"Type mismatch: Expected string, got {type(source_value).__name__}.")
                    return
                elif array_type == "bool" and not isinstance(source_value, bool):
                    print(f"Type mismatch: Expected boolean, got {type(source_value).__name__}.")
                    return
                elif array_type == "date" and not isinstance(source_value, str):
                    # Basic ISO date format check
                    try:
                        datetime.datetime.fromisoformat(source_value)
                    except (ValueError, TypeError):
                        print(f"Type mismatch: Expected ISO date string, got invalid format: {source_value}.")
                        return
                elif array_type == "object" and not isinstance(source_value, dict):
                    print(f"Type mismatch: Expected object (dict), got {type(source_value).__name__}.")
                    return
                    
            result = Arrays.append_to_array(
                user_id=target_component.owner,
                component_id=target_component.id,
                value=source_value
            )
            
        elif self.operation == "remove_back":
            if not target_component.data["item"]:
                print("Cannot remove from empty array.")
                return
                
            result = Arrays.remove_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=-1
            )
            
        elif self.operation == "remove_front":
            if not target_component.data["item"]:
                print("Cannot remove from empty array.")
                return
                
            result = Arrays.remove_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=0
            )
            
        elif self.operation == "delete_at":
            # Validate index parameter
            if not isinstance(source_value, dict) or "index" not in source_value:
                print("Missing 'index' in data_value for 'delete_at' operation.")
                return
                
            index = source_value.get("index")
            if not isinstance(index, int):
                print(f"Invalid index type: expected int, got {type(index).__name__}.")
                return
                
                
            result = Arrays.remove_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=index
            )
            
        elif self.operation == "push_at":
            # Validate parameters
            if not isinstance(source_value, dict):
                print("Invalid data_value structure for 'push_at' operation.")
                return
                
            if "index" not in source_value:
                print("Missing 'index' in data_value for 'push_at' operation.")
                return
                
            if "value" not in source_value:
                print("Missing 'value' in data_value for 'push_at' operation.")
                return
                
            index = source_value.get("index")
            value = source_value.get("value")
            
            if not isinstance(index, int):
                print(f"Invalid index type: expected int, got {type(index).__name__}.")
                return
                
            # Type check the value based on array type
            if array_type and array_type != "any":
                if array_type == "int" and not isinstance(value, int):
                    print(f"Type mismatch: Expected int, got {type(value).__name__}.")
                    return
                elif array_type == "str" and not isinstance(value, str):
                    print(f"Type mismatch: Expected string, got {type(value).__name__}.")
                    return
                elif array_type == "bool" and not isinstance(value, bool):
                    print(f"Type mismatch: Expected boolean, got {type(value).__name__}.")
                    return
                elif array_type == "date" and not isinstance(value, str):
                    # Basic ISO date format check
                    try:
                        datetime.datetime.fromisoformat(value)
                    except (ValueError, TypeError):
                        print(f"Type mismatch: Expected ISO date string, got invalid format: {value}.")
                        return
                elif array_type == "object" and not isinstance(value, dict):
                    print(f"Type mismatch: Expected object (dict), got {type(value).__name__}.")
                    return
                    
            result = Arrays.insert_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=index,
                value=value
            )
        
        elif self.operation == "update_at":
            # Validate parameters
            if not isinstance(source_value, dict):
                print("Invalid data_value structure for 'update_at' operation.")
                return
                
            if "index" not in source_value:
                print("Missing 'index' in data_value for 'update_at' operation.")
                return
                
            if "value" not in source_value:
                print("Missing 'value' in data_value for 'update_at' operation.")
                return
                
            index = source_value.get("index")
            value = source_value.get("value")
            
            if not isinstance(index, int):
                print(f"Invalid index type: expected int, got {type(index).__name__}.")
                return
                
                
            # Type check the value based on array type
            if array_type and array_type != "any":
                if array_type == "int" and not isinstance(value, int):
                    print(f"Type mismatch: Expected int, got {type(value).__name__}.")
                    return
                elif array_type == "str" and not isinstance(value, str):
                    print(f"Type mismatch: Expected string, got {type(value).__name__}.")
                    return
                elif array_type == "bool" and not isinstance(value, bool):
                    print(f"Type mismatch: Expected boolean, got {type(value).__name__}.")
                    return
                elif array_type == "date" and not isinstance(value, str):
                    # Basic ISO date format check
                    try:
                        datetime.datetime.fromisoformat(value)
                    except (ValueError, TypeError):
                        print(f"Type mismatch: Expected ISO date string, got invalid format: {value}.")
                        return
                elif array_type == "object" and not isinstance(value, dict):
                    print(f"Type mismatch: Expected object (dict), got {type(value).__name__}.")
                    return
                    
            result = Arrays.update_at_index(
                user_id=target_component.owner,
                component_id=target_component.id,
                index=index,
                value=value
            )
            
        else:
            print(f"Unsupported operation '{self.operation}' for {target_component.comp_type}.")
            return

        if not result.get("success", False):
            print(f"Array operation failed: {result.get('message', 'Unknown error')}")
            return

        self._mark_as_done(target_component)
        return True

    def _execute_scalar_operation(self, target_component, source_value):
        """Handle operations specific to scalar component types (int, str, bool, date)"""
        # Validate operation type
        if self.operation not in ["replace", "add", "multiply", "toggle"]:
            print(f"Unsupported operation '{self.operation}' for {target_component.comp_type}.")
            return

        # Handle operations based on type
        if self.operation == "replace":
            # Type check the new value based on component type
            if target_component.comp_type == "int" and not isinstance(source_value, int):
                print(f"Type mismatch: Expected int for '{target_component.comp_type}', got {type(source_value).__name__}.")
                return
            elif target_component.comp_type == "str" and not isinstance(source_value, str):
                print(f"Type mismatch: Expected string for '{target_component.comp_type}', got {type(source_value).__name__}.")
                return
            elif target_component.comp_type == "bool" and not isinstance(source_value, bool):
                print(f"Type mismatch: Expected boolean for '{target_component.comp_type}', got {type(source_value).__name__}.")
                return
            elif target_component.comp_type == "date" and not isinstance(source_value, str):
                # Basic ISO date format check
                try:
                    datetime.datetime.fromisoformat(source_value)
                except (ValueError, TypeError):
                    print(f"Type mismatch: Expected ISO date string for '{target_component.comp_type}', got invalid format: {source_value}.")
                    return
                    
            target_component.data["item"] = source_value
            
        elif self.operation == "add":
            # Check if operation makes sense for the type
            if not isinstance(target_component.data["item"], (int, float)):
                print(f"Cannot perform 'add' operation on non-numeric type: {type(target_component.data['item']).__name__}.")
                return
                
            if not isinstance(source_value, (int, float)):
                print(f"Cannot add non-numeric value: {type(source_value).__name__}.")
                return
                
            target_component.data["item"] += source_value
            
        elif self.operation == "multiply":
            # Check if operation makes sense for the type
            if not isinstance(target_component.data["item"], (int, float)):
                print(f"Cannot perform 'multiply' operation on non-numeric type: {type(target_component.data['item']).__name__}.")
                return
                
            if not isinstance(source_value, (int, float)):
                print(f"Cannot multiply by non-numeric value: {type(source_value).__name__}.")
                return
                
            target_component.data["item"] *= source_value
            
        elif self.operation == "toggle":
            # Check if operation makes sense for the type
            if not isinstance(target_component.data["item"], bool):
                print(f"Cannot perform 'toggle' operation on non-boolean type: {type(target_component.data['item']).__name__}.")
                return
                
            target_component.data["item"] = not target_component.data["item"]
            
        else:
            print(f"Unsupported operation '{self.operation}' for {target_component.comp_type}.")
            return

        self._mark_as_done(target_component)
        return True

    def _mark_as_done(self, target_component):
        """Mark operation as completed and save changes"""
        self.details = {**(self.details or {}), "done": True}
        target_component.save()
        self.save_to_db()
        print(f"Data transfer executed: {self.operation} on {target_component.id}")

    def to_json(self):
        return {
            "id": self.id,
            "source_component": self.source_component,
            "target_component": self.target_component,
            "data_value": self.data_value,
            "operation": self.operation,
            "schedule_time": self.schedule_time.isoformat() if self.schedule_time else None,
            "details": self.details,
            "timestamp": self.timestamp,
            "owner": self.owner
        }

    @staticmethod
    def from_json(data):
        return DataTransfer(
            id=data.get("id"),
            source_component=data.get("source_component"),
            target_component=data.get("target_component"),
            data_value=data.get("data_value"),
            operation=data.get("operation"),
            details=data.get("details"),
            schedule_time=datetime.fromisoformat(
                data["schedule_time"]) if data.get("schedule_time") else None,
            owner=data.get("owner")
        )

    def save_to_db(self):
        data_transfer_db = DataTransfer_db(
            id=self.id,
            source_component=self.source_component,
            target_component=self.target_component,
            data_value=self.data_value,
            operation=self.operation,
            schedule_time=self.schedule_time,
            details=self.details,
            owner=self.owner
        )
        data_transfer_db.save()

    @staticmethod
    def load_from_db(transfer_id):
        data_transfer_db = DataTransfer_db.objects(id=transfer_id).first()
        source_component_id = data_transfer_db.source_component.id if data_transfer_db.source_component else None
        if data_transfer_db:
            return DataTransfer(
                id=data_transfer_db.id,
                source_component=source_component_id,
                target_component=data_transfer_db.target_component.id,
                data_value=data_transfer_db.data_value,
                operation=data_transfer_db.operation,
                details=data_transfer_db.details,
                schedule_time=data_transfer_db.schedule_time,
                owner=data_transfer_db.owner
            )
        return None
