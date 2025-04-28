# Authentication Functionality
 
## Endpoints

### 1. **Register User**
- **Endpoint**: `/auth/register`
- **Method**: `POST`
- **Description**: Registers a new user with device tracking.
- **Validation**:
  - Username must contain at least one letter and can include letters, numbers, underscores, dots, and hyphens.
  - Password must be strong (uppercase, lowercase, number, special character, and at least 8 characters long).
- **Process**:
  - Checks if the username or email already exists.
  - Registers the user in Firebase and sends an email verification.
  - Creates default subjects for the user.
  - Tracks the user's device.

### 2. **Login User**
- **Endpoint**: `/auth/login`
- **Method**: `POST`
- **Description**: Authenticates a user and generates JWT tokens.
- **Validation**:
  - Verifies the username or email and password.
  - Ensures the user's email is verified.
  - Tracks the user's device and enforces a maximum device limit.
- **Process**:
  - Generates an access token and a refresh token.
  - Sends a login notification to the user.

### 3. **Forgot Password**
- **Endpoint**: `/auth/forgot-password`
- **Method**: `POST`
- **Description**: Sends a password reset email to the user.
- **Process**:
  - Calls the Firebase `forgot-password` endpoint to send the reset email.

### 4. **Logout Device**
- **Endpoint**: `/auth/logout-device`
- **Method**: `POST`
- **Description**: Logs out the user from a specific device.
- **Process**:
  - Verifies the device ID and removes it from the user's registered devices.

### 5. **Reset Security**
- **Endpoint**: `/auth/reset-security`
- **Method**: `POST`
- **Description**: Resets the user's security settings by clearing invalid login attempts.

### 6. **Refresh Token**
- **Endpoint**: `/auth/refresh-token`
- **Method**: `POST`
- **Description**: Refreshes the access token using a valid refresh token.

### 7. **Get Devices**
- **Endpoint**: `/auth/devices`
- **Method**: `GET`
- **Description**: Retrieves all registered devices for the user.

### 8. **Clear All Devices**
- **Endpoint**: `/auth/clear-devices`
- **Method**: `POST`
- **Description**: Clears all registered devices except the current one.

## Middleware

### 1. **Authenticate User**
- **Function**: `authenticate_user`
- **Description**: Authenticates the user with Firebase and tracks the device.
- **Features**:
  - Locks the account after too many invalid attempts.
  - Verifies the user's email.
  - Tracks the user's devices and enforces a maximum device limit.

### 2. **Verify Device**
- **Function**: `verify_device`
- **Description**: Ensures the current device is registered for the user.
- **Features**:
  - Rejects unrecognized devices.
  - Requires re-login for unregistered devices.

### 3. **Get Current User**
- **Function**: `get_current_user`
- **Description**: Extracts and validates the JWT access token.

## Firebase Integration

### 1. **Registration**
- **Endpoint**: `/api/node/firebase_register`
- **Description**: Registers a user in Firebase and sends an email verification.

### 2. **Login**
- **Endpoint**: `/api/node/firebase_login`
- **Description**: Authenticates a user in Firebase.

### 3. **Forgot Password**
- **Endpoint**: `/api/node/firebase_forgot-password`
- **Description**: Sends a password reset email using Firebase.

## Error Handling

- **Common Errors**:
  - `400`: Invalid input (e.g., weak password, missing fields).
  - `401`: Unauthorized access (e.g., invalid token, unverified email).
  - `403`: Forbidden (e.g., unrecognized device).
  - `404`: Resource not found (e.g., user not found).
  - `409`: Conflict (e.g., username or email already exists).
  - `500`: Internal server error.

## Data Schema

### User Attributes
| Name             | Type    | Required | Description                              |
|------------------|---------|----------|------------------------------------------|
| id               | string  | true     | Unique identifier for the user.          |
| username         | string  | true     | The username of the user.                |
| email            | string  | true     | The email of the user.                   |
| email_verified   | boolean | true     | Indicates if the email is verified.      |
| admin            | boolean | true     | Indicates if the user is an admin.       |
| devices          | list    | false    | List of registered devices.              |
| invalid_attempts | int     | false    | Number of failed login attempts.         |
| last_reset       | string  | false    | Timestamp of the last security reset.    |
| firstname        | string  | false    | The first name of the user.              |
| lastname         | string  | false    | The last name of the user.               |
| phone_number     | string  | false    | The phone number of the user.            |
| birthday         | string  | false    | The birthday of the user (ISO format).   |

