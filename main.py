import json
import os
import uuid
import threading
import time
from datetime import datetime, timedelta

ENTITY_DIR = "entities"
COMPONENT_DIR = "components"
DATA_TRANSFER_DIR = "data_transfers"

os.makedirs(ENTITY_DIR, exist_ok=True)
os.makedirs(COMPONENT_DIR, exist_ok=True)
os.makedirs(DATA_TRANSFER_DIR, exist_ok=True)

# Predefined data and widget types
PREDEFINED_COMPONENT_TYPES = {
    "int": 0,
    "str": "",
    "bool": True,
    "Array_type": {"items": [], "type": ""},
    "Array_generic": {"items": []},
    "GraphWidget": {"type": "graph", "data": []},
}
ACCEPTED_OPERATIONS = {

    "int": ["replace", "add", "subtract", "multiply"],
    "str": ["replace"],
    "bool": ["replace", "toggle"],
    "Array_type": ["replace", "append", "remove_back", "remove_front", "delete_at", "push_at"],
    "Array_generic": ["replace", "append", "remove_back", "remove_front", "delete_at", "push_at"],
}


class Component:
    def __init__(self, name, data=None, id=None, host_entity=None):
        self.name = name
        self.data = data or PREDEFINED_COMPONENT_TYPES.get(name, {})
        self.id = id or str(uuid.uuid4())
        self.host_entity = host_entity

    def is_widget(self):
        """Check if the component is a widget based on predefined types."""
        return isinstance(self.data, dict) and "type" in self.data

    def to_json(self):
        return {
            "name": self.name,
            "id": self.id,
            "data": self.data,
            "host_entity": self.host_entity
        }

    @staticmethod
    def from_json(data):
        return Component(
            name=data["name"],
            data=data["data"],
            id=data["id"],
            host_entity=data["host_entity"]
        )

    def save_to_file(self):
        with open(f"{COMPONENT_DIR}/{self.id}.json", "w") as f:
            json.dump(self.to_json(), f, indent=4)

    def alter_data(self, value):
        if not (self.name.startswith("Array") and isinstance(value, list)) or (self.name not in ["Array_type", "Array_generic"]):
            print(value)
            self.data = value
        else:
            print(value)
            self.data["items"] = value
        self.save_to_file()

    @staticmethod
    def load_from_file(comp_id):
        with open(f"{COMPONENT_DIR}/{comp_id}.json", "r") as f:
            data = json.load(f)
            return Component.from_json(data)


