---
title: planitly
language_tabs:
  - shell: Shell
  - http: HTTP
  - javascript: JavaScript
  - ruby: Ruby
  - python: Python
  - php: PHP
  - java: Java
  - go: Go
toc_footers: []
includes: []
search: true
code_clipboard: true
highlight_theme: darkula
headingLevel: 2
generator: "@tarslib/widdershins v4.0.29"

---

# planitly

Base URLs:

# Authentication

# Subjects

## GET get all subjects

GET /subjects/

> Body Parameters

```json
{}
```

### Params

|Name|Location|Type|Required|Description|
|---|---|---|---|---|
|Authorization|header|string| yes |the tokin of the user |
|body|body|object| no |none|

> Response Examples

> 200 Response

```json
[
  {
    "_id": "a0754f54-f031-42a6-a0a9-c1e623303f31",
    "name": "pdhielo",
    "components": [],
    "owner": "fd8abce3-f3e1-4459-99c1-6a403bc73d58",
    "template": ""
  },
  {
    "_id": "95959977-5d0b-4932-a664-9b9028faf64c",
    "name": "pdhielo",
    "components": [],
    "owner": "948ecb46-4805-470e-bf2d-48eb80abec26",
    "template": ""
  },
  {
    "_id": "ea0394fb-9331-4b27-b5a1-d090cc51e766",
    "name": "person",
    "components": [
      "adfbf2f6-32a1-445c-8302-540f761c8464",
      "29f3b563-be8b-47bf-9725-1d8a325530bc",
      "6819a63a-9fd2-4181-bd28-34b1b39fad51",
      "1957c880-e00a-4c7e-9118-de7fbd7b8a6f",
      "516d3ef4-f1ce-4a27-81ba-0a4661243783"
    ],
    "owner": "2d6168c6-778c-4166-bf2b-4423ea9a5a6b",
    "template": "person"
  }
]
```

> 401 Response

```json
{
  "detail": "Invalid token"
}
```

> 403 Response

```json
{
  "detail": "Admins only!"
}
```

### Responses

|HTTP Status Code |Meaning|Description|Data schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|Inline|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|none|Inline|
|403|[Forbidden](https://tools.ietf.org/html/rfc7231#section-6.5.3)|none|Inline|

### Responses Data Schema

## POST create a subject

POST /subjects/

> Body Parameters

```json
{
  "name": "philo",
  "template": "person"
}
```

### Params

|Name|Location|Type|Required|Description|
|---|---|---|---|---|
|Authorization|header|string| yes |none|
|body|body|object| no |none|
|» name|body|string| yes |name of subject|
|» id|body|string| no |ID|
|» template|body|string| no |the template the subject will be created with|

> Response Examples

> 201 Response

```json
{
  "id": "11659392-ca3d-4d59-a498-01d8051974e2",
  "name": "philo",
  "components": [
    "6a5356bd-6ecf-4b04-b5d0-b2efe57b4267",
    "7bbe764e-e6de-46d7-9d9b-acf60a784b2a",
    "409ec358-1abb-48c9-b9ac-b8a407299c23",
    "89ea4f39-dcb7-4325-aad6-645dcf6309d8",
    "6f36e5c3-5af6-447b-a109-0c94be6e536f"
  ]
}
```

> 422 Response

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": [
        "body"
      ],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

> 500 Response

```json
{
  "detail": "An unexpected error occurred: 400: Subject with this ID or name already exists"
}
```

### Responses

