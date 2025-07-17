import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status
from typing import Optional
import os
import base64

firebase_app = None
# Use the environment variable name as used in Render
base64_key = os.getenv("FIREBASE_CREDENTIALS_BASE64")
if base64_key:
    import json
    key_json = base64.b64decode(base64_key).decode("utf-8")
    cred = credentials.Certificate(json.loads(key_json))
    firebase_app = firebase_admin.initialize_app(cred)
else:
    cred = credentials.Certificate(os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json"))
    firebase_app = firebase_admin.initialize_app(cred)


def verify_token(id_token: str) -> Optional[dict]:
    """Verify Firebase ID token and return user info"""
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

def get_user(uid: str) -> dict:
    """Get user details from Firebase"""
    try:
        user = auth.get_user(uid)
        return {
            "uid": user.uid,
            "email": user.email,
            "name": user.display_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )