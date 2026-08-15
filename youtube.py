import os
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import YOUTUBE_CLIENT_SECRET, YOUTUBE_TOKEN_FILE

logger = logging.getLogger("ReelsBoost")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]


def get_youtube_service():
    """Create authenticated YouTube API service."""

    creds = None

    # Existing token
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            YOUTUBE_TOKEN_FILE,
            SCOPES
        )

    # Refresh expired token
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            logger.warning(f"⚠️ YouTube token refresh failed: {e}")
            creds = None

    # First-time OAuth login
    if not creds or not creds.valid:

        if not YOUTUBE_CLIENT_SECRET:
            logger.error(
                "❌ YOUTUBE_CLIENT_SECRET is missing from .env"
            )
            return None

        if not os.path.exists(YOUTUBE_CLIENT_SECRET):
            logger.error(
                f"❌ Client secret file not found: "
                f"{YOUTUBE_CLIENT_SECRET}"
            )
            return None

        logger.info("🔐 Starting YouTube OAuth...")

        flow = InstalledAppFlow.from_client_secrets_file(
            YOUTUBE_CLIENT_SECRET,
            SCOPES
        )

        creds = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent"
        )

        with open(YOUTUBE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

        logger.info(
            f"✅ YouTube token saved: {YOUTUBE_TOKEN_FILE}"
        )

    return build(
        "youtube",
        "v3",
        credentials=creds
    )


def upload_to_youtube(
    video_path,
    title="Luxury Property | Sarkar Robotics",
    description="Beautiful property available for sale. Contact us for more details.",
    tags=None
):
    """Upload an MP4 video to YouTube."""

    try:

        if not video_path or not os.path.exists(video_path):
            logger.error(
                f"❌ YouTube: Video not found: {video_path}"
            )
            return False

        youtube = get_youtube_service()

        if youtube is None:
            return False

        if tags is None:
            tags = [
                "real estate",
                "property",
                "property for sale",
                "luxury property",
                "Sarkar Robotics"
            ]

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        logger.info("▶️ YouTube upload started...")

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = request.execute()

        video_id = response.get("id")

        logger.info(
            f"✅ YouTube upload successful: {video_id}"
        )

        if video_id:
            logger.info(
                f"🔗 https://www.youtube.com/watch?v={video_id}"
            )

        return True

    except Exception as e:

        logger.exception(
            f"❌ YouTube upload error: {e}"
        )

        return False