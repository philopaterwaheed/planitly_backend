
from dotenv import load_dotenv
import os

load_dotenv()

env_variables = {
    'MONGO_HOST': os.getenv('MONGO_HOST'),
    'JWT_SECRET': os.getenv('JWT_SECRET'),
    'APIKEY': os.getenv('APIKEY'),
    'AUTHDOMAIN': os.getenv('AUTHDOMAIN'),
    'PROJECTID': os.getenv('PROJECTID'),
    'STORAGEBUC': os.getenv('STORAGEBUC'),
    'MESSAGINGS': os.getenv('MESSAGINGS'),
    'APPID': os.getenv('APPID'),
    'MEASUREMEN': os.getenv('MEASUREMEN'),
    'DEV': os.getenv('DEV'),
}
