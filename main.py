import threading

from datetime import datetime
from fastapi import FastAPI
from pytz import UTC
from models import MONGO_HOST
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routes import subjects, components, auth, dataTransfers, connection, widget, notifications , profile, categories , templets , settings , ai_message , home 
import os
import logging
from mongoengine import connect, disconnect
from consts import firebase_urls
import sys
from utils.connections import listen_for_connection_changes, load_pending_connections, execute_due_connections, periodic_sync_connections

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def run_worker():
    """Run the worker process for connection execution."""
    logger.info("Starting Planitly worker process")
    disconnect()
    if MONGO_HOST == "localhost":
        connect(db="planitly", host="localhost", port=27017)
    else:
        connect(db="Cluster0", host=MONGO_HOST, port=27017)

    # Initial load
    load_pending_connections()

    # Start change stream listener in a thread
    listener_thread = threading.Thread(target=listen_for_connection_changes, daemon=True)
    listener_thread.start()

    sync_thread = threading.Thread(target=periodic_sync_connections, daemon=True)
    sync_thread.start()
    logger.info("Worker process started, listening for connection changes...")
    # Start execution loop
    execute_due_connections()


@app.get("/")
async def welcome():
    return {"message": "Welcome to the Planitly API!"}


@app.get("/time")
async def get_time():
    return {"time": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "utc": datetime.now(UTC).isoformat(), "fire": firebase_urls['register']}


@app.get("/api-docs")
async def get_docs():
    return FileResponse("Docs/planitly_Api_docs.html")
def run_server():
    """Run FastAPI server."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)


def is_uvicorn():
    # Uvicorn sets this env variable when running
    return "uvicorn" in sys.argv[0] or "UVICORN_CMD" in os.environ

# Registering Routes
app.include_router(subjects.router)
app.include_router(components.router)
app.include_router(auth.router)
app.include_router(connection.router)
app.include_router(dataTransfers.router)
app.include_router(widget.router)
app.include_router(notifications.router)
app.include_router(profile.router)
app.include_router(categories.router)
app.include_router(templets.router)
app.include_router(settings.router)
app.include_router(ai_message.router)
app.include_router(home.router)


if __name__ == "__main__":
    if is_uvicorn():
        run_server()
    else:
        run_worker()
