"""
Uploads a finished video to YouTube, optionally scheduled for a future
publish time. Reuses the same OAuth pattern as the yt_bulk_edit project --
put client_secret.json in config/ and it'll walk you through login on
first run.
"""

import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
CLIENT_SECRET_FILE = os.path.join(CONFIG_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(CONFIG_DIR, "token.json")


def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(f"ERROR: {CLIENT_SECRET_FILE} not found. See README setup steps.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, title: str, description: str, tags: list,
                  publish_at: str = None):
    """publish_at: ISO 8601 UTC datetime string, e.g. '2026-09-25T14:00:00Z'.
    If provided, video uploads as private and auto-publishes at that time.
    If omitted, video is published immediately as public."""
    youtube = get_authenticated_service()

    status = {"selfDeclaredMadeForKids": False}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    else:
        status["privacyStatus"] = "public"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "1",  # Film & Animation
        },
        "status": status,
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status_progress, response = request.next_chunk()
        if status_progress:
            print(f"Uploaded {int(status_progress.progress() * 100)}%")

    print(f"Done. Video ID: {response['id']}")
    print(f"https://youtube.com/watch?v={response['id']}")
    return response["id"]


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print('Usage: python3 upload_video.py video.mp4 "Title" "Description" [publish_at_ISO]')
        sys.exit(1)
    video_path, title, description = sys.argv[1], sys.argv[2], sys.argv[3]
    publish_at = sys.argv[4] if len(sys.argv) > 4 else None
    upload_video(video_path, title, description, ["movies", "moviereview", "shorts"], publish_at)
