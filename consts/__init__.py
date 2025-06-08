from dotenv import load_dotenv
import os

load_dotenv()

env_variables = {
    'MONGO_HOST': os.getenv('MONGO_HOST', "localhost"),
    'JWT_SECRET': os.getenv('JWT_SECRET_KEY', "secret"),
    'REJWT_SECRET': os.getenv('REJWT_SECRET_KEY', "secret"),
    'APIKEY': os.getenv('APIKEY'),
    'AUTHDOMAIN': os.getenv('AUTHDOMAIN'),
    'PROJECTID': os.getenv('PROJECTID'),
    'STORAGEBUC': os.getenv('STORAGEBUC'),
    'MESSAGINGS': os.getenv('MESSAGINGS'),
    'APPID': os.getenv('APPID'),
    'MEASUREMEN': os.getenv('MEASUREMEN'),
    'CLOUDINARY_API_KEY': os.getenv('CLOUDNARY_API_KEY'),
    'CLOUDINARY_API_SECRET': os.getenv('CLOUDNARY_API_SECRET'),
    'CLOUDINARY_CLOUD_NAME': os.getenv('CLOUDNARY_CLOUD_NAME'),
    'CLOUDINARY_URL': f"https://api.cloudinary.com/v1_1/{os.getenv('CLOUDNARY_CLOUD_NAME')}/image/upload",
    'DEV': os.getenv('DEV' ,"false"),
    'AI_SERVICE_URL': os.getenv('AI_SERVICE_URL', "https://potential-tribble-pjgg7jr5jwqxcrxq6-5001.app.github.dev"),
    'IPI_TOKEN': os.getenv('IPI_TOKEN'),
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
    },
    'AUTH_API_KEY': os.getenv('AUTH_API_KEY', "default_AUTH_api_key"),
}

if env_variables['DEV'] == "true":
    firebase_base_url = "http://localhost:3000/api/node"
    print("Using local Firebase URL")
else:
    firebase_base_url = "https://planitly-backend.vercel.app/api/node"
    print("Using production Firebase URL")

firebase_urls = {
    'register': f"{firebase_base_url}/firebase_register",
    'login': f"{firebase_base_url}/firebase_login",
    'forgot-password': f"{firebase_base_url}/firebase_forgot-password"
}
