from .user import User
from .dataTransfer import DataTransfer_db, DataTransfer
from .subject import Subject_db, Subject
from .component import Component_db, Component
from .connection import Connection_db, Connection
from .widget import Widget, Widget_db
from .todos import Todo_db, Todo
from .locks import AccountLock
from .rates import RateLimit
from .tokens import RefreshToken
from .notifications import Notification_db , Notification , NotificationCount
from .fcmtoken import FCMToken_db, FCMManager
from .category import Category_db
from .devices import Device_db
from .arrayItem import ArrayItem_db, Arrays
from mongoengine import connect
from consts import env_variables

# TODO - compine the classes with the db classes

MONGO_HOST = env_variables['MONGO_HOST']
if MONGO_HOST == "localhost":
    connect(db="planitly", host="localhost", port=27017)
else:
    connect(db="Cluster0", host=MONGO_HOST, port=27017)
