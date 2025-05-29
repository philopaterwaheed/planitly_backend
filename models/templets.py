import datetime
from mongoengine import Document, StringField, DictField, ReferenceField

# Templates are predefined subjects that can be used to create new subjects
DEFAULT_USER_TEMPLATES = {
    "profile": {
        "name": "User Profile",
        "is_deletable": False,
        "category": "system",
        "components": [
            {
                "name": "Display Name",
                "type": "str",
                "data": {"item": ""},
                "is_deletable": False
            },
            {
                "name": "Bio",
                "type": "str",
                "data": {"item": ""},
                "is_deletable": False
            },
            {
                "name": "Joined Date",
                "type": "date",
                "data": {"item": ""},
                "is_deletable": False
            }
        ],
        "widgets": [
            {"name": "Profile Summary", "type": "text_field", "data": {"content": "Welcome to your profile!", "editable": False}},
        ]
    },
    "settings": {
        "name": "User Settings",
        "is_deletable": False,
        "category": "system",
        "components": [
            {
                "name": "Theme",
                "type": "str",
                "data": {"item": "light"},
                "is_deletable": False
            },
            {
                "name": "Notifications",
                "type": "bool",
                "data": {"item": True},
                "is_deletable": False
            },
            {
                "name": "Privacy Level",
                "type": "str",
                "data": {"item": "standard"},
                "is_deletable": False
            }
        ],
        "widgets": [
            {"name": "Settings Overview", "type": "note", "data": {"content": "Adjust your settings here.", "tags": [], "pinned": False}},
        ]
    },
    "habit_tracker": {
        "name": "Habit Tracker",
        "is_deletable": False,
        "category": "system",
        "components": [
            {
                "name": "habits",
                "type": "Array_type",
                "data": {"type": "str"},  # Specify the type of items in the array
                "is_deletable": False
            }
        ],
        "widgets": [
            {"name": "Daily Habits", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
        ]
    },
    "financial_tracker": {
        "name": "Financial Tracker",
        "is_deletable": False,
        "category": "system",
        "components": [
            {
                "name": "Income",
                "type": "Array_of_pairs",
                "data": {"type": {"key": "str", "value": "str"}},  # Specify the key and value types
                "is_deletable": False
            },
            {
                "name": "Expenses",
                "type": "Array_of_pairs",
                "data": {"type": {"key": "str", "value": "str"}},  # Specify the key and value types
                "is_deletable": False
            },
            {
                "name": "Savings Goal",
                "type": "int",
                "data": {"item": 0},
                "is_deletable": False
            }
        ],
        "widgets": [
            {
                "name": "Expense Tracker",
                "type": "table",
                "data": {
                    "columns": ["Date", "Category", "Amount"],
                    "rows": []
                }
            },
        ]
    }
}

TEMPLATES = {
    "habit": {
        "category": "Personal Development",  # Add category
        "components": [
            {"name": "Description", "type": "str", "data": {"item": "Description"}},
            {"name": "Frequency", "type": "str", "data": {"item": "Daily"}},
            {"name": "Start Date", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "End Date", "type": "date", "data": {"item": datetime.datetime.now()}},
        ],
        "widgets": [
            {"name": "Daily Checklist", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
        ],
    },
    "person": {
        "category": "Contacts",  # Add category
        "components": [
            {"name": "Full Name", "type": "str", "data": {"item": "John Doe"}},
            {"name": "Birthday", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Phone", "type": "str", "data": {"item": "1234567890"}},
        ],
        "widgets": [
            {"name": "Contact Notes", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
            {"name": "Birthday Reminder", "type": "calendar", "data": {"events": [{"title": "Birthday", "date": datetime.datetime.now().strftime("%Y-%m-%d")}]}},
        ],
    },
    "financial_tracker": {
        "category": "Finance",  # Add category
        "components": [
            {"name": "Income", "type": "Array_type", "data": {"type": "int"}},  # Specify the type of items in the array
            {"name": "Expenses", "type": "Array_type", "data": {"type": "int"}},  # Specify the type of items in the array
            {"name": "Savings Goal", "type": "int", "data": {"item": 0}},
        ],
        "widgets": [
            {"name": "Expense Tracker", "type": "table", "data": {"columns": ["Date", "Category", "Amount"], "rows": []}},
        ],
    },
}

class CustomTemplate_db(Document):
    owner = ReferenceField('User', required=True)
    name = StringField(required=True)
    description = StringField()
    data = DictField(required=True)  # Should contain components/widgets structure
    category = StringField() 

    meta = {
        'indexes': [
            {'fields': ['owner', 'name'], 'unique': True}
        ]
    }