|HTTP Status Code |Meaning|Description|Data schema|
|---|---|---|---|
|201|[Created](https://tools.ietf.org/html/rfc7231#section-6.3.2)|none|Inline|
|422|[Unprocessable Entity](https://tools.ietf.org/html/rfc2518#section-10.3)|none|Inline|
|500|[Internal Server Error](https://tools.ietf.org/html/rfc7231#section-6.6.1)|none|Inline|

### Responses Data Schema

# components

## GET get all components

GET /components

Admin required

### Params

|Name|Location|Type|Required|Description|
|---|---|---|---|---|
|Authorization|header|string| yes |none|

> Response Examples

> 200 Response

```json
[
  {
    "_id": "adfbf2f6-32a1-445c-8302-540f761c8464",
    "name": "Full Name",
    "host_subject": "ea0394fb-9331-4b27-b5a1-d090cc51e766",
    "data": {
      "item": "John Doe"
    },
    "comp_type": "str",
    "owner": "2d6168c6-778c-4166-bf2b-4423ea9a5a6b"
  },
  {
    "_id": "29f3b563-be8b-47bf-9725-1d8a325530bc",
    "name": "Birthday",
    "host_subject": "ea0394fb-9331-4b27-b5a1-d090cc51e766",
    "data": {
      "item": "2025-03-28T19:24:11.094000"
    },
    "comp_type": "date",
    "owner": "2d6168c6-778c-4166-bf2b-4423ea9a5a6b"
  },
  {
    "_id": "6819a63a-9fd2-4181-bd28-34b1b39fad51",
    "name": "Phone",
    "host_subject": "ea0394fb-9331-4b27-b5a1-d090cc51e766",
    "data": {
      "item": "1234567890"
    },
    "comp_type": "str",
    "owner": "2d6168c6-778c-4166-bf2b-4423ea9a5a6b"
  },
  {
    "_id": "1957c880-e00a-4c7e-9118-de7fbd7b8a6f",
    "name": "Email",
    "host_subject": "ea0394fb-9331-4b27-b5a1-d090cc51e766",
    "data": {
      "item": ""
    },
    "comp_type": "str",
    "owner": "2d6168c6-778c-4166-bf2b-4423ea9a5a6b"
  },
  {
    "_id": "516d3ef4-f1ce-4a27-81ba-0a4661243783",
    "name": "Address",
    "host_subject": "ea0394fb-9331-4b27-b5a1-d090cc51e766",
    "data": {
      "item": ""
    },
    "comp_type": "str",
    "owner": "2d6168c6-778c-4166-bf2b-4423ea9a5a6b"
  }
]
```

### Responses

|HTTP Status Code |Meaning|Description|Data schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|Inline|

### Responses Data Schema

# Data Schema

<h2 id="tocS_subject">subject</h2>

<a id="schemasubject"></a>
<a id="schema_subject"></a>
<a id="tocSsubject"></a>
<a id="tocssubject"></a>

```json
{
  "id": "string",
  "name": "string",
  "components": [
    {
      "id": "string",
      "name": "string",
      "host_subject": {
        "id": "string",
        "name": "string",
        "components": [
          null
        ],
        "template": "string",
        "owner": {}
      },
      "data": {
        "item": "string",
        "items": "string"
      },
      "comp_type": "string",
      "owner": {
        "id": "string",
        "username": "string",
        "email": "string",
        "password": "string",
        "admin": true
      }
    }
  ],
  "template": "string",
  "owner": {
    "id": "string",
    "username": "string",
    "email": "string",
    "password": "string",
    "admin": true
  }
}

```

### Attribute

|Name|Type|Required|Restrictions|Title|Description|
|---|---|---|---|---|---|
|id|string|true|none||ID|
|name|string|true|none||name|
|components|[anyOf]|true|none||held components|

anyOf

|Name|Type|Required|Restrictions|Title|Description|
|---|---|---|---|---|---|
|» *anonymous*|[component](#schemacomponent)|false|none||none|

or

|Name|Type|Required|Restrictions|Title|Description|
|---|---|---|---|---|---|
|» *anonymous*|null|false|none||none|

continued

|Name|Type|Required|Restrictions|Title|Description|
|---|---|---|---|---|---|
|template|string|true|none||template to create the subject on|
|owner|[user](#schemauser)|true|none||the owner of the subject|

<h2 id="tocS_component">component</h2>

<a id="schemacomponent"></a>
<a id="schema_component"></a>
<a id="tocScomponent"></a>
<a id="tocscomponent"></a>

```json
{
  "id": "string",
  "name": "string",
  "host_subject": {
    "id": "string",
    "name": "string",
    "components": [
      {
        "id": "string",
        "name": "string",
        "host_subject": {},
        "data": {},
        "comp_type": "string",
        "owner": {}
      }
    ],
    "template": "string",
    "owner": {
      "id": "string",
      "username": "string",
      "email": "string",
      "password": "string",
      "admin": true
    }
  },
  "data": {
    "item": "string",
    "items": "string"
  },
  "comp_type": "string",
  "owner": {
    "id": "string",
    "username": "string",
    "email": "string",
    "password": "string",
    "admin": true
  }
}

```

### Attribute

|Name|Type|Required|Restrictions|Title|Description|
|---|---|---|---|---|---|
|id|string|true|none||ID|
|name|string|true|none||name|
|host_subject|[subject](#schemasubject)|true|none||the the subject that hosts the component|
|data|object|true|none||none|
|» item|string|true|none||if it is not an array|
|» items|string|true|none||if it is an array|
|comp_type|string|true|none||the type of the component|
|owner|[user](#schemauser)|true|none||the owner of the subject|

<h2 id="tocS_user">user</h2>

<a id="schemauser"></a>
<a id="schema_user"></a>
<a id="tocSuser"></a>
<a id="tocsuser"></a>

```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "password": "string",
  "admin": true
}

```

### Attribute

|Name|Type|Required|Restrictions|Title|Description|
|---|---|---|---|---|---|
|id|string|true|none||ID|
|username|string|true|none||none|
|email|string|true|none||the email of user|
|password|string|true|none||password of the user|
|admin|boolean|true|none||if the user is admin or not|


