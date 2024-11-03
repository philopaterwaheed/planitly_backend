import json
import os
import uuid
from datetime import datetime

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
    "Array_generic": [],
    "GraphWidget": {"type": "graph", "data": []},
    "ToggleSwitchWidget": {"type": "toggle", "state": True}
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
        """Update the data value for a specific key."""
        self.data = value
        self.save_to_file()

    @staticmethod
    def load_from_file(comp_id):
        with open(f"{COMPONENT_DIR}/{comp_id}.json", "r") as f:
            data = json.load(f)
            return Component.from_json(data)


class DataTransfer:
    def __init__(self, source_component=None, target_component=None, data_value=None, operation="replace"):
        self.source_component = source_component
        self.target_component = target_component
        self.data_value = data_value  # Unbound data to use if no source_component
        self.operation = operation
        self.timestamp = datetime.now().isoformat()

    def execute(self):
        if self.operation not in ACCEPTED_OPERATIONS[self.target_component.name]:
            print(f"Operation '{self.operation}' not supported for component type '{
                  self.tatget_component.name}'.")
            return

        """Perform the data transfer and apply the operation."""
        if self.target_component:
            target_data = self.target_component.data

            # Use source component data if available, else use unbound data_value
            source_value = None
            if self.source_component:
                source_value = self.source_component.data
            else:
                source_value = self.data_value

            if self.source_component and self.source_component.name != self.target_component.name or type(source_value).__name__ != self.target_component.name:
                print(f"Source and target components must be of the same type.")
                return
            if isinstance(target_data, list):
                if self.source_component and type(target_data).__name__ != self.source_component.data["type"]:
                    print(f"Source and target components must be of the same type.")
                    return
            if source_value is not None:
                # Perform operations based on type and specified action
                if self.operation == "replace":
                    if self.source_component.name == self.target_component.name:
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
                elif self.operation == "append" and isinstance(target_data, list) and type(target_data).__name__ == self.source_component.data["type"]:
                    target_data.append(self.data_value)
                elif self.operation == "remove_back" and isinstance(target_data, list) and target_data and type(target_data).__name__ == self.source_component.data["type"]:
                    target_data.pop()
                elif self.operation == "remove_front" and isinstance(target_data, list) and target_data and type(target_data).__name__ == self.source_component.data["type"]:
                    target_data.pop(0)
                elif self.operation == "delete_at" and isinstance(target_data, list) and isinstance(self.data_value, int) and 0 <= self.data_value < len(target_data) and type(target_data).__name__ == self.source_component.data["type"]:
                    target_data.pop(self.data_value)
                elif self.operation == "push_at" and isinstance(target_data, list) and isinstance(self.data_value, dict) and type(target_data).__name__ == self.source_component.data["type"]:
                    index = self.data_value.get("index")
                    item = self.data_value.get("item")
                    if isinstance(index, int) and 0 <= index <= len(target_data):
                        target_data.insert(index, item)

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
            operation=data["operation"]
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
        entity = Entity(data["entity_id"])
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


# Example usage
if __name__ == "__main__":
    manager = EntityManager()

    entity1 = manager.create_entity("notPhilo")
    entity2 = manager.create_entity("philo")
    comp1 = entity1.add_component("int")
    comp2 = entity2.add_component("str")
    comp3 = entity2.add_component("bool")
    transaction = DataTransfer(
        data_value=False, target_component=comp3, operation="toggle")
    transaction.execute()
    transaction.save_to_file()
    transaction = DataTransfer(
        data_value="hello", target_component=comp1, operation="add")
    transaction.execute()
    transaction.save_to_file()

    manager.save_all_entities()
    manager.load_all_entities()
    loaded_entity1 = manager.get_entity(entity1.entity_id)
    loaded_entity2 = manager.get_entity(entity2.entity_id)
    print(f"Loaded entity {loaded_entity1.entity_id} with components: {
          list(loaded_entity1.components.keys())}")
    print(f"Loaded entity {loaded_entity2.entity_id} with components: {
          list(loaded_entity2.components.keys())}")
