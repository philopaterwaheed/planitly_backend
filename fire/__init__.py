from firebase_admin import credentials
import firebase_admin
from consts import env_variables , firebase_urls
from errors import FirebaseAuthError
import requests
cred_dict = env_variables.get(
    "FIREBASE_CREDENTIALS_JSON", None
)
cred = credentials.Certificate(cred_dict)


def initialize_firebase(cred):
    """Initialize Firebase Admin SDK from .env file"""
    try:
        # Initialize the app
        firebase_admin.initialize_app(cred)
        return True
    except Exception as e:
        print(f"Failed to initialize Firebase: {e}")
        return False


initialize_firebase(cred)


async def node_firebase(email: str, password: str = None, operation: str = "register"):

    try:
        # Validate the operation
        if operation not in firebase_urls:
            raise FirebaseAuthError(status_code=400, message=f"Invalid operation: {operation}")

        # Prepare the request data
        data = {"email": email}
        if password:
            data["password"] = password

        # Get the appropriate URL for the operation
        url = firebase_urls[operation]

        # Make the POST request to the Node.js Firebase API
        response = requests.post(url, json=data)

        # Handle non-successful responses
        if response.status_code not in [200, 201]:
            try:
                error_msg = response.json().get("error", response.text)
            except Exception:
                error_msg = response.text

            raise FirebaseAuthError(
                status_code=response.status_code,
                message=error_msg
            )

        # Return the response data
        return response

    except requests.exceptions.RequestException as e:
        raise FirebaseAuthError(status_code=500, message=f"Error connecting to Firebase service: {str(e)}")