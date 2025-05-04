from .component import Component_db
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
            source_component = Component_db.objects(
                id=self.source_component).first()
        if self.target_component:
            target_component = Component_db.objects(
                id=self.target_component).first()

        if self.operation not in ACCEPTED_OPERATIONS[target_component.comp_type]:
            print(f"Operation '{self.operation}' not supported for component type '{
                  target_component.comp_type}'.")
            return

        """Perform the data transfer and apply the operation."""
        if target_component:
            if isinstance(target_component.data, dict) and "items" in target_component.data:
                target_data = target_component.data.get("items")
            elif "item" in target_component.data:
                target_data = target_component.data

            # Use source component data if available, else use unbound data_value
            source_value = None
            if source_component:
                source_value = source_component.data
            else:
                source_value = self.data_value
            if isinstance(source_value, dict) and len(source_value) == 1:
                source_value = list(source_value.values())[0]
            if isinstance(target_data, dict) and len(target_data) == 1:
                target_data = list(target_data.values())[0]
            # type checks
            if target_component.comp_type == "Array_generic":
                pass
            elif target_component and target_component.comp_type.startswith("Array_type") and isinstance(target_data, list):
                if source_component and source_component.comp_type != target_component.data["type"]:
                    print(f"Source and target components must be of the same type.{
                          type(self.data_value).__name__}.")
                    return
            elif (source_component is not None) and (source_component.comp_type != target_component.comp_type or type(source_value).__name__ != target_component.comp_type):
                print(f"Source and target components must be of the same type.{
                    type(source_value).__name__}{source_component.comp_type}.")
                return
            # by default the remove_front , remove_front don't need source data
            if source_value is not None or self.operation == "remove_back" or self.operation == "remove_front":
                print(source_value)
                print(target_data)
                # Perform operations based on type and specified action
                if self.operation == "replace":
                    target_data = source_value
                elif self.operation == "add" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data += source_value
                elif self.operation == "multiply" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data *= source_value
                elif self.operation == "toggle" and isinstance(target_data, bool):
                    target_data = not target_data
                elif self.operation == "append" and isinstance(target_data, list) and (target_component.comp_type == "Array_generic" or type(source_value).__name__ == target_component.data["type"]):
                    target_data.append(
                        {"item": source_value, "id": str(uuid.uuid4())})
                elif self.operation == "remove_back" and isinstance(target_data, list) and len(target_data) >= 0:
                    removed = target_data.pop()
                    if (isinstance(removed, dict)):
                        self.details["removed"] = removed
                elif self.operation == "remove_front" and isinstance(target_data, list) and len(target_data) >= 0:
                    removed = target_data.pop(0)
                    if (isinstance(removed, dict)):
                        self.details["removed"] = removed
                elif self.operation == "delete_at" and isinstance(target_data, list) and isinstance(self.data_value, dict) and "index" in self.data_value and (target_component.comp_type == "Array_generic" or type(target_data["item"]).__name__ == target_component.data["type"]):
                    print(f"target_data index : {target_data}")
                    index = self.data_value.get("index")
                    removed = None
                    if isinstance(index, int) and 0 <= index <= len(target_data):
                        removed = target_data.pop(int(index))
                    if (isinstance(removed, dict)):
                        self.details["removed"] = removed
                elif self.operation == "push_at" and isinstance(target_data, list) and isinstance(self.data_value, dict) and "index" in self.data_value and (target_component.comp_type == "Array_generic" or type(source_value["item"]).__name__ == target_component.data["type"]):
                    index = self.data_value.get("index")
                    item = source_value.get("item")
                    if isinstance(index, int) and 0 <= index <= len(target_data):
                        target_data.insert(
                            index, {"item": source_value["item"], "id": str(uuid.uuid4())})
                elif self.operation == "replace" and target_component.comp_type == "pair":
                    target_data["key"] = source_value.get("key", target_data["key"])
                    target_data["value"] = source_value.get("value", target_data["value"])
                elif self.operation == "update_key" and target_component.comp_type == "pair":
                    if "key" in source_value:
                        target_data["key"] = source_value["key"]
                elif self.operation == "update_value" and target_component.comp_type == "pair":
                    if "value" in source_value:
                        target_data["value"] = source_value["value"]
                elif self.operation == "append" and target_component.comp_type == "Array_of_pairs":
                    if isinstance(source_value, dict) and "key" in source_value and "value" in source_value:
                        target_data.append(source_value)
                elif self.operation == "remove_back" and target_component.comp_type == "Array_of_pairs":
                    if len(target_data) > 0:
                        removed = target_data.pop()
                        self.details["removed"] = removed
                elif self.operation == "remove_front" and target_component.comp_type == "Array_of_pairs":
                    if len(target_data) > 0:
                        removed = target_data.pop(0)
                        self.details["removed"] = removed
                elif self.operation == "delete_at" and target_component.comp_type == "Array_of_pairs":
                    index = self.data_value.get("index")
                    if isinstance(index, int) and 0 <= index < len(target_data):
                        removed = target_data.pop(index)
                        self.details["removed"] = removed
                elif self.operation == "push_at" and target_component.comp_type == "Array_of_pairs":
                    index = self.data_value.get("index")
                    pair = self.data_value.get("pair")
                    if isinstance(index, int) and 0 <= index <= len(target_data) and isinstance(pair, dict) and "key" in pair and "value" in pair:
                        target_data.insert(index, pair)
                elif self.operation == "update_pair" and target_component.comp_type == "Array_of_pairs":
                    index = self.data_value.get("index")
                    pair = self.data_value.get("pair")
                    if isinstance(index, int) and 0 <= index < len(target_data) and isinstance(pair, dict):
                        target_data[index].update(pair)
                elif target_component.comp_type in ["Array_type", "Array_generic"]:
                    target_items = ArrayItem_db.objects(component=target_component.id)
                    if self.operation == "append":
                        ArrayItem_db(component=target_component.id, value=str(source_value)).save()
                    elif self.operation == "remove_back" and target_items:
                        target_items.order_by('-id').first().delete()
                    elif self.operation == "remove_front" and target_items:
                        target_items.order_by('id').first().delete()
                    elif self.operation == "delete_at":
                        index = self.data_value.get("index")
                        if isinstance(index, int) and 0 <= index < len(target_items):
                            target_items[index].delete()
                    elif self.operation == "push_at":
                        index = self.data_value.get("index")
                        value = self.data_value.get("value")
                        if isinstance(index, int) and value:
                            ArrayItem_db(component=target_component.id, value=str(value)).save()
                    return True
                else:
                    return False
                if not (target_component.comp_type.startswith("Array") and isinstance(target_data, list)) or (target_component.comp_type not in ["Array_type", "Array_generic"]):
                    target_component.data["item"] = target_data
                else:
                    target_component.data["items"] = target_data

                self.details = {**(self.details or {}), "done": True}
                target_component.save()
                self.save_to_db()
                print(f"Data transfer executed: {self.operation} on {target_component.id} with value {target_data}")
                return True
            else:
                print(f"Source data not available for operation '{
                      self.operation}'.")
                return False

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
