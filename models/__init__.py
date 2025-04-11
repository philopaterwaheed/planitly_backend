from .user import User
from .dataTransfer import DataTransfer_db, DataTransfer
from .subject import Subject_db, Subject
from .component import Component_db, Component
from .connection import Connection_db, Connection
from .widget import Widget, Widget_db
from .todos import Todo_db, Todo
from mongoengine import connect
from dotenv import load_dotenv
import os

# TODO - compine the classes with the db classes

load_env = load_dotenv()
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
if MONGO_HOST == "localhost":
    connect(db="planitly", host="localhost", port=27017)
else:
    connect(db="Cluster0", host=MONGO_HOST, port=27017)

