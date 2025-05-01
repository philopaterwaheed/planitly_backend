import datetime
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
                "data": {"items": [], "type": "str"},
                "is_deletable": False
            }
        ]
    },
    "financial_tracker": {
        "name": "Financial Tracker",
        "is_deletable": False,
        "category": "system",
        "components": [
                {
                    "name": "Income",
                    "type": "Array_type",
                    "data": {"items": [], "type": "int"},
                    "is_deletable": False
                },
            {
                    "name": "Expenses",
                    "type": "Array_type",
                    "data": {"items": [], "type": "int"},
                    "is_deletable": False
            },
            {
                    "name": "Savings Goal",
                    "type": "int",
                    "data": {"item": ""},
                    "is_deletable": False
            }
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
    },
    "person": {
        "category": "Contacts",  # Add category
        "components": [
            {"name": "Full Name", "type": "str", "data": {"item": "John Doe"}},
            {"name": "Birthday", "type": "date", "data": {"item": datetime.datetime.now()}},
            {"name": "Phone", "type": "str", "data": {"item": "1234567890"}},
        ],
    },
    "financial_tracker": {
        "category": "Finance",  # Add category
        "components": [
            {"name": "Income", "type": "Array_type", "data": {"items": [], "type": "int"}},
            {"name": "Expenses", "type": "Array_type", "data": {"items": [], "type": "int"}},
            {"name": "Savings Goal", "type": "int", "data": {"item": 0}},
        ],
    },
}
