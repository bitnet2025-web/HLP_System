import os
import firebase_admin
from firebase_admin import credentials, firestore, storage

def init_firebase():
    # Loads service account JSON from project root file named serviceAccountKey.json
    sa_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
    if not os.path.exists(sa_path):
        raise FileNotFoundError("serviceAccountKey.json not found in project root. Place the Firebase service account JSON there.")
    cred = credentials.Certificate(sa_path)

    if not firebase_admin._apps:
        # Initialize app with storage bucket automatically read from JSON if present
        firebase_admin.initialize_app(cred, {
            # If your Firebase storage bucket name differs, set the environment variable or replace below:
            # "storageBucket": "hlp-management-system.appspot.com"
        })

    db = firestore.client()
    try:
        bucket = storage.bucket()
    except Exception:
        bucket = None
    return db, bucket
