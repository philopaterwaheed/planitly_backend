import threading
import time
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from mongoengine.errors import DoesNotExist
from pytz import UTC
from models import User, Component, Subject, Subject_db, DataTransfer, DataTransfer_db, Connection_db, Connection, MONGO_HOST
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routes import subjects, components, auth, dataTransfers, connection, widget
import os
from queue import Queue
from mongoengine import connect, disconnect


child_pids = []
app = FastAPI(title="Planitly API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PythonExecutor:
    def __init__(self):
        """Initialize executor with a thread-safe queue and a running flag."""
        self.task_queue = Queue()

    def fetch_and_execute(self, connection_db):
        """Fetch expired connections and execute transfers in a loop."""
        print("Executor started!")
        while True:
            try:
                now = datetime.now(UTC)
                print(f"Current time: {now.isoformat()}")
                # Fetch expired connections
                expired_connections = connection_db.objects.filter(
                    end_date__lte=now)

                for conn in expired_connections:
                    connection = Connection.load_from_db(conn.id)
                    transfers = conn.data_transfers
                    for transfer_id in transfers:
                        print(transfer_id.id)
                        transfer = DataTransfer.load_from_db(transfer_id.id)
                        if not transfer:
                            print(f"Transfer with ID {transfer_id.id} not found.")
                            continue
                        print(f"Executing data transfer: {transfer}")
                        transfer.execute()  # Execute transfer
                        transfer.save_to_db()  # Save transfer state
                    connection.done = True
                    connection.save_to_db()  # Save connection state
            finally:
                pass

            """ except Exception as e: """
            """     print(f"Error occurred: {e}") """
            # Handle exceptions as needed

            time.sleep(5)  # Check every 5 seconds

    def start(self, connection_db):
        self.fetch_and_execute(connection_db)
        print("Executor fork iss done .")


@app.get("/")
async def home():
    return {"message": "Welcome to the Planitly API!"}


@app.get("/time")
async def get_time():
    return {"time": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "utc": datetime.now(UTC).isoformat()}


@app.get("/api-docs")
async def get_docs():
    return FileResponse("Docs/planitly_Api_docs.html")


@app.on_event("startup")
async def startup_event():
    pid1 = os.fork()
    if pid1 == 0:
        # reloading the database
        # to avoid the deadlock
        # to be fork safe
        disconnect()
        if MONGO_HOST == "localhost":
            connect(db="planitly", host="localhost", port=27017)
        else:
            connect(db="Cluster0", host=MONGO_HOST, port=27017)
        PythonExecutor().start(Connection_db)
        os._exit(0)
    else:
        child_pids.append(pid1)
        print(f"Child process {pid1} started for database connection.")


@app.on_event("shutdown")
async def shutdown_event():
    for pid in child_pids:
        try:
            os.kill(pid, 0)
        except OSError:
            print(f"Child process {pid} is not running.")
        else:
            os.kill(pid, 9)


def run_server():
    """Run FastAPI server."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)


# Registering Routes
app.include_router(subjects.router)
app.include_router(components.router)
app.include_router(auth.router)
app.include_router(connection.router)
app.include_router(dataTransfers.router)
app.include_router(widget.router)


if __name__ == "__main__":
    run_server()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting program.")
