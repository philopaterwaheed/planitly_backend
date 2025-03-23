import json
import uuid
import threading
import time
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session
from flask_jwt_extended import JWTManager, create_access_token, verify_jwt_in_request, get_jwt_identity
from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError  # type: ignore
from bson import json_util
from pytz import UTC  # type: ignore
import os
from dotenv import load_dotenv
from middleWares import login_required, admin_required
from models import User, Component, Component_db, Subject, Subject_db, DataTransfer, DataTransfer_db

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
jwt = JWTManager(app)


class SubjectManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SubjectManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'subjects'):
            self.subjects = {}
        if not hasattr(self, 'scheduled_transfers'):
            self.scheduled_transfers = []

    def create_subject(self, name):
        subject = Subject(name)
        self.subjects[subject.id] = subject
        return subject

    def get_subject(self, id):
        return self.subjects.get(id)

    def get_subject_by_name(self, name):
        return next((subject for subject in self.subjects.values() if subject.name == name), None)

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
        current_time = datetime.now(UTC)
        pending_transfers = [
            t for t in manager.scheduled_transfers if t.schedule_time and current_time >= t.schedule_time]
        for transfer in pending_transfers:
            print(f"Executing scheduled transfer: {transfer}")
            transfer.execute()
            manager.scheduled_transfers.remove(
                transfer)  # Remove executed transfer
        time.sleep(1)  # Check every second

# [done]


@app.route('/components', methods=['POST'])
@login_required
def create_component():
    data = request.json
    # check if the component already exists
    if 'id' in data and Component.load_from_db(data['id']):
        return jsonify({"message": "Component with this ID already exists"}), 400

    # check if the host subject id exists
    if 'host_subject' not in data:
        return jsonify({"message": "Host subject is required"}), 400

    # check if the host subject exists
    host_subject = Subject.load_from_db(data['host_subject'])
    if not host_subject:
        return jsonify({"message": "Host subject not found"}), 404

    if 'comp_type' not in data:
        return jsonify({"message": "Component type is required"}), 400

    component = Component(**data, owner=request.user_id)
    component.save_to_db()
    host_subject.components.append(component.id)
    host_subject.save_to_db()
    return jsonify({"message": "Component created", "id": str(component.id)}), 201


# create a new subject route
@app.route('/subjects', methods=['POST'])
@login_required
def create_subject():
    data = request.json
    if 'id' in data and Subject_db.objects(id=data['id']).first():
        return jsonify({"message": "Subject with this ID already exists"}), 400

    if data.get('template'):
        # todo create a subject from a template
        pass
    # create a new subject from data and save it
    subject = Subject(**data, owner=request.user_id)
    subject.save_to_db()
    return jsonify({"message": "Subject created", "id": str(subject.id)}), 201


