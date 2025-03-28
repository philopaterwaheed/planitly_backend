import datetime
# Templates are predefined subjects that can be used to create new subjects
TEMPLATES = {
    "habit": {
        "components": [
            {"name": "Description", "type": "str",
             "data": {"item": "Description"}},
            {"name": "Frequency", "type": "str", "data": {"item": "Daily"}},
            {"name": "Start Date", "type": "date",
                "data": {"item": datetime.datetime.now()}},
            {"name": "End Date", "type": "date", "data": {
                "item": datetime.datetime.now()}}
        ]
    },
    "person": {
        "components": [
            {"name": "Full Name", "type": "str", "data": {"item": "John Doe"}},
            {"name": "Birthday", "type": "date", "data": {
                "item": datetime.datetime.now()}},
            {"name": "Phone", "type": "str", "data": {"item": "1234567890"}},
            {"name": "Email", "type": "str", "data": {"item": ""}},
            {"name": "Address", "type": "str", "data": {"item": ""}}
        ]
    },
    "task": {
        "components": [
            {"name": "Title", "type": "str", "data":  {"item": "Task Title"}},
            {"name": "Description", "type": "str",
             "data": {"item": "Task Details"}},
            {"name": "Due Date", "type": "date", "data": {
                "item": datetime.datetime.now()}},
        ]
    }
}
