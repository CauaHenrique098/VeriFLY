import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

service_account = json.loads(
    os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]
)

cred = credentials.Certificate(service_account)

firebase_admin.initialize_app(cred)

db = firestore.client()