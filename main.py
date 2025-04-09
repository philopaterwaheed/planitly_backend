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
from utils import FilePriorityQueue
import os
from mongoengine import connect, disconnect
from pymongo.errors import PyMongoError


child_pids = []
connections_q = FilePriorityQueue(directory="connections")

app = FastAPI(title="Planitly API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def listen_for_new_connections():
    collection = Connection_db._get_collection()
    try:
        print("inserted")
        with collection.watch([{"$match": {"operationType": "insert"}}]) as stream:
            for change in stream:
                connection_doc = change["fullDocument"]
                print("New Connection Inserted:", connection_doc)
                connections_q.push(connection_doc["end_date"] ,connection_doc["_id"])
    except PyMongoError as e:
        print("Change Stream Error:", e)

def execute_due_connections():
    print("Executing due connections...")
    #todo add try and catch
    while connections_q.peek()[0] < datetime.now():
        print ("Connections Queue:", connections_q.peek()[0] )
        poped = connections_q.pop()
        Connection.load_from_db(poped()[1])
        """     print("Executing:", due_connection) """
        """     print(connections_q.head()) """
            # Your execution logic here
    time.sleep(10)  # Wait a bit if nothing is ready

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
        threading.Thread(target=execute_due_connections, daemon=True).start()
        # should be in this order because watch blocks 
        listen_for_new_connections()
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
