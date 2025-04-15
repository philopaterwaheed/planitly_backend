from firebase_admin import credentials
import firebase_admin
from consts import env_variables

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
