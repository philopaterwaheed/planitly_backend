from .component import Component_db
from mongoengine import Document, StringField, DictField, ReferenceField, DateTimeField, NULLIFY
import uuid
from pytz import UTC  # type: ignore
from datetime import datetime

ACCEPTED_OPERATIONS = {

    "int": ["replace", "add", "subtract", "multiply"],
    "str": ["replace"],
    "bool": ["replace", "toggle"],
    "Array_type": ["replace", "append", "remove_back", "remove_front", "delete_at", "push_at"],
    "Array_generic": ["replace", "append", "remove_back", "remove_front", "delete_at", "push_at"],
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


class DataTransfer:
    def __init__(self, id=None, source_component=None, target_component=None, data_value=None, operation="replace", details=None, schedule_time=None):
        self.id = id or str(uuid.uuid4())
        self.source_component = source_component
        self.target_component = target_component
        self.data_value = data_value
        self.operation = operation
        self.schedule_time = schedule_time
        self.details = details or {}
        self.timestamp = datetime.now(UTC).isoformat()

    def execute(self):
        source_component = Component_db.objects(
            id=self.source_component).first() if self.source_component else None
        target_component = Component_db.objects(
            id=self.target_component).first()

        if not target_component or self.operation not in ACCEPTED_OPERATIONS.get(target_component.comp_type, []):
            print(f"Operation '{self.operation}' not supported for component type '{
                  target_component.comp_type}'")
            return False

        target_data = target_component.data.get("items") if isinstance(
            target_component.data, dict) and "items" in target_component.data else target_component.data.get("item")
        source_value = source_component.data if source_component else self.data_value
        if isinstance(source_value, dict) and len(source_value) == 1:
            source_value = list(source_value.values())[0]
        if isinstance(target_data, dict) and len(target_data) == 1:
            target_data = list(target_data.values())[0]

        if self.operation == "replace":
            target_data = source_value
        elif self.operation == "add" and isinstance(target_data, (int, float)):
            target_data += source_value
        elif self.operation == "subtract" and isinstance(target_data, (int, float)):
            target_data -= source_value
        elif self.operation == "multiply" and isinstance(target_data, (int, float)):
            target_data *= source_value
        elif self.operation == "toggle" and isinstance(target_data, bool):
            target_data = not target_data
        elif self.operation in ["append", "remove_back", "remove_front", "delete_at", "push_at"] and isinstance(target_data, list):
            if self.operation == "append":
                target_data.append(
                    {"item": source_value, "id": str(uuid.uuid4())})
            elif self.operation == "remove_back" and target_data:
                self.details["removed"] = target_data.pop()
            elif self.operation == "remove_front" and target_data:
                self.details["removed"] = target_data.pop(0)
            elif self.operation == "delete_at" and isinstance(self.data_value, dict) and "index" in self.data_value:
                index = self.data_value["index"]
                if isinstance(index, int) and 0 <= index < len(target_data):
                    self.details["removed"] = target_data.pop(index)
            elif self.operation == "push_at" and isinstance(self.data_value, dict) and "index" in self.data_value:
                index = self.data_value["index"]
                if isinstance(index, int) and 0 <= index <= len(target_data):
                    target_data.insert(
                        index, {"item": source_value, "id": str(uuid.uuid4())})
        else:
            return False

        if isinstance(target_component.data, dict) and "items" in target_component.data:
            target_component.data["items"] = target_data
        else:
            target_component.data["item"] = target_data

        target_component.save()
        self.details["done"] = True
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
            "timestamp": self.timestamp
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
                data["schedule_time"]) if data.get("schedule_time") else None
        )

    def save_to_db(self):
        data_transfer_db = DataTransfer_db(
            id=self.id,
            source_component=self.source_component,
            target_component=self.target_component,
            data_value=self.data_value,
            operation=self.operation,
            schedule_time=self.schedule_time,
            details=self.details
        )
        data_transfer_db.save()

    @staticmethod
    def load_from_db(transfer_id):
        data_transfer_db = DataTransfer_db.objects(id=transfer_id).first()
        if data_transfer_db:
            return DataTransfer(
                id=data_transfer_db.id,
                source_component=data_transfer_db.source_component,
                target_component=data_transfer_db.target_component,
                data_value=data_transfer_db.data_value,
                operation=data_transfer_db.operation,
                details=data_transfer_db.details,
                schedule_time=data_transfer_db.schedule_time
            )
        return None
