# Planity Backend API

Planity Backend provides RESTful API endpoints to manage **subjects**, **components**, and **data transfers**. Below is a quick guide on how to interact with the API using `curl` commands.

---

## Features

- **Subjects**: Create, retrieve, and manage subjects and their components.
- **Components**: Define and access components with associated data and entities.
- **Data Transfers**: Manage operations and schedules for data transfers between components.

---

## Table of Contents

- **Subjects API**
- **Components API**
- **Data Transfers API**
- **Project Structure**
- **Requirements**
- **How to Run**
---

## Subjects API

###  Create a Subject

```bash
curl -X POST http://127.0.0.1:5000/subjects \
-H "Content-Type: application/json" \
-d '{
  "id": "sub123",
  "name": "Subject A",
  "components": ["comp123", "comp456"]
}
```
Response : 

```bash
{
  "id": "sub123",
  "message": "Subject created"
}
```
```bash
curl -X GET http://127.0.0.1:5000/subjects
```
Response:
```bash
[{"_id": "sub123", "name": "Subject A", "components": ["comp123", "comp456"]}]
```
Get a Single Subject
```bash
curl -X GET http://127.0.0.1:5000/subjects/sub123
```
Response:
```bash
{
  "_id": "sub123",
  "components": ["comp123", "comp456"],
  "name": "Subject A"
}
```

Components API
  Create a Component

```bash
curl -X POST http://127.0.0.1:5000/components \
-H "Content-Type: application/json" \
-d '{
  "id": "comp456",
  "name": "Component A",
  "hostEntity": "host456",
  "data": {
    "key1": "value1",
    "key2": "value2"
  },
  "type": "exampleType"
}'
```
Response:
```bash
{
  "id": "comp456",
  "message": "Component created"
}
```
 Get All Components
```bash
curl -X GET http://127.0.0.1:5000/components
```
Response:
```bash
[
  {
    "_id": "comp123",
    "name": "Component A",
    "hostEntity": "host456",
    "data": {"key1": "value1", "key2": "value2"},
    "type": "exampleType"
  },
  {
    "_id": "comp456",
    "name": "Component A",
    "hostEntity": "host456",
    "data": {"key1": "value1", "key2": "value2"},
    "type": "exampleType"
  }
]
```
Get a Single Component
```bash
curl -X GET http://127.0.0.1:5000/components/comp456
```
Response:
```bash
{
  "_id": "comp456",
  "data": {"key1": "value1", "key2": "value2"},
  "hostEntity": "host456",
  "name": "Component A",
  "type": "exampleType"
}
```
Data Transfers API
  Create a Data Transfer
```bash
curl -X POST http://127.0.0.1:5000/data_transfers \
-H "Content-Type: application/json" \
-d '{
  "id": "transfer1",
  "sourceComp": "comp123",
  "targetSource": "comp456",
  "operation": "transfer",
  "schedule": "2024-11-23T10:00:00Z",
  "data_value": {"key": "value"}
}'
```
Response:
```bash
{
  "id": "transfer1",
  "message": "Data transfer created"
}
```
Get All Data Transfers
```bash
curl -X GET http://127.0.0.1:5000/data_transfers
```
Response:
```bash
[
  {
    "_id": "transfer1",
    "sourceComp": "comp123",
    "targetSource": "comp456",
    "data_value": {"key": "value"},
    "operation": "transfer",
    "schedule": "2024-11-23T10:00:00Z"
  }
]
```
Get a Single Data Transfer
```bash
curl -X GET http://127.0.0.1:5000/data_transfers/transfer1
```
Response:
```bash
{
  "_id": "transfer1",
  "data_value": {"key": "value"},
  "details": null,
  "operation": "transfer",
  "schedule": "2024-11-23T10:00:00Z",
  "sourceComp": "comp123",
  "targetSource": "comp456"
}
```
## Project Structure

- **app.py**: Main application file.
- **models/**: Data models for subjects, components, and data transfers.
- **routes/**: API route handlers.
- **tests/**: Unit tests for backend APIs.

##  Requirements

- Python 3.8+
- Flask
- MongoDB

##  How to Run

   ```bash
   git clone https://github.com/your-username/planity_backend.git
   cd planity_backend
   pip install -r requirements.txt
   python app.py
```

