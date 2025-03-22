from .user import User
from .data_transfer import DataTransfer_db, DataTransfer
from .subject import Subject_db, Subject
from .component import Component_db, Component
from mongoengine import connect

# TODO - compine the classes with the db classes

connect(db="planitly", host="localhost", port=27017)
