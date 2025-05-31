from .component import Component, PREDEFINED_COMPONENT_TYPES
from .subject import Subject, Subject_db
from .dataTransfer import DataTransfer_db, DataTransfer
import uuid
from mongoengine import Document, StringField, DictField, ReferenceField, ListField, DateTimeField, NULLIFY, BooleanField
from mongoengine.errors import DoesNotExist
from datetime import datetime, timezone


class Connection_db(Document):
    id = StringField(primary_key=True)
    source_subject = ReferenceField(Subject_db, required=True)
    target_subject = ReferenceField(Subject_db, required=True)
    con_type = StringField(required=True)
    data_transfers = ListField(ReferenceField(
        DataTransfer_db, reverse_delete_rule=NULLIFY))
    owner = StringField(required=True)  # Store user ID
    start_date = DateTimeField(required=True)
    end_date = DateTimeField(required=True)
    done = BooleanField(default=False, required=True)
    meta = {'collection': 'connections'}


def parse_date(date_val):
    from datetime import timezone
    if isinstance(date_val, str) and date_val:
        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(date_val)
            if dt.tzinfo is None:
                raise ValueError("Date string must include timezone information.")
            return dt.astimezone(timezone.utc)
        except Exception as e:
            print(f"Error parsing date '{date_val}': {e}")
            return None
    elif isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            raise ValueError("Datetime object must be timezone-aware.")
        return date_val.astimezone(timezone.utc)
    return None  # Return None if the date_val is not valid


class Connection:
    def __init__(self, source_subject, target_subject, con_type, data_transfers=None, id=None, owner=None, start_date="", end_date="", done=None):
        self.id = id or str(uuid.uuid4())
        self.source_subject = source_subject
        self.target_subject = target_subject
        self.con_type = con_type
        self.data_transfers = data_transfers or []
        self.owner = owner or source_subject.owner
        self.start_date = parse_date(start_date)
        self.end_date = parse_date(end_date)
        if self.start_date is None or self.end_date is None:
            raise ValueError("start_date and end_date must be provided as timezone-aware ISO strings.")
        self.done = done or False

    async def add_data_transfer(self, source_component, target_component, data_value, operation, details=None):
        data_transfer = DataTransfer(source_component=source_component, target_component=target_component,
                                     data_value=data_value, operation=operation, details=details, owner=self.owner, schedule_time=self.end_date)
        data_transfer.save_to_db()
        self.data_transfers.append(data_transfer.id)

    def to_json(self):
        return {
            "id": self.id,
            "source_subject": self.source_subject.id,
            "target_subject": self.target_subject.id,
            "con_type": self.con_type,
            "data_transfers": self.data_transfers,
            "owner": self.owner,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "done": self.done
        }

    @staticmethod
    def from_json(data):
        connection = Connection(id=data["id"], source_subject=data["source_subject"], target_subject=data["target_subject"],
                                con_type=data["con_type"], owner=data["owner"], start_date=data["start_date"], end_date=data["end_date"], done=data["done"])
        for transfer_id in data["data_transfers"]:
            data_transfer = DataTransfer_db.objects(id=transfer_id).first()
            connection.data_transfers[transfer_id] = data_transfer
        return connection

    def save_to_db(self):
        try:
            connection_db = Connection_db(id=self.id,
                                          source_subject=self.source_subject,
                                          target_subject=self.target_subject,
                                          con_type=self.con_type,
                                          data_transfers=self.data_transfers,
                                          owner=self.owner,
                                          start_date=self.start_date,
                                          end_date=self.end_date,
                                          done=self.done)
            connection_db.save()
        except Exception as e:
            print(f"Error saving connection with ID {self.id} to the database.")
            raise e

    @staticmethod
    def load_from_db(conn_id):
        try:
            print(f"Looking for connection with id: {conn_id} (type: {type(conn_id)})")
            connection_db = Connection_db.objects(id=conn_id).first()
            if connection_db:
                print(type(connection_db.start_date))
                connection = Connection(
                    id=connection_db.id,
                    source_subject=connection_db.source_subject,
                    target_subject=connection_db.target_subject,
                    con_type=connection_db.con_type,
                    data_transfers=connection_db.data_transfers,
                    owner=connection_db.owner,
                    start_date=connection_db.start_date,
                    end_date=connection_db.end_date,
                    done=connection_db.done
                )
                return connection
            else:
                print(f"Connection with ID {conn_id} not found.")
                return None
        except DoesNotExist:
            print(f"Connection with ID {conn_id} does not exist.")
            return None

    @staticmethod
    def from_db(connection_db):
        """
        Create a Connection instance from a Connection_db document.
        """
        if not connection_db:
            return None
        return Connection(
            id=connection_db.id,
            source_subject=connection_db.source_subject,
            target_subject=connection_db.target_subject,
            con_type=connection_db.con_type,
            data_transfers=connection_db.data_transfers,
            owner=connection_db.owner,
            start_date=connection_db.start_date,
            end_date=connection_db.end_date,
            done=connection_db.done
        )

    def execute(self):
        try:
            if self.done:
                return
            for data_transfer in self.data_transfers:
                print(f"Executing data transfer with ID {data_transfer.id}")
                transfer = DataTransfer.load_from_db(data_transfer.id)
                if transfer:
                    if transfer.execute():
                        print(f"Data transfer with ID {data_transfer.id} executed successfully from connection.")
                else:
                    print(f"Data transfer with ID {data_transfer} not found.")
                    raise Exception(
                        f"Data transfer with ID {data_transfer} not found.")
            self.done = True
            self.save_to_db()
        except Exception as e:
            print(f"Error executing connection with ID {self.id}: {e}")
