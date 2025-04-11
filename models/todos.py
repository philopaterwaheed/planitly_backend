# models/todo.py
import uuid
from datetime import datetime
from mongoengine import Document, StringField, BooleanField, DateTimeField, ReferenceField


class Todo_db(Document):
    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    text = StringField(required=True)
    completed = BooleanField(default=False)
    date = DateTimeField(required=True)  # The date this todo belongs to
    widget_id = StringField(required=True)  # Reference to parent widget
    owner = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    meta = {'collection': 'todos'}

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "date": self.date.strftime("%Y-%m-%d"),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class Todo:
    def __init__(self, id=None, text=None, completed=False, date=None, widget_id=None, owner=None):
        self.id = id or str(uuid.uuid4())
        self.text = text
        self.completed = completed
        self.date = date
        self.widget_id = widget_id
        self.owner = owner

    def save_to_db(self):
        todo_db = Todo_db(
            id=self.id,
            text=self.text,
            completed=self.completed,
            date=self.date,
            widget_id=self.widget_id,
            owner=self.owner
        )
        todo_db.save()
        return todo_db

    @staticmethod
    def load_from_db(id):
        try:
            todo_db = Todo_db.objects(id=id).first()
            if todo_db:
                return Todo(
                    id=todo_db.id,
                    text=todo_db.text,
                    completed=todo_db.completed,
                    date=todo_db.date,
                    widget_id=todo_db.widget_id,
                    owner=todo_db.owner
                )
            return None
        except Exception as e:
            print(f"Error loading todo: {str(e)}")
            return None
