from .component import Component, PREDEFINED_COMPONENT_TYPES
from .subject import Subject, Subject_db
from .dataTransfer import DataTransfer_db, DataTransfer
import uuid
from mongoengine import Document, StringField, DictField, ReferenceField, ListField, DateTimeField, NULLIFY
from mongoengine.errors import DoesNotExist


class Connection_db(Document):
    id = StringField(primary_key=True)
    source_subject = ReferenceField(Subject_db, required=True)
    target_subject = ReferenceField(Subject_db, required=True)
    type = StringField(required=True)
    data_tarnsfers = ListField(ReferenceField(
        DataTransfer_db, reverse_delete_rule=NULLIFY))
    owner = StringField(required=True)  # Store user ID
    start_date = DateTimeField()
    end_date = DateTimeField()
    meta = {'collection': 'connections'}


class Connection:
    def __init__(self, source_subject, target_subject, con_type, id=None, owner=None, start_date=None, end_date=None):
        self.id = id or str(uuid.uuid4())
        self.source_subject = source_subject
        self.target_subject = target_subject
        self.type = con_type
        data_transfers = {}
        self.owner = owner or source_subject.owner
        self.start_date = start_date or None
        self.end_date = end_date or None

    def add_data_tranfer(self, data_transfer_id):
        if data_transfer_id not in self.data_transfers:
            self.data_transfers[data_transfer_id] = DataTransfer.load_from_db(
                data_transfer_id)
            return True
        return False

    def to_json(self):
        return {
            "id": self.id,
            "source_subject": self.source_subject.id,
            "target_subject": self.target_subject.id,
            "type": self.type,
            "data_transfers": self.data_transfers,
            "owner": self.owner,
            "start_date": self.start_date,
            "end_date": self.end_date
        }

    @staticmethod
    def from_json(data):
        connection = Connection(id=data["id"], source_subject=data["source_subject"], target_subject=data["target_subject"],
                                type=data["type"], owner=data["owner"], start_date=data["start_date"], end_date=data["end_date"])
        for transfer_id in data["data_transfers"]:
            data_transfer = DataTransfer_db.objects(id=transfer_id).first()
            connection.data_transfers[transfer_id] = data_transfer
        return connection

    def save_to_db(self):
        connection_db = Connection_db(id=self.id,
                                      source_subject=self.source_subject,
                                      target_subject=self.target_subject,
                                      type=self.type,
                                      data_transfers=[
                                          data_transfer.id for data_transfer in self.data_transfers.values()],
                                      owner=self.owner,
                                      start_date=self.start_date,
                                      end_date=self.end_date)
        connection_db.save()

    @staticmethod
    def load_from_db(id):
        try:
            connection_db = Connection_db .objects(id=id).first()
            if connection_db:
                connection = Connection.from_json({
                    "id": connection_db.id,
                    "source_subject": connection_db.source_subject,
                    "target_subject": connection_db.target_subject,
                    "type": connection_db.type,
                    "data_transfers": connection_db.data_transfers,
                    "owner": connection_db.owner,
                    "start_date": connection_db.start_date,
                    "end_date": connection_db.end_date
                })
                return connection
            else:
                print(f"Connection with ID {id} not found.")
                return None
        except DoesNotExist:
            print(f"Connection with ID {id} does not exist.")
            return None