class DataTransfer:
    def __init__(self, source_component=None, target_component=None, data_value=None, operation="replace", details=None, schedule_time=None):
        self.source_component = source_component
        self.target_component = target_component
        self.data_value = data_value  # Unbound data to use if no source_component
        self.operation = operation
        self.schedule_time = schedule_time
        self.details = {}
        self.timestamp = datetime.now().isoformat()

    def execute(self):
        if self.operation not in ACCEPTED_OPERATIONS[self.target_component.name]:
            print(f"Operation '{self.operation}' not supported for component type '{
                  self.tatget_component.name}'.")
            return

        """Perform the data transfer and apply the operation."""
        if self.target_component:
            if isinstance(self.target_component.data, dict):
                target_data = self.target_component.data.get("items")
            else:
                target_data = self.target_component.data

            # Use source component data if available, else use unbound data_value
            source_value = None
            if self.source_component:
                source_value = self.source_component.data
            else:
                source_value = self.data_value

            # type checks
            if self.target_component.name == "Array_generic":
                pass
            elif self.target_component and self.target_component.name.startswith("Array_type") and isinstance(target_data, list):
                if self.source_component and self.source_component.name != self.target_component.data["type"]:
                    print(f"Source and target components must be of the same type.{
                          type(self.data_value).__name__}.")
                    return
            elif (self.source_component is not None) and (self.source_component.name != self.target_component.name or type(source_value).__name__ != self.target_component.name):
                print(f"Source and target components must be of the same type.{
                    type(source_value).__name__}{self.source_component.name}.")
                return
            # by default the remove_front , remove_front don't need source data
            if source_value is not None or self.operation == "remove_back" or self.operation == "remove_front":
                # Perform operations based on type and specified action
                if self.operation == "replace":
                    target_data = source_value
                elif self.operation == "add" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data += source_value
                elif self.operation == "subtract" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data -= source_value
                elif self.operation == "multiply" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data *= source_value
                elif self.operation == "subtract" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data -= source_value
                elif self.operation == "toggle" and isinstance(target_data, bool):
                    target_data = not target_data
                elif self.operation == "append" and isinstance(target_data, list) and (self.target_component.name == "Array_generic" or type(source_value).__name__ == self.target_component.data["type"]):
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
                elif self.operation == "delete_at" and isinstance(target_data, list) and isinstance(source_value, int) and 0 <= source_value < len(target_data):
                    removed = target_data.pop(source_value)
                    if (isinstance(removed, dict)):
                        self.details["removed"] = removed
                elif self.operation == "push_at" and isinstance(target_data, list) and isinstance(source_value, dict) and (self.target_component.name == "Array_generic" or type(source_value).__name__ == self.target_component.data["type"]):
                    index = source_value.get("index")
                    item = source_value.get("item")
                    if isinstance(index, int) and 0 <= index <= len(target_data):
                        target_data.insert(
                            index, {"item": source_value, "id": str(uuid.uuid4())})
                self.target_component.alter_data(target_data)
                return True
            else:
                print(f"Source data not available for operation '{
                      self.operation}'.")
                return False

    def to_json(self):
        return {
            "source_component": self.source_component.id if self.source_component else None,
            "target_component": self.target_component.id if self.target_component else None,
            "data_value": self.data_value,
            "operation": self.operation,
            "schedule_time": self.schedule_time.isoformat() if self.schedule_time else None,
            "details": self.details,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_json(data, entity_manager):
        source_component = entity_manager.get_component(
            data["source_component"]) if data["source_component"] else None
        target_component = entity_manager.get_component(
            data["target_component"]) if data["target_component"] else None
        return DataTransfer(
            source_component=source_component,
            target_component=target_component,
            data_value=data["data_value"],
            operation=data["operation"],
            details=data["details"]
        )

    def save_to_file(self):
        file_name = f"{DATA_TRANSFER_DIR}/{self.timestamp}.json"
        with open(file_name, "w") as f:
            json.dump(self.to_json(), f, indent=4)

    @staticmethod
    def load_from_file(timestamp, entity_manager):
        with open(f"{DATA_TRANSFER_DIR}/{timestamp}.json", "r") as f:
            data = json.load(f)
            return DataTransfer.from_json(data, entity_manager)


class Entity:
    def __init__(self, name, entity_id=None):
        self.entity_id = entity_id or str(uuid.uuid4())
        self.name = name
        self.components = {}

    def add_component(self, component_name):
        if component_name in PREDEFINED_COMPONENT_TYPES:
            component = Component(name=component_name)
            component.host_entity = self.entity_id
            self.components[component.id] = component
            component.save_to_file()
        else:
            print(f"Component type '{component_name}' is not defined.")
        return component

    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def to_json(self):
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "components": list(self.components.keys())
        }

    @staticmethod
    def from_json(data):
        entity = Entity(name=data["name"], entity_id=data["entity_id"])
        for comp_id in data["components"]:
            component = Component.load_from_file(comp_id)
            entity.components[comp_id] = component
        return entity

    def save_to_file(self):
        with open(f"{ENTITY_DIR}/{self.entity_id}.json", "w") as f:
            json.dump(self.to_json(), f, indent=4)

    @staticmethod
    def load_from_file(entity_id):
        with open(f"{ENTITY_DIR}/{entity_id}.json", "r") as f:
            data = json.load(f)
            return Entity.from_json(data)


class EntityManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EntityManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.entities = {}
        self.scheduled_transfers = []

    def create_entity(self, name):
        entity = Entity(name)
        self.entities[entity.entity_id] = entity
        return entity

    def delete_entity(self, entity_id):
        if entity_id in self.entities:
            for entity in self.entities.values():
                for comp in entity.component:
                    os.remove(f"{COMPONENT_DIR}/{Component.id}.json")
            del self.entities[entity_id]
            os.remove(f"{ENTITY_DIR}/{entity_id}.json")

    def get_entity(self, entity_id):
        return self.entities.get(entity_id)

    def get_entity_by_name(self, name):
        for entity in self.entities.values():
            if entity.name == name:
                return entity

    def save_all_entities(self):
        for entity in self.entities.values():
            entity.save_to_file()

    def load_all_entities(self):
        for file_name in os.listdir(ENTITY_DIR):
            if file_name.endswith(".json"):
                entity_id = file_name.split(".json")[0]
                entity = Entity.load_from_file(entity_id)
                self.entities[entity_id] = entity

    def get_component(self, comp_id):
        for entity in self.entities.values():
            component = entity.get_component(comp_id)
            if component:
                return component
        return None


manager = EntityManager()


def time_tracker():
    """Thread to keep track of the current time and execute scheduled transfers."""
    while True:
        current_time = datetime.now()
        for transfer in manager.scheduled_transfers[:]:
            if transfer.schedule_time and current_time >= transfer.schedule_time:
                print(f"Executing scheduled transfer at {current_time}")
                transfer.execute()
                manager.scheduled_transfers.remove(
                    transfer)  # Remove completed transfer
        time.sleep(1)  # Check every second


