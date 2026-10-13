import os
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore

# Global placeholder for the database client instance
db = None


def initialize_firebase():
    """
    Initializes the core Firebase Admin SDK connection.
    Ensures that a single application-wide client instance is registered.
    """
    global db

    # If already initialized, return existing database reference
    if firebase_admin._apps:
        if db is None:
            db = firestore.client()
        return db

    # Locate credential target path from environment configuration
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Verify the target credentials file physically exists on storage
    if cred_path and not Path(cred_path).exists():
        raise FileNotFoundError(
            f"Initialization Failed: Credential token file not located at position: {cred_path}"
        )

    try:
        # Load the authentication token and initialize administrative context
        if cred_path:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            # Cloud Run obtains credentials from its attached service account.
            project_id = os.getenv("FIREBASE_PROJECT_ID")
            options = {"projectId": project_id} if project_id else None
            firebase_admin.initialize_app(options=options)

        # Instantiate the database client connection
        db = firestore.client()
        print("Successfully synchronized backend connection with Firestore.")
        return db

    except Exception as error:
        raise RuntimeError(f"Critical error establishing Firebase client context: {str(error)}")
