import json
import uuid
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from mongoengine import connect, Document, StringField, ListField, ReferenceField, DateTimeField, DictField, NULLIFY
from mongoengine.errors import DoesNotExist, ValidationError
from bson import json_util
from pytz import UTC


app = Flask(__name__)
connect(db="planitly", host="localhost", port=27017)


class Component_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    host_subject = StringField(required=True)
    data = DictField()
    comp_type = StringField(required=True)
    meta = {'collection': 'components'}


class Subject_db(Document):
    id = StringField(primary_key=True)
    name = StringField(required=True)
    components = ListField(ReferenceField(
        Component_db, reverse_delete_rule=NULLIFY))
    meta = {'collection': 'subjects'}


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
    meta = {'collection': 'data_transfers'}


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
    def __init__(self, name, comp_type, data=None, id=None, host_subject=None):
        self.name = name
        self.comp_type = comp_type
        self.data = data or PREDEFINED_COMPONENT_TYPES.get(name, {})
        self.id = id or str(uuid.uuid4())
        self.host_subject = host_subject

    def is_widget(self):
        """Check if the component is a widget based on predefined types."""
        return isinstance(self.data, dict) and "type" in self.data

    def to_json(self):
        return {
            "name": self.name,
            "id": self.id,
            "type": self.comp_type,
            "data": self.data,
            "host_subject": self.host_subject
        }

    @staticmethod
    def from_json(data):
        return Component(
            name=data["name"],
            data=data["data"],
            id=data["id"],
            comp_type=data["type"],
            host_subject=data["host_subject"]
        )

    def save_to_db(self):
        component_db = Component_db(
            id=self.id,
            name=self.name,
            hostSubject=self.host_subject,
            data=self.data,
            comp_type=self.comp_type
        )
        component_db.save()

    @staticmethod
    def alter_search(id, value):
        component_db = Component_db.objects(id=id).first()
        if not (component_db.comp_type.startswith("Array") and isinstance(value, list)) or (component_db.comp_type not in ["Array_type", "Array_generic"]):
            component_db.data["item"] = value
        else:
            component_db.data["items"] = value
        component_db.save()

    def alter_data(self, value):
        if not (self.comp_type.startswith("Array") and isinstance(value, list)) or (self.comp_type not in ["Array_type", "Array_generic"]):
            print(value)
            self.data["item"] = value
        else:
            print(value)
            self.data["items"] = value
        self.save_to_db()

    @staticmethod
    def load_from_db(comp_id):
        component_db = Component_db.objects(id=comp_id).first()
        if component_db:
            return Component.from_json({
                "name": component_db.name,
                "id": component_db.id,
                "data": component_db.data,
                "type": component_db.comp_type,
                "host_subject": component_db.host_subject
            })
        return None


