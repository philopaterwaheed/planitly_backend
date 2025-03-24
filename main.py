import threading
import time
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from mongoengine.errors import DoesNotExist
from pytz import UTC
from models import User, Component, Subject, Subject_db, DataTransfer, DataTransfer_db
from fastapi.middleware.cors import CORSMiddleware
from routes import subjects, components, auth, dataTransfers


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
app.include_router(dataTransfers.router)

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
