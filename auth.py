from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import json

with open("config.json") as f:
    config = json.load(f)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def authenticate_youtube():
    creds = None
    if os.path.exists(config["TOKEN_FILE"]):
        creds = Credentials.from_authorized_user_file(config["TOKEN_FILE"], SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            config["YOUTUBE_CLIENT_SECRET"], SCOPES
        )
        creds = flow.run_local_server(port=8080, access_type="offline", prompt="consent")

        # Save the new token
        with open(config["TOKEN_FILE"], "w") as token:
            token.write(creds.to_json())

    return creds

authenticate_youtube()
print("Authentication successful!")