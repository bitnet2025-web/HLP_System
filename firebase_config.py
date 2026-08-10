import firebase_admin
from firebase_admin import credentials, db
import os

def init_firebase():
    # Allow pointing to the uploaded file path via env var
    sa_env = os.environ.get("SERVICE_ACCOUNT_PATH")
    if sa_env and os.path.exists(sa_env):
        cred_path = sa_env
    else:
        cred_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")

    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"Service account JSON not found at {cred_path}")

    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://hlp-management-system-default-rtdb.firebaseio.com/"
        })

    return db
