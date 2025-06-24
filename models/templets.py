import datetime
from mongoengine import Document, StringField, DictField, ReferenceField

# Templates are predefined subjects that are created per user by the system
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
    "habit_tracker": {
        "name": "Habit Tracker",
        "is_deletable": False,
        "category": "system",
        "components": [
            {
                "name": "habits",
                "type": "Array_type",
                "data": {"type": "str"},  # Array of habit subject IDs
                "is_deletable": False
            },
            {
                "name": "daily_status",
                "type": "Array_of_pairs",
                "data": {"type": {"key": "str", "value": "bool"}},  # habit_id: completion_status
                "is_deletable": False
            },
            {
                "name": "current_date",
                "type": "str",
                "data": {"item": datetime.datetime.now().strftime("%Y-%m-%d")},
                "is_deletable": False
            },
            {
                "name": "last_updated",
                "type": "date",
                "data": {"item": datetime.datetime.now()},
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
        ]
    },
    "health": {
        "name": "Health Profile",
        "is_deletable": False,
        "category": "system",
        "components": [
            {
                "name": "Blood Type",
                "type": "str",
                "data": {"item": ""},
                "is_deletable": False
            },
            {
                "name": "Allergies",
                "type": "str",
                "data": {"item": ""},
                "is_deletable": False
            },
            {
                "name": "Emergency Contact",
                "type": "str",
                "data": {"item": ""},
                "is_deletable": False
            },
            {
                "name": "Doctor Name",
                "type": "str",
                "data": {"item": ""},
                "is_deletable": False
            },
            {
                "name": "Insurance Provider",
                "type": "str",
                "data": {"item": ""},
                "is_deletable": False
            }
        ],
        "widgets": [
            {"name": "Appointment Calendar", "type": "calendar", "data": {"events": []}},
            {"name": "Medical Notes", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
        ],
    }
}

TEMPLATES = {
    "habit": {
        "category": "Personal Development",
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
        "category": "Contacts", 
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
    "fitness": {
        "category": "Health & Fitness",
        "components": [
            {"name": "Current Weight", "type": "int", "data": {"item": 0}},
            {"name": "Target Weight", "type": "int", "data": {"item": 0}},
            {"name": "Height", "type": "int", "data": {"item": 0}},
            {"name": "Exercise Routine", "type": "str", "data": {"item": ""}},
        ],
        "widgets": [
            {"name": "Workout Log", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
            {"name": "Progress Notes", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
        ],
    },
    "academic": {
        "category": "Education",
        "components": [
            {"name": "Course Name", "type": "str", "data": {"item": ""}},
            {"name": "Instructor", "type": "str", "data": {"item": ""}},
            {"name": "Credits", "type": "int", "data": {"item": 3}},
            {"name": "Semester", "type": "str", "data": {"item": ""}},
            {"name": "Current Grade", "type": "str", "data": {"item": ""}},
        ],
        "widgets": [
            {"name": "Assignment Tracker", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
            {"name": "Course Calendar", "type": "calendar", "data": {"events": []}},
            {"name": "Study Notes", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
        ],
    },
    "project": {
        "category": "Productivity",
        "components": [
            {"name": "Project Name", "type": "str", "data": {"item": ""}},
            {"name": "Description", "type": "str", "data": {"item": ""}},
            {"name": "Start Date", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Due Date", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Status", "type": "str", "data": {"item": "Planning"}},
            {"name": "Priority", "type": "str", "data": {"item": "Medium"}},
        ],
        "widgets": [
            {"name": "Task List", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
            {"name": "Project Timeline", "type": "calendar", "data": {"events": []}},
            {"name": "Project Notes", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
        ],
    },
    "personal_development": {
        "category": "Personal Development",
        "components": [
            {"name": "Current Goal", "type": "str", "data": {"item": ""}},
            {"name": "Target Skill", "type": "str", "data": {"item": ""}},
            {"name": "Progress Level", "type": "str", "data": {"item": "Beginner"}},
            {"name": "Learning Resources", "type": "str", "data": {"item": ""}},
            {"name": "Target Date", "type": "date", "data": {"item": datetime.datetime.now()}},
        ],
        "widgets": [
            {"name": "Daily Practice", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
            {"name": "Learning Calendar", "type": "calendar", "data": {"events": []}},
            {"name": "Progress Journal", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
        ],
    },
    "travel": {
        "category": "Travel",
        "components": [
            {"name": "Destination", "type": "str", "data": {"item": ""}},
            {"name": "Departure Date", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Return Date", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Budget", "type": "int", "data": {"item": 0}},
            {"name": "Accommodation", "type": "str", "data": {"item": ""}},
            {"name": "Transportation", "type": "str", "data": {"item": ""}},
        ],
        "widgets": [
            {"name": "Daily Itinerary", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
            {"name": "Travel Calendar", "type": "calendar", "data": {"events": []}},
            {"name": "Travel Journal", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
        ],
    },
    "reading": {
        "category": "Education",
        "components": [
            {"name": "Book Title", "type": "str", "data": {"item": ""}},
            {"name": "Author", "type": "str", "data": {"item": ""}},
            {"name": "Genre", "type": "str", "data": {"item": ""}},
            {"name": "Total Pages", "type": "int", "data": {"item": 0}},
            {"name": "Current Page", "type": "int", "data": {"item": 0}},
            {"name": "Start Date", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Target Finish Date", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Rating", "type": "str", "data": {"item": ""}},
        ],
        "widgets": [
            {"name": "Reading Schedule", "type": "daily_todo", "data": {"selected_date": datetime.datetime.now().strftime("%Y-%m-%d")}},
            {"name": "Reading Calendar", "type": "calendar", "data": {"events": []}},
            {"name": "Book Notes", "type": "note", "data": {"content": "", "tags": [], "pinned": False}},
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