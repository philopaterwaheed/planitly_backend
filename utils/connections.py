import time
from datetime import datetime, timedelta
from pytz import UTC
from models import Connection_db, Connection, MONGO_HOST
import os
import logging
from .file_priority_queue import FilePriorityQueue
import tempfile
import threading
from dateutil import parser as date_parser
import pytz

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

queue_dir = os.path.join(tempfile.gettempdir(), "planitly_queue")
connection_queue = FilePriorityQueue(directory=queue_dir, max_memory_items=100)


def execute_due_connections():
    """Process connections that are due for execution."""
    logger.info("Starting connection execution service")

    try:
        # Initial load of all pending connections (including far future ones)
        load_pending_connections()
        
        while True:
            try:
                item = connection_queue.peek()
                current_time = datetime.now(UTC)
                # Pop and process all due connections
                while item:
                    next_end_date, conn_id = item
                    if next_end_date.tzinfo is None:
                        next_end_date = next_end_date.replace(tzinfo=UTC)
                    if next_end_date <= current_time:
                        _, conn_id = connection_queue.pop()
                        logger.info(f"Executing connection: {conn_id}")
                        try:
                            connection = Connection_db.objects(id=conn_id).first()
                            connection_to_exec = Connection.from_db(connection)
                            if not connection_to_exec:
                                logger.error(f"Connection {conn_id} not found in database")
                                item = connection_queue.peek()
                                continue
                            connection_to_exec.execute()
                            logger.info(f"Connection {conn_id} executed successfully")
                        except Exception as e:
                            logger.error(f"Failed to execute connection {conn_id}: {e}")
                        item = connection_queue.peek()
                        current_time = datetime.now(UTC)
                    else:
                        break
                # If no due connections, sleep until the next one or a short interval
                if item:
                    next_end_date, _ = item
                    sleep_seconds = min((next_end_date - current_time).total_seconds(), 30)
                    time.sleep(max(1, sleep_seconds))
                else:
                    logger.info("Connection queue empty, waiting for new connections")
                    time.sleep(10)
            except Exception as e:
                logger.error(f"Error in connection execution loop: {e}")
                time.sleep(10)
    except Exception as e:
        logger.error(f"Fatal error in execute_due_connections: {e}")

def listen_for_connection_changes():
    """Listen for new/updated connections and add them to the queue."""
    from pymongo import MongoClient
    import bson

    # Use pymongo for change streams
    if MONGO_HOST == "localhost":
        client = MongoClient(host="localhost", port=27017)
        db = client["planitly"]
    else:
        client = MongoClient(host=MONGO_HOST, port=27017)
        db = client["Cluster0"]

    collection = db["connections"]

    logger.info("Listening for connection changes...")
    try:
        with collection.watch(
            [{"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}],
            full_document='updateLookup'
        ) as stream:
            for change in stream:
                try:
                    doc = change.get("fullDocument")
                    if doc and not doc.get("done", False):
                        print (f"Change detected: {doc}")
                        end_date = doc.get("end_date")
                        # Always parse and convert to UTC
                        if isinstance(end_date, str):
                            dt = date_parser.parse(end_date)
                            if dt.tzinfo is None:
                                end_date = pytz.UTC.localize(dt)
                            else:
                                end_date = dt.astimezone(pytz.UTC)
                        elif isinstance(end_date, bson.datetime.datetime):
                            if end_date.tzinfo is None:
                                end_date = end_date.replace(tzinfo=UTC)
                            else:
                                end_date = end_date.astimezone(UTC)
                        now = datetime.now(UTC)
                        five_minutes_later = now + timedelta(minutes=5)
                        if end_date <= five_minutes_later:
                            doc_id = doc.get("id", doc.get("_id"))
                            connection_queue.push(end_date, str(doc_id))
                            logger.info(f"Queued new/updated connection {doc_id} for {end_date}")
                        else:
                            logger.info(f"Ignored connection with end_date {end_date} (more than 5 minutes in the future)")
                except Exception as e:
                    logger.error(f"Error processing change stream event: {e}")
    except Exception as e:
        logger.error(f"Change stream listener stopped: {e}")


def load_pending_connections():
    """Load pending connections from database into the file-based queue."""
    try:
        current_time = datetime.now(UTC)
        pending_connections = Connection_db.objects(
            done=False,
            end_date__lte=current_time
        )
        for conn in pending_connections:
            connection_queue.push(conn.end_date, str(conn.id))
        # Also add near-future connections
        future_time = current_time + timedelta(minutes=5)
        future_connections = Connection_db.objects(
            done=False,
            end_date__gt=current_time,
            end_date__lte=future_time
        )
        for conn in future_connections:
            connection_queue.push(conn.end_date, str(conn.id))
    except Exception as e:
        logger.error(f"Error loading pending connections: {e}")


def add_to_queue(connection):
    """Add a connection to the queue if it's not already there."""
    conn_id = str(connection.id)
    connection_queue.push(
        (connection.end_date, 0, conn_id))
    logger.info(f"Added connection {conn_id} to queue, scheduled for {connection.end_date}")

def periodic_sync_connections():
    """Periodically sync all connections with end_date in the next 5 minutes."""
    time.sleep(5 * 60)  # Initial delay
    while True:
        try:
            logger.info("Running periodic connection sync...")
            start_time = datetime.now(UTC)
            end_time = start_time + timedelta(minutes=5)
            # Fetch connections with end_date in the next 5 minutes and not done
            upcoming_connections = Connection_db.objects(
                done=False,
                end_date__gt=start_time,
                end_date__lte=end_time
            )
            synced_count = 0
            for conn in upcoming_connections:
                connection_queue.push(conn.end_date, str(conn.id))
                synced_count += 1
            logger.info(f"Periodic sync completed: {synced_count} connections processed")
            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            sleep_time = max(0, 5 * 60 - elapsed)
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"Error in periodic sync: {e}")
            time.sleep(60)  # Wait 1 minute on error
