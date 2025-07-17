import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status
from typing import Optional
import os
import base64

# Initialize Firebase Admin SDK with support for base64 env var (for Render)
firebase_app = None
base64_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
if base64_key:
    # Decode the base64 string and load credentials from dict
    import json
    key_json = base64.b64decode(base64_key).decode("utf-8")
    cred = credentials.Certificate(json.loads(key_json))
    firebase_app = firebase_admin.initialize_app(cred)
else:
    # Fallback to file for local development
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