class DataTransfer:
    def __init__(self, id=None,  source_component=None, target_component=None, data_value=None, operation="replace", details=None, schedule_time=None):
        self.id = id
        self.source_component = source_component
        self.target_component = target_component
        self.data_value = data_value  # Unbound data to use if no source_component
        self.operation = operation
        self.schedule_time = schedule_time
        self.details = {}
        self.timestamp = datetime.now(UTC).isoformat()

    def execute(self):
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
                elif self.operation == "subtract" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data -= source_value
                elif self.operation == "multiply" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data *= source_value
                elif self.operation == "subtract" and isinstance(source_value, (int, float)) and isinstance(target_data, (int, float)):
                    target_data -= source_value
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
                else:
                    return False
                if not (target_component.comp_type.startswith("Array") and isinstance(target_data, list)) or (target_component.comp_type not in ["Array_type", "Array_generic"]):
                    target_component.data["item"] = target_data
                else:
                    target_component.data["items"] = target_data
                target_component.save()
                self.details["done"] = True
                return True
            else:
                print(f"Source data not available for operation '{
                      self.operation}'.")
                return False

    def to_json(self):
        return {
            "id": self.id,
            "source_component": self.source_component.id if self.source_component else None,
            "target_component": self.target_component.id if self.target_component else None,
            "data_value": self.data_value,
            "operation": self.operation,
            "schedule_time": self.schedule_time.isoformat() if self.schedule_time else None,
            "details": self.details,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_json(data, subject_manager):
        id = data.get('id', None)
        source_component = subject_manager.get_component(
            data["source_component"]) if data["source_component"] else None
        target_component = subject_manager.get_component(
            data["target_component"]) if data["target_component"] else None
        return DataTransfer(
            id=id,
            source_component=source_component,
            target_component=target_component,
            data_value=data["data_value"],
            operation=data["operation"],
            details=data["details"]
        )

    def save_to_db(self):
        data_transfer_db = DataTransfer_db(
            id=self.id or str(uuid.uuid4()),
            source_component=self.source_component.id if self.source_component else None,
            target_component=self.target_component.id if self.target_component else None,
            data_value=self.data_value,
            operation=self.operation,
            schedule_time=self.schedule_time,
            details=self.details
        )
        data_transfer_db.save()

    @staticmethod
    def load_from_db(transfer_id, subject_manager):
        data_transfer_db = DataTransfer_db.objects(id=transfer_id).first()
        if data_transfer_db:
            id = data_transfer_db.id
            source_component = subject_manager.get_component(
                data_transfer_db.source_component) if data_transfer_db.source_component else None
            target_component = subject_manager.get_component(
                data_transfer_db.target_source)
            return DataTransfer(
                id=id,
                source_component=source_component,
                target_component=target_component,
                data_value=data_transfer_db.data_value,
                operation=data_transfer_db.operation,
                details=data_transfer_db.details,
                schedule_time=data_transfer_db.schedule_time
            )
        return None


class Subject:
    def __init__(self, name, id=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.components = {}

    def add_component(self, component_name,  component_type):
        if component_type in PREDEFINED_COMPONENT_TYPES:
            component = Component(name=component_name,
                                  comp_type=component_type)
            component.host_subject = self.id
            self.components[component.id] = component
            component.save_to_db()
        else:
            print(f"Component type '{component_type}' is not defined.")
        return component

    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "components": list(self.components.keys())
        }

    @staticmethod
    def from_json(data):
        subject = Subject(name=data["name"], id=data["id"])
        for comp_id in data["components"]:
            component = Component.load_from_file(comp_id)
            subject.components[comp_id] = component
        return subject

    def save_to_db(self):
        subject_db = Subject_db(
            id=self.id,
            name=self.name,
            components=[component.id for component in self.components.values()]
        )
        subject_db.save()

    @staticmethod
    def load_from_db(id):
        try:
            subject_db = Subject_db.objects(id=id).first()
            if subject_db:
                subject = Subject.from_json({
                    "id": subject_db.id,
                    "name": subject_db.name,
                    "components": subject_db.components
                })
                return subject
            else:
                print(f"Subject with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Subject with ID {id} does not exist.")
            return None


class SubjectManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SubjectManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.subjects = {}
        self.scheduled_transfers = []

    def create_subject(self, name):
        subject = Subject(name)
        self.subjects[subject.id] = subject
        return subject

    def get_subject(self, id):
        return self.subjects.get(id)

    def get_subject_by_name(self, name):
        for subject in self.subjects.values():
            if subject.name == name:
                return subject

    def save_all_subjects(self):
        for subject in self.subjects.values():
            subject.save_to_db()

    def get_component(self, comp_id):
        for subject in self.subjects.values():
            component = subject.get_component(comp_id)
            if component:
                return component
        return None

    def load_all_subjects(self):
        subjects_db = Subject_db.objects.all()
        for subject_db in subjects_db:
            subject = Subject.load_from_db(subject_db.id)
            if subject:
                self.subjects[subject.id] = subject


manager = SubjectManager()


def time_tracker():
    """Thread to keep track of the current time and execute scheduled transfers."""
    while True:
        current_time = datetime.now(UTC)
        for transfer in manager.scheduled_transfers[:]:
            if transfer.schedule_time and current_time >= transfer.schedule_time:
                print(f"Executing scheduled transfer at {current_time}")
                transfer.execute()
                manager.scheduled_transfers.remove(
                    transfer)  # Remove completed transfer
        time.sleep(1)  # Check every second


def execute_scheduled_transfers():
    """Thread to execute data transfers based on schedule."""
    while True:
        for transfer in manager.scheduled_transfers:
            if transfer.schedule_time and datetime.now(UTC) >= transfer.schedule_time:
                print(f"Executing scheduled transfer: {transfer}")
                transfer.execute()
                # Remove executed transfer
                manager.scheduled_transfers.remove(transfer)
        time.sleep(1)  # Check every second


# [done]
@app.route('/components', methods=['POST'])
def create_component():
    data = request.json
    if 'id' in data:
        existing_component = Component_db.objects(id=data['id']).first()
        if existing_component:
            return jsonify({"message": "Component with this ID already exists", "id": str(existing_component.id)}), 400

    if 'host_subject' not in data:
        return jsonify({"message": "Host subject is required"}), 400
    host_subject_id = data['host_subject']
    host_subject = Subject_db.objects(id=host_subject_id).first()
    if not host_subject:
        return jsonify({"message": "Host subject not found"}), 404
    if 'comp_type' not in data:
        return jsonify({"message": "Component type is required"}), 400
    component = Component_db(**data)
    component.save()
    return jsonify({"message": "Component created", "id": str(component.id)}), 201


# [done]
@app.route('/subjects', methods=['POST'])
def create_subject():
    data = request.json
    if 'id' in data:
        existing_subject = Subject_db.objects(id=data['id']).first()
        if existing_subject:
            return jsonify({"message": "Subject with this ID already exists", "id": str(existing_subject.id)}), 400
    components = []
    if 'components' in data:
        component_ids = data.pop('components', [])
        components = Component_db.objects.filter(id__in=component_ids)

    subject = Subject_db(**data, components=components)
    subject.save()
    return jsonify({"message": "Subject created", "id": str(subject.id)}), 201


@app.route('/data_transfers', methods=['POST'])
def create_data_transfer():
    try:
        data = request.json
        data_id = data.get('id', None)
        source_component = data['source_component']
        target_component = data['target_component']
        schedule_time = None
        if 'schedule_time' in data and data['schedule_time']:
            try:
                schedule_time = datetime.fromisoformat(
                    data['schedule_time'].replace("Z", "+00:00"))
            except ValueError:
                return jsonify({"error": "Invalid date format for 'schedule_time'"}), 400
        data_transfer = DataTransfer(
            id=data_id,
            source_component=source_component,
            target_component=target_component,
            data_value=data["data_value"],
            operation=data['operation'],
            schedule_time=schedule_time,
            details=data.get('details')
        )
        if schedule_time and datetime.now(UTC) >= schedule_time:
            print("entered")
            success = data_transfer.execute()
            if success:
                return jsonify({"message": "Data transfer executed immediately", "id": str(data_transfer.id)}), 200
            else:
                return jsonify({"error": "Failed to execute data transfer"}), 500
        data_transfer.save_to_db()
        return jsonify({"message": "Data transfer created", "id": str(data_transfer.id)}), 201
    except DoesNotExist as e:
        return jsonify({"error": f"Component not found: {str(e)}"}), 404
    except ValidationError as e:
        return jsonify({"error": f"Validation error: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


# [done]
@app.route('/subjects/<subject_id>', methods=['GET'])
def get_subject(subject_id):
    try:
        subject = Subject_db.objects.get(id=subject_id)
        return jsonify(subject.to_mongo().to_dict()), 200
    except DoesNotExist:
        return jsonify({"error": "Subject not found"}), 404


# [done]
@app.route('/components/<component_id>', methods=['GET'])
def get_component_by_id(component_id):
    try:
        component = Component_db.objects.get(id=component_id)
        return jsonify(component.to_mongo().to_dict()), 200
    except Component_db.DoesNotExist:
        return jsonify({"error": "Component not found"}), 404


@app.route('/data_transfers/<transfer_id>', methods=['GET'])
def get_data_transfer(transfer_id):
    try:
        data_transfer = DataTransfer_db.objects.get(id=transfer_id)
        return jsonify(data_transfer.to_mongo().to_dict()), 200
    except DataTransfer.DoesNotExist:
        return jsonify({"error": "Data transfer not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


# [done]
@app.route('/components', methods=['GET'])
def get_all_components():
    components = Component_db.objects()
    return json.dumps([comp.to_mongo() for comp in components], default=json_util.default), 200


# [done]
@app.route('/subjects', methods=['GET'])
def get_all_subjects():
    subjects = Subject_db.objects()
    return json.dumps([subj.to_mongo() for subj in subjects], default=json_util.default), 200


@app.route('/data_transfers', methods=['GET'])
def get_all_data_transfers():
    data_transfers = DataTransfer_db.objects()
    return json.dumps([dt.to_mongo() for dt in data_transfers], default=json_util.default), 200


@app.route('/subjects/<subject_id>', methods=['DELETE'])
def delete_subject(subject_id):
    try:
        subject = Subject_db.objects.get(id=subject_id)
        for comp in subject.components:
            component = Component_db.objects.get(id=comp.id)
            component.delete()
            print(f"Component {comp.id} deleted.")
        subject.delete()
        return jsonify({"message": f"Subject and associated components with ID {subject_id} deleted successfully."}), 200
    except DoesNotExist:
        return jsonify({"error": "Subject not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


# [done]
@app.route('/components/<component_id>', methods=['DELETE'])
def delete_component(component_id):
    try:
        component = Component_db.objects.get(id=component_id)
        component.delete()  # Deletes the component from the database
        return jsonify({"message": "Component deleted successfully", "id": component_id}), 200
    except DoesNotExist:
        return jsonify({"error": "Component not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/data_transfers/<transfer_id>', methods=['DELETE'])
def delete_data_transfer(transfer_id):
    try:
        data_transfer = DataTransfer_db.objects.get(id=transfer_id)
        data_transfer.delete()  # Deletes the data transfer from the database
        return jsonify({"message": "Data transfer deleted successfully", "id": transfer_id}), 200
    except DoesNotExist:
        return jsonify({"error": "Data transfer not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


def server():
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
    # remove use_reloader=False to run with Threads


# Example usage
if __name__ == "__main__":
    manager.load_all_subjects()

    time_tracker_thread = threading.Thread(target=time_tracker, daemon=True)
    """ user_interaction_thread = threading.Thread( """
    """     target=user_interaction, daemon=True) """
    server_thread = threading.Thread(target=server, daemon=True)
    execute_thread = threading.Thread(
        target=execute_scheduled_transfers, daemon=True)

    time_tracker_thread.start()
    """ user_interaction_thread.start() """
    server_thread.start()
    execute_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting program.")
