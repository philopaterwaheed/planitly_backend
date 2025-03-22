
from mongoengine import Document, StringField, EmailField, BooleanField
from werkzeug.security import generate_password_hash, check_password_hash


class User(Document):
    id = StringField(primary_key=True, auto_generate=True)
    username = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
    admin = BooleanField(default=False, required=False)
    meta = {'collection': 'users'}

    def hash_password(self):
        self.password = generate_password_hash(self.password)

    def check_password(self, password):
        return check_password_hash(self.password, password)
