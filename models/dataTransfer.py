from .component import Component_db
from .arrayItem import Arrays
from mongoengine import Document, StringField, DictField, ReferenceField, DateTimeField, NULLIFY
import uuid
from pytz import UTC  # type: ignore
from datetime import datetime

ACCEPTED_OPERATIONS = {
    "int": ["replace", "add", "multiply"],
    "str": ["replace"],
    "date": ["replace"],
    "bool": ["replace", "toggle"],
    "Array_type": ["replace", "append", "remove_back", "remove_front", "delete_at", "push_at"],
    "Array_generic": ["replace", "append", "remove_back", "remove_front", "delete_at", "push_at"],
    "pair": ["replace", "update_key", "update_value"],  # New operations for pair
    "Array_of_pairs": ["replace", "append", "remove_back", "remove_front", "delete_at", "push_at", "update_pair"],  # New operations for Array_of_pairs
}


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
        self.schedule_time = schedule_time
        self.details = details or {}
        self.details["done"] = False
        self.owner = owner
        self.timestamp = datetime.now(UTC).isoformat()

    def execute(self):
        if self.details.get("done"):
            return
        source_component = target_component = None
        if self.source_component:
            source_component = Component_db.objects(id=self.source_component).first()
        if self.target_component:
            target_component = Component_db.objects(id=self.target_component).first()

        if not target_component or self.operation not in ACCEPTED_OPERATIONS[target_component.comp_type]:
            print(f"Operation '{self.operation}' not supported for component type '{target_component.comp_type}'.")
            return

        # Use source component data if available, else use unbound data_value
        source_value = (source_component.data if source_component else self.data_value)["item"]

        if target_component.comp_type == "pair":
            # Operations for `pair`
            if self.operation == "update_key":
                if self.data_value and self.data_value.get("item"):
                    new_key = self.data_value.get("item").get("key")
                    if new_key:
                        target_component.data["item"]["key"] = new_key
                    else:
                        print("Missing 'key' in data_value for update_key operation.")
                        return
                else:
                    print("Invalid data_value or missing 'item' for update_key operation.")
                    return
            elif self.operation == "update_value":
                if self.data_value and self.data_value.get("item"):
                    new_value = self.data_value.get("item").get("value")
                    if new_value:
                        target_component.data["item"]["value"] = new_value
                    else:
                        print("Missing 'value' in data_value for update_value operation.")
                        return
                else:
                    print("Invalid data_value or missing 'item' for update_value operation.")
                    return
            else:
                print(f"Unsupported operation '{self.operation}' for pair.")
                return

        elif target_component.comp_type == "Array_of_pairs":
            # Operations for `Array_of_pairs`
            if self.operation == "append":
                result = Arrays.append_to_array(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    value=source_value
                )
            elif self.operation == "remove_back":
                result = Arrays.remove_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=-1
                )
            elif self.operation == "remove_front":
                result = Arrays.remove_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=0
                )
            elif self.operation == "delete_at":
                index = self.data_value.get("index")
                result = Arrays.remove_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=index
                )
            elif self.operation == "push_at":
                index = self.data_value.get("index")
                pair = self.data_value.get("pair")
                result = Arrays.insert_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=index,
                    value=pair
                )
            elif self.operation == "update_pair":
                index = self.data_value.get("index")
                pair = self.data_value.get("pair")
                result = Arrays.update_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=index,
                    value=pair
                )
            else:
                print(f"Unsupported operation '{self.operation}' for Array_of_pairs.")
                return

            if not result["success"]:
                print(f"Array_of_pairs operation failed: {result['message']}")
                return

        elif target_component.comp_type in ["Array_type", "Array_generic"]:
            # Operations for generic arrays
            if self.operation == "append":
                result = Arrays.append_to_array(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    value=source_value
                )
            elif self.operation == "remove_back":
                result = Arrays.remove_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=-1
                )
            elif self.operation == "remove_front":
                result = Arrays.remove_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=0
                )
            elif self.operation == "delete_at":
                index = self.data_value.get("index")
                result = Arrays.remove_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=index
                )
            elif self.operation == "push_at":
                index = self.data_value.get("index")
                value = self.data_value.get("value")
                result = Arrays.insert_at_index(
                    user_id=target_component.owner,
                    component_id=target_component.id,
                    index=index,
                    value=value
                )
            else:
                print(f"Unsupported operation '{self.operation}' for array.")
                return

            if not result["success"]:
                print(f"Array operation failed: {result['message']}")
                return

        else:
            # Handle non-array operations
            if self.operation == "replace":
                target_component.data["item"] = source_value
            elif self.operation == "add" and isinstance(source_value, (int, float)) and isinstance(target_component.data, (int, float)):
                target_component.data["item"]+= source_value
            elif self.operation == "multiply" and isinstance(source_value, (int, float)) and isinstance(target_component.data, (int, float)):
                target_component.data ["item"]*= source_value
            elif self.operation == "toggle" and isinstance(target_component.data, bool):
                target_component.data ["item"]= not target_component.data
            else:
                print(f"Unsupported operation '{self.operation}' for non-array component.")
                return

        self.details = {**(self.details or {}), "done": True}
        target_component.save()
        self.save_to_db()
        print(f"Data transfer executed: {self.operation} on {target_component.id}")
        return True

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
