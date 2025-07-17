import os
from dotenv import load_dotenv

load_dotenv()

FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json")
API_TITLE = os.getenv("API_TITLE", "Task Management API")
API_VERSION = os.getenv("API_VERSION", "1.0.0")
PORT = int(os.getenv("PORT", 8000))