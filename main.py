import threading
import time
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from mongoengine.errors import DoesNotExist
from pytz import UTC
from models import User, Component, Subject, Subject_db, DataTransfer, DataTransfer_db, Connection_db, Connection
from fastapi.middleware.cors import CORSMiddleware
from routes import subjects, components, auth, connection


app = FastAPI(title="Planitly API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


""" @app.route('/data_transfers', methods=['POST']) """
""" @get_current_user """
""" def create_data_transfer(): """
"""     try: """
"""         data = request.json """
"""         data_id = data.get('id', str(uuid.uuid4())) """
"""         source_component = Component_db.objects( """
"""             id=data.get('source_component')).first() """
"""         target_component = Component_db.objects( """
"""             id=data.get('target_component')).first() """
""""""
"""         if not target_component: """
"""             return jsonify({"error": "Target component not found"}), 404 """
""""""
"""         schedule_time = None """
"""         if 'schedule_time' in data and data['schedule_time']: """
"""             try: """
"""                 schedule_time = datetime.fromisoformat( """
"""                     data['schedule_time'].replace("Z", "+00:00")) """
"""             except ValueError: """
"""                 return jsonify({"error": "Invalid date format for 'schedule_time'"}), 400 """
""""""
"""         data_transfer = DataTransfer( """
"""             id=data_id, """
"""             source_component=source_component, """
"""             target_component=target_component, """
"""             data_value=data.get("data_value"), """
"""             operation=data.get("operation"), """
"""             schedule_time=schedule_time, """
"""             details=data.get("details") """
"""         ) """
""""""
"""         if schedule_time and datetime.now(UTC) >= schedule_time: """
"""             if data_transfer.execute(): """
"""                 return jsonify({"message": "Data transfer executed immediately", "id": str(data_transfer.id)}), 200 """
"""             return jsonify({"error": "Failed to execute data transfer"}), 500 """
""""""
"""         data_transfer.save_to_db() """
"""         return jsonify({"message": "Data transfer created", "id": str(data_transfer.id)}), 201 """
"""     except DoesNotExist as e: """
"""         return jsonify({"error": f"Component not found: {str(e)}"}), 404 """
"""     except ValidationError as e: """
"""         return jsonify({"error": f"Validation error: {str(e)}"}), 400 """
"""     except Exception as e: """
"""         return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500 """
""""""


""" @app.get("/data_transfers/{transfer_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user)]) """
""" async def get_data_transfer(transfer_id: str): """
"""Retrieve a data transfer by its ID."""
"""     try: """
"""         data_transfer = DataTransfer_db.objects.get(id=transfer_id) """
"""         return json_util.loads(json_util.dumps(data_transfer.to_mongo())) """
"""     except DoesNotExist: """
"""         raise HTTPException(status_code=404, detail="Data transfer not found") """
"""     except Exception as e: """
"""         raise HTTPException( """
"""             status_code=500, detail=f"An unexpected error occurred: {str(e)}") """
""""""
""""""
""" @app.get("/data_transfers", dependencies=[Depends(get_current_user)], status_code=status.HTTP_200_OK) """
""" async def get_all_data_transfers(): """
"""Retrieve all data transfers."""
"""     data_transfers = DataTransfer_db.objects() """
"""     return json_util.loads(json_util.dumps([dt.to_mongo() for dt in data_transfers])) """
""""""
""""""
""" @app.delete("/data_transfers/{transfer_id}", status_code=status.HTTP_200_OK) """
""" async def delete_data_transfer(transfer_id: str, current_user=Depends(get_current_user)): """
"""Delete a data transfer."""
"""     try: """
"""         data_transfer = DataTransfer_db.objects.get(id=transfer_id) """
"""         data_transfer.delete() """
"""         return {"message": "Data transfer deleted successfully", "id": transfer_id} """
"""     except DoesNotExist: """
"""         raise HTTPException(status_code=404, detail="Data transfer not found") """
"""     except Exception as e: """
"""         raise HTTPException( """
"""             status_code=500, detail=f"An unexpected error occurred: {str(e)}") """
""""""

@app.get("/")
async def home():
    return {"message": "Welcome to the Planitly API!"}


def run_server():
    """Run FastAPI server."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)


# Registering Routes
app.include_router(subjects.router)
app.include_router(components.router)
app.include_router(auth.router)
app.include_router(connection.router)


if __name__ == "__main__":
    manager.load_all_subjects()

    time_tracker_thread = threading.Thread(target=time_tracker, daemon=True)
    execute_thread = threading.Thread(
        target=execute_scheduled_transfers, daemon=True)

    time_tracker_thread.start()
    execute_thread.start()
    run_server()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting program.")
