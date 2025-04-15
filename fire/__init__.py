from firebase_admin import credentials, auth
import firebase_admin
import requests

import json
import os
from dotenv import load_dotenv

load_dotenv()
firebase_cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
cred_dict = json.loads(firebase_cred_json)
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


API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_REST_API = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={
    API_KEY}"


def send_verification_email(email):
    payload = json.dumps({
        "requestType": "VERIFY_EMAIL",
        "email": email
    })

    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.post(FIREBASE_REST_API, headers=headers, data=payload)
    return response.json()


initialize_firebase(cred)