def user_interaction():
    """Thread to periodically ask the user for new actions: create entities, add components, or data transfers."""
    while True:
        print("\nOptions:")
        print("1. Create a new entity")
        print("2. Add a component to an entity")
        print("3. Create a data transfer")
        print("4. List all entities and components")
        choice = input("Enter choice (1/2/3/4): ").strip()

        if choice == "1":
            # Create a new entity
            entity_name = input("Enter entity name: ").strip()
            entity = manager.create_entity(entity_name)
            entity.save_to_file()
            print(f"Entity '{entity_name}' created with ID: {
                  entity.entity_id}")

        elif choice == "2":
            # Add a component to an entity
            entity_id = input(
                "Enter the ID of the entity to add a component to: ").strip()
            entity = manager.get_entity(entity_id)
            if entity:
                component_name = input(f"Enter component name (options: {
                                       list(PREDEFINED_COMPONENT_TYPES.keys())}): ").strip()
                if component_name in PREDEFINED_COMPONENT_TYPES:
                    if component_name == "Array_type":
                        # Prompt user to define the type of items for Array_type
                        array_item_type = input(f"Enter item type for array (options: {
                                                list(PREDEFINED_COMPONENT_TYPES.keys())}): ").strip()
                        if array_item_type in PREDEFINED_COMPONENT_TYPES:
                            data = {"items": [], "type": array_item_type}
                            component = Component(name="Array_type", data=data)
                            entity.components[component.id] = component
                            component.save_to_file()
                            print(f"Array_type component added with item type '{
                                  array_item_type}' to entity '{entity.name}'.")
                        else:
                            print(f"Invalid item type '{
                                  array_item_type}' for array.")
                            continue
                    component = entity.add_component(component_name)
                    entity.save_to_file()
                    print(f"Component '{component_name}' added to entity '{
                          entity.name}'.")
                else:
                    print(f"Component type '{component_name}' is not defined.")
            else:
                print("Entity not found.")

        elif choice == "3":
            # Create a data transfer
            source_id = input(
                "Enter source component ID (or 'None' if no source): ").strip()
            target_id = input("Enter target component ID: ").strip()
            operation = input(
                "Enter operation type (options: replace, add, subtract, multiply, toggle, append, remove_back, remove_front, delete_at, push_at): ").strip()
            data_value = input(
                "Enter data value (leave empty if not applicable): ").strip()
            delay = int(input(
                "Enter delay (seconds) for this transfer or 0 for immediate execution: ").strip())

            source_component = manager.get_component(
                source_id) if source_id.lower() != "none" else None
            target_component = manager.get_component(target_id)

            if target_component and operation in ACCEPTED_OPERATIONS.get(target_component.name, []):
                parsed_value = None

                # Process data_value based on the type of operation and target component
                if target_component.name.startswith("Array"):
                    if operation == "delete_at" or operation == "push_at":
                        # `delete_at` and `push_at` expect a dictionary with index info
                        try:
                            parsed_value = json.loads(data_value)
                            if operation == "push_at" and not isinstance(parsed_value, dict):
                                raise ValueError(
                                    "push_at operation expects a dictionary with 'index' and 'item'.")
                            elif operation == "delete_at" and not isinstance(parsed_value, int):
                                raise ValueError(
                                    "delete_at operation expects an integer index.")
                        except (json.JSONDecodeError, ValueError):
                            print(f"Invalid data format for operation '{
                                  operation}' on an array.")
                            continue
                    elif operation == "append" and data_value:
                        # `append` expects a single item to add to the array
                        try:
                            parsed_value = json.loads(data_value)
                        except json.JSONDecodeError:
                            print("Invalid JSON format for array append data.")
                            continue
                else:
                    # Non-array components
                    parsed_value = int(
                        data_value) if data_value.isdigit() else data_value

                schedule_time = datetime.now() + timedelta(seconds=delay) if delay > 0 else None
                transfer = DataTransfer(
                    source_component=source_component,
                    target_component=target_component,
                    data_value=parsed_value,
                    operation=operation,
                    schedule_time=schedule_time
                )

                if schedule_time:
                    manager.scheduled_transfers.append(transfer)
                    print(f"Scheduled transfer for '{
                          operation}' at {schedule_time}.")
                else:
                    success = transfer.execute()
                    if success:
                        print(f"Transfer '{operation}' executed immediately.")
            else:
                print("Invalid target component or operation type.")

        elif choice == "4":
            # List all entities and components
            for entity in manager.entities.values():
                print(f"\nEntity ID: {entity.entity_id}, Name: {entity.name}")
                for comp_id, component in entity.components.items():
                    print(f"  Component ID: {comp_id}, Name: {
                          component.name}, Data: {component.data}")

        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")

        time.sleep(5)  # Wait 5 seconds before asking again


def execute_scheduled_transfers():
    """Thread to execute data transfers based on schedule."""
    while True:
        for transfer in manager.scheduled_transfers:
            if transfer.schedule_time and datetime.now() >= transfer.schedule_time:
                print(f"Executing scheduled transfer: {transfer}")
                transfer.execute()
                # Remove executed transfer
                manager.scheduled_transfers.remove(transfer)
        time.sleep(1)  # Check every second


# Example usage
if __name__ == "__main__":
    manager.load_all_entities()

    time_tracker_thread = threading.Thread(target=time_tracker, daemon=True)
    user_interaction_thread = threading.Thread(
        target=user_interaction, daemon=True)
    execute_thread = threading.Thread(
        target=execute_scheduled_transfers, daemon=True)

    time_tracker_thread.start()
    user_interaction_thread.start()
    execute_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting program.")
