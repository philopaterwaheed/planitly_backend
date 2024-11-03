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

class Component:
    def __init__(self, name, comp_type, data=None, id=None, host_entity=None):
        self.name = name
        self.comp_type = comp_type
        self.data = data or {}
        self.id = id or str(uuid.uuid4())
        self.host_entity = host_entity

    def to_json(self):
        return {
            "name": self.name,
            "id": self.id,
            "comp_type": self.comp_type,
            "data": self.data,
            "host_entity": self.host_entity
        }

    @staticmethod
    def from_json(data):
        return Component(
            name=data["name"],
            comp_type=data["comp_type"],
            data=data["data"],
            id=data["id"],
            host_entity=data["host_entity"]
        )

    def save_to_file(self):
        with open(f"{COMPONENT_DIR}/{self.id}.json", "w") as f:
            json.dump(self.to_json(), f, indent=4)

    @staticmethod
    def load_from_file(comp_id):
        with open(f"{COMPONENT_DIR}/{comp_id}.json", "r") as f:
            data = json.load(f)
            return Component.from_json(data)

class DataTransfer:
    def __init__(self, source_component, target_component, data_key, data_value, data_type=None, operation="replace"):
        self.source_component = source_component
        self.target_component = target_component
        self.data_key = data_key
        self.data_value = data_value
        self.data_type = data_type or type(data_value).__name__
        self.operation = operation
        self.timestamp = datetime.now().isoformat()

    def to_json(self):
        return {
            "source_component": self.source_component,
            "target_component": self.target_component,
            "data_key": self.data_key,
            "data_value": self.data_value,
            "data_type": self.data_type,
            "operation": self.operation,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_json(data):
        return DataTransfer(
            source_component=data["source_component"],
            target_component=data["target_component"],
            data_key=data["data_key"],
            data_value=data["data_value"],
            data_type=data["data_type"],
            operation=data["operation"]
        )

    def save_to_file(self):
        file_name = f"{DATA_TRANSFER_DIR}/{self.timestamp}.json"
        with open(file_name, "w") as f:
            json.dump(self.to_json(), f, indent=4)

    @staticmethod
    def load_from_file(timestamp):
        with open(f"{DATA_TRANSFER_DIR}/{timestamp}.json", "r") as f:
            data = json.load(f)
            return DataTransfer.from_json(data)

class Entity:
    def __init__(self, entity_id=None):
        self.entity_id = entity_id or str(uuid.uuid4())
        self.components = {}

    def add_component(self, component):
        self.components[component.id] = component
        component.save_to_file()

    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def to_json(self):
        return {
            "entity_id": self.entity_id,
            "components": list(self.components.keys())
        }

    @staticmethod
    def from_json(data):
        entity = Entity(data["entity_id"])
        for comp_id in data["components"]:
            component = Component.load_from_file(comp_id)
            entity.add_component(component)
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
    def __init__(self):
        self.entities = {}

    def create_entity(self):
        entity = Entity()
        self.entities[entity.entity_id] = entity
        return entity

    def delete_entity(self, entity_id):
        if entity_id in self.entities:
            del self.entities[entity_id]
            os.remove(f"{ENTITY_DIR}/{entity_id}.json")

    def get_entity(self, entity_id):
        return self.entities.get(entity_id)

    def save_all_entities(self):
        for entity in self.entities.values():
            entity.save_to_file()

    def load_all_entities(self):
        for file_name in os.listdir(ENTITY_DIR):
            if file_name.endswith(".json"):
                entity_id = file_name.split(".json")[0]
                entity = Entity.load_from_file(entity_id)
                self.entities[entity_id] = entity

    def transfer_data(self, source_entity, target_entity, source_comp_id, target_comp_id, data_key, operation="replace"):
        source_component = source_entity.get_component(source_comp_id)
        target_component = target_entity.get_component(target_comp_id)

        if source_component and target_component:
            data_value = source_component.data.get(data_key)
            if data_value is not None:
                transfer = DataTransfer(
                    source_component=source_comp_id,
                    target_component=target_comp_id,
                    data_key=data_key,
                    data_value=data_value,
                    operation=operation
                )
                transfer.save_to_file()

                if operation == "replace":
                    target_component.data[data_key] = data_value
                elif operation == "add" and isinstance(data_value, (int, float)):
                    target_component.data[data_key] = target_component.data.get(data_key, 0) + data_value
                elif operation == "append" and isinstance(data_value, list):
                    target_component.data.setdefault(data_key, []).extend(data_value)
                
                print(f"Data transferred from {source_comp_id} to {target_comp_id}: {data_key} = {data_value}")

# Example usage
if __name__ == "__main__":
    manager = EntityManager()

    # Create two entities with components
    entity1 = manager.create_entity()
    position = Component("Position", "Spatial", {"x": 10, "y": 20})
    entity1.add_component(position)

    entity2 = manager.create_entity()
    health = Component("Health", "Stats", {"current": 100, "max": 100})
    entity2.add_component(health)

    # Demonstrate data transfer between components of different entities
    print("Before transfer:", health.data)
    manager.transfer_data(entity1, entity2, position.id, health.id, "x", "replace")
    print("After transfer:", health.data)

    # Save all entities and load them
    manager.save_all_entities()
    print(f"Entities saved with components: {list(entity1.components.keys())}, {list(entity2.components.keys())}")

    # Load all entities from files
    manager.load_all_entities()
    loaded_entity1 = manager.get_entity(entity1.entity_id)
    loaded_entity2 = manager.get_entity(entity2.entity_id)
    print(f"Loaded entity {loaded_entity1.entity_id} with components: {list(loaded_entity1.components.keys())}")
    print(f"Loaded entity {loaded_entity2.entity_id} with components: {list(loaded_entity2.components.keys())}")