@app.route('/data_transfers', methods=['POST'])
@login_required
def create_data_transfer():
    try:
        data = request.json
        data_id = data.get('id', str(uuid.uuid4()))
        source_component = Component_db.objects(
            id=data.get('source_component')).first()
        target_component = Component_db.objects(
            id=data.get('target_component')).first()

        if not target_component:
            return jsonify({"error": "Target component not found"}), 404

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
            data_value=data.get("data_value"),
            operation=data.get("operation"),
            schedule_time=schedule_time,
            details=data.get("details")
        )

        if schedule_time and datetime.now(UTC) >= schedule_time:
            if data_transfer.execute():
                return jsonify({"message": "Data transfer executed immediately", "id": str(data_transfer.id)}), 200
            return jsonify({"error": "Failed to execute data transfer"}), 500

        data_transfer.save_to_db()
        return jsonify({"message": "Data transfer created", "id": str(data_transfer.id)}), 201
    except DoesNotExist as e:
        return jsonify({"error": f"Component not found: {str(e)}"}), 404
    except ValidationError as e:
        return jsonify({"error": f"Validation error: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/subjects/<subject_id>', methods=['GET'])
@login_required
def get_subject(subject_id):
    try:
        subject = Subject_db.objects.get(id=subject_id)
        return jsonify(subject.to_mongo().to_dict()), 200
    except DoesNotExist:
        return jsonify({"error": "Subject not found"}), 404


@app.route('/components/<component_id>', methods=['GET'])
@login_required
def get_component_by_id(component_id):
    try:
        component = Component_db.objects.get(id=component_id)
        return jsonify(component.to_mongo().to_dict()), 200
    except DoesNotExist:
        return jsonify({"error": "Component not found"}), 404


@app.route('/data_transfers/<transfer_id>', methods=['GET'])
@login_required
def get_data_transfer(transfer_id):
    try:
        data_transfer = DataTransfer_db.objects.get(id=transfer_id)
        return jsonify(data_transfer.to_mongo().to_dict()), 200
    except DoesNotExist:
        return jsonify({"error": "Data transfer not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/components', methods=['GET'])
@login_required
@admin_required
def get_all_components():
    components = Component_db.objects()
    return json.dumps([comp.to_mongo() for comp in components], default=json_util.default), 200


# get all subjects route
@app.route('/subjects', methods=['GET'])
@login_required
@admin_required
def get_all_subjects():
    subjects = Subject_db.objects()
    return json.dumps([subj.to_mongo() for subj in subjects], default=json_util.default), 200


# get by User_id subjects route
@app.route('/subjects/user/<user_id>', methods=['GET'])
@login_required
def get_user_subjects(user_id):
    # if the user is the owner or an admin, return all subjects under user
    if request.user_id == user_id or request.user.admin:
        subjects = Subject_db.objects(owner=user_id)
        return json.dumps([subj.to_mongo() for subj in subjects], default=json_util.default), 200
    subjects = Subject_db.objects()
    return json.dumps([subj.to_mongo() for subj in subjects], default=json_util.default), 200


@app.route('/data_transfers', methods=['GET'])
@login_required
def get_all_data_transfers():
    data_transfers = DataTransfer_db.objects()
    return json.dumps([dt.to_mongo() for dt in data_transfers], default=json_util.default), 200


@app.route('/subjects/<subject_id>', methods=['DELETE'])
@login_required
def delete_subject(subject_id):
    try:
        subject = Subject_db.objects.get(id=subject_id)
        if request.user_id == subject.owner or request.user.admin:
            for comp in subject.components:
                comp.delete()
            subject.delete()
            return jsonify({"message": f"Subject and associated components with ID {subject_id} deleted successfully."}), 200
    except DoesNotExist:
        return jsonify({"error": "Subject not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/components/<component_id>', methods=['DELETE'])
@login_required
def delete_component(component_id):
    try:
        # Find and delete the component
        component = Component_db.objects.get(id=component_id)
        if request.user_id == component.owner or request.user.admin:
            component_host_subject = component.host_subject  # Get the host subject ID

            # Find the hosting subject and remove the component ID from the components list
            subject = Subject.load_from_db(component_host_subject.id)
            print(subject.components)
            subject.components.remove(component_id)
            subject.save_to_db()
            component.delete()

        return jsonify({"message": "Component deleted successfully", "id": component_id}), 200
    except DoesNotExist:
        return jsonify({"error": "Component or Subject not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/data_transfers/<transfer_id>', methods=['DELETE'])
@login_required
def delete_data_transfer(transfer_id):
    try:
        data_transfer = DataTransfer_db.objects.get(id=transfer_id)
        # delete the data transfer from data_base
        data_transfer.delete()
        return jsonify({"message": "Data transfer deleted successfully", "id": transfer_id}), 200
    except DoesNotExist:
        return jsonify({"error": "Data transfer not found"}), 404
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.json
        if not data:
            return jsonify({"message": "Invalid request", "status": "error"}), 400
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        if not username or not email or not password:
            return jsonify({"message": "All fields are required", "status": "error"}), 400

        if not re.match(r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&^#_+=<>.,;:|\\/-])[A-Za-z\d@$!%*?&^#_+=<>.,;:|\\/-]{8,}$", password):
            return jsonify({"message": "Password must be at least 8 characters long, with one uppercase letter, one number, and one special character.", "status": "error"}), 400

        user = User(id=str(uuid.uuid4()), username=username,
                    email=email, password=password)
        user.hash_password()
        user.save()

        # Generate JWT token
        access_token = create_access_token(identity=str(user.id))

        return jsonify({
            "message": "User registered successfully",
            "token": access_token
        }), 201

    except ValidationError:
        return jsonify({"message": "Invalid data", "status": "error"}), 400
    except NotUniqueError:
        return jsonify({"message": "Username or Email already exist", "status": "error"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")

        # Check if user exists
        user = User.objects(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({"error": "Invalid credentials"}), 401

        # Generate JWT token
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={"admin": user.admin},
            expires_delta=timedelta(days=30)
        )

        return jsonify({
            "message": "Login successful",
            "token": access_token
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Welcome to the Planitly API!"}), 200


def server():
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)


if __name__ == "__main__":
    manager.load_all_subjects()

    time_tracker_thread = threading.Thread(target=time_tracker, daemon=True)
    server_thread = threading.Thread(target=server, daemon=True)
    execute_thread = threading.Thread(
        target=execute_scheduled_transfers, daemon=True)

    time_tracker_thread.start()
    server_thread.start()
    execute_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting program.")
