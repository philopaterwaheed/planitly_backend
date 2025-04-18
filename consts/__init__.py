
from dotenv import load_dotenv
import os

load_dotenv()

env_variables = {
    'MONGO_HOST': os.getenv('MONGO_HOST', "server"),
    'JWT_SECRET': os.getenv('JWT_SECRET_KEY', "secret"),
    'REJWT_SECRET': os.getenv('REJWT_SECRET_KEY', "secret"),
    'APIKEY': os.getenv('APIKEY'),
    'AUTHDOMAIN': os.getenv('AUTHDOMAIN'),
    'PROJECTID': os.getenv('PROJECTID'),
    'STORAGEBUC': os.getenv('STORAGEBUC'),
    'MESSAGINGS': os.getenv('MESSAGINGS'),
    'APPID': os.getenv('APPID'),
    'MEASUREMEN': os.getenv('MEASUREMEN'),
    'DEV': os.getenv('DEV'),
    'FIREBASE_CREDENTIALS_JSON': {
        'type': "service_account",
        'project_id': os.getenv('FIREBASE_PROJECT_ID'),
        'private_key_id': os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        'private_key': os.getenv('FIREBASE_PRIVATE_KEY'),
        'client_email': os.getenv('FIREBASE_CLIENT_EMAIL'),
        'client_id': os.getenv('FIREBASE_CLIENT_ID'),
        'auth_uri': os.getenv('FIREBASE_AUTH_URI'),
        'token_uri': os.getenv('FIREBASE_TOKEN_URI'),
        'auth_provider_x509_cert_url': os.getenv('FIREBASE_AUTH_PROVIDER_CERT_URL'),
        'client_x509_cert_url': os.getenv('FIREBASE_CLIENT_CERT_URL')
    }
}
