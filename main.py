import threading
import time
import heapq
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from mongoengine.errors import DoesNotExist
from pytz import UTC
from models import User, Component, Subject, Subject_db, DataTransfer, DataTransfer_db, Connection_db, Connection, MONGO_HOST
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routes import subjects, components, auth, dataTransfers, connection, widget, notifications , profile, categories , templets , settings , ai_message
from routes.settings import router as settings_router
import os
import logging
from mongoengine import connect, disconnect
from consts import firebase_urls


# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

child_pids = []

# Initialize our priority queue using heapq
connection_heap = []
# Dictionary to track connections that are already in the heap
connection_in_heap = set()

app = FastAPI(title="Planitly API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def execute_due_connections():
    """Process connections that are due for execution."""
    logger.info("Starting connection execution service")

    try:
        # Initial load of all pending connections
        load_pending_connections()

        while True:
            try:
                # Check if there are any connections in the heap
                if connection_heap:
                    # Peek at the next connection without removing it
                    next_end_date, _, next_conn_id = connection_heap[0]
                    current_time = datetime.now()

                    if next_end_date <= current_time:
                        # Pop the connection from the heap
                        _, _, conn_id = heapq.heappop(connection_heap)
                        # Remove from tracking set
                        connection_in_heap.discard(conn_id)

                        logger.info(f"Executing connection: {conn_id}")

                        try:
                            Connection.load_from_db(conn_id).execute()
                        except DoesNotExist:
                            logger.error(
                                f"Connection {conn_id} not found in database")
                        except Exception as e:
                            logger.error(f"Failed to execute connection {
                                         conn_id}: {e}")
                    else:
                        # Calculate sleep time until next connection
                        sleep_seconds = min(
                            (next_end_date - current_time).total_seconds(),
                            30  # Maximum sleep time of 30 seconds
                        )
                        time.sleep(max(1, sleep_seconds))
                else:
                    # If heap is empty, reload connections and wait
                    logger.info(
                        "Connection heap empty, reloading pending connections")
                    load_pending_connections()
                    time.sleep(30)

                # Periodically reload connections to catch any new ones
                if datetime.now().second % 60 == 0:  # Once every minute
                    load_pending_connections()

            except Exception as e:
                logger.error(f"Error in connection execution loop: {e}")
                time.sleep(10)

    except Exception as e:
        logger.error(f"Fatal error in execute_due_connections: {e}")


def load_pending_connections():
    """Load pending connections from database into the heap."""
    try:
        # Get connections that are not done and end_date is now or in the past
        current_time = datetime.now()
        pending_connections = Connection_db.objects(
            done=False,
            end_date__lte=current_time
        )

        # Add immediate connections to heap
        for conn in pending_connections:
            add_to_heap(conn)

        # Also get future connections that will execute soon (next 5 minutes)
        future_time = current_time + timedelta(minutes=5)
        future_connections = Connection_db.objects(
            done=False,
            end_date__gt=current_time,
            end_date__lte=future_time
        )

        # Add future connections to heap
        for conn in future_connections:
            add_to_heap(conn)

    except Exception as e:
        logger.error(f"Error loading pending connections: {e}")


def add_to_heap(connection):
    """Add a connection to the heap if it's not already there."""
    conn_id = str(connection.id)
    if conn_id not in connection_in_heap:
        # Use a counter as a tiebreaker for connections with the same end_date
        # This ensures stable sorting even when end_dates are identical
        counter = len(connection_heap)
        heapq.heappush(connection_heap,
                       (connection.end_date, counter, conn_id))
        connection_in_heap.add(conn_id)
        logger.info(f"Added connection {conn_id} to heap, scheduled for {
                    connection.end_date}")


@app.get("/")
async def home():
    return {"message": "Welcome to the Planitly API!"}


@app.get("/time")
async def get_time():
    return {"time": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "utc": datetime.now(UTC).isoformat(), "fire": firebase_urls['register']}


@app.get("/api-docs")
async def get_docs():
    return FileResponse("Docs/planitly_Api_docs.html")


@app.on_event("startup")
async def startup_event():
    pid1 = os.fork()
    if pid1 == 0:
        # Reloading the database connection to be fork safe
        disconnect()
        if MONGO_HOST == "localhost":
            connect(db="planitly", host="localhost", port=27017)
        else:
            connect(db="Cluster0", host=MONGO_HOST, port=27017)

        # Start the connection execution service
        execute_due_connections()
        os._exit(0)
    else:
        child_pids.append(pid1)
        logger.info(f"Child process {pid1} started for connection execution.")


@app.on_event("shutdown")
async def shutdown_event():
    for pid in child_pids:
        try:
            os.kill(pid, 0)
        except OSError:
            logger.warning(f"Child process {pid} is not running.")
        else:
            os.kill(pid, 9)
            logger.info(f"Terminated child process {pid}.")


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
app.include_router(notifications.router)
app.include_router(profile.router)
app.include_router(categories.router)
app.include_router(templets.router)
app.include_router(settings.router)
app.include_router(ai_message.router)

if __name__ == "__main__":
    run_server()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Exiting program.")
