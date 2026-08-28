import os
import json
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import (
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_TOKEN_JSON,
    YOUTUBE_TOKEN_FILE
)

logger = logging.getLogger("ReelsBoost")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]


def get_youtube_service():
    """Create authenticated YouTube API service."""

    creds = None

    # ====================================================
    # STEP 1 - LOAD TOKEN FROM RENDER ENVIRONMENT
    # ====================================================

    token_json = os.getenv("YOUTUBE_TOKEN_JSON")

    if token_json:

        try:

            logger.info(
                "🔐 Loading YouTube OAuth token from environment..."
            )

            token_data = json.loads(token_json)

            creds = Credentials.from_authorized_user_info(
                token_data,
                SCOPES
            )

            logger.info(
                "✅ YouTube OAuth token loaded from environment"
            )

        except Exception as e:

            logger.exception(
                f"❌ Failed to load YOUTUBE_TOKEN_JSON: {e}"
            )

            creds = None

    # ====================================================
    # STEP 2 - LOCAL TOKEN FILE
    # ====================================================

    if creds is None and os.path.exists(YOUTUBE_TOKEN_FILE):

        try:

            logger.info(
                f"🔐 Loading local YouTube token: "
                f"{YOUTUBE_TOKEN_FILE}"
            )

            creds = Credentials.from_authorized_user_file(
                YOUTUBE_TOKEN_FILE,
                SCOPES
            )

            logger.info(
                "✅ Local YouTube token loaded"
            )

        except Exception as e:

            logger.exception(
                f"❌ Failed to load local YouTube token: {e}"
            )

            creds = None

    # ====================================================
    # STEP 3 - REFRESH EXPIRED TOKEN
    # ====================================================

    if creds and creds.expired and creds.refresh_token:

        try:

            logger.info(
                "🔄 Refreshing expired YouTube OAuth token..."
            )

            creds.refresh(Request())

            logger.info(
                "✅ YouTube OAuth token refreshed"
            )

        except Exception as e:

            logger.exception(
                f"❌ YouTube token refresh failed: {e}"
            )

            creds = None

    # ====================================================
    # STEP 4 - FIRST TIME LOCAL OAUTH
    # ====================================================

    if not creds or not creds.valid:

        # Render should NOT try browser OAuth
        if os.getenv("RENDER"):

            logger.error(
                "❌ YouTube OAuth credentials are invalid "
                "or missing on Render."
            )

            return None

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

        logger.info(
            "🔐 Starting YouTube OAuth..."
        )

        try:

            flow = InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CLIENT_SECRET,
                SCOPES
            )

            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent"
            )

            with open(
                YOUTUBE_TOKEN_FILE,
                "w"
            ) as token:

                token.write(
                    creds.to_json()
                )

            logger.info(
                f"✅ YouTube token saved: "
                f"{YOUTUBE_TOKEN_FILE}"
            )

        except Exception as e:

            logger.exception(
                f"❌ YouTube OAuth failed: {e}"
            )

            return None

    # ====================================================
    # STEP 5 - BUILD YOUTUBE API SERVICE
    # ====================================================

    try:

        youtube = build(
            "youtube",
            "v3",
            credentials=creds
        )

        logger.info(
            "✅ YouTube API service ready"
        )

        return youtube

    except Exception as e:

        logger.exception(
            f"❌ Failed to build YouTube service: {e}"
        )

        return None


def upload_to_youtube(
    video_path,
    title=None,
    description=None,
    tags=None
):
    """Upload an MP4 video to YouTube."""

    try:

        if not title:
            title = "🏠 Amazing Property Tour | Sarkar Robotics #Shorts"

        if not description:
            description = (
                "🏠 Take a quick look at this beautiful property!\n\n"
                "📍 Property details available on request.\n"
                "📩 Contact us for more information.\n\n"
                "🔔 Subscribe to Sarkar Robotics for more property tours, "
                "real estate updates and property listings.\n\n"
                "#Shorts #RealEstate #Property #PropertyForSale #SarkarRobotics"
            )
        # ====================================================
        # STEP 1 - CHECK VIDEO
        # ====================================================

        if not video_path or not os.path.exists(video_path):

            logger.error(
                f"❌ YouTube: Video not found: {video_path}"
            )

            return False

        # ====================================================
        # STEP 2 - GET YOUTUBE SERVICE
        # ====================================================

        youtube = get_youtube_service()

        if youtube is None:

            logger.error(
                "❌ YouTube service unavailable"
            )

            return False

        # ====================================================
        # STEP 3 - DEFAULT TAGS
        # ====================================================

        if tags is None:
            tags = [
                "real estate",
                "property",
                "property for sale",
                "luxury property",
                "luxury real estate",
                "property listing"
            ]

        # ====================================================

        # ====================================================
        # STEP 4 - VIDEO METADATA
        # ====================================================

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

        # ====================================================
        # STEP 5 - UPLOAD
        # ====================================================

        logger.info(
            "▶️ YouTube upload started..."
        )

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

        # ====================================================
        # STEP 6 - RESULT
        # ====================================================

        video_id = response.get("id")

        if video_id:

            logger.info(
                f"✅ YouTube upload successful: "
                f"{video_id}"
            )

            logger.info(
                f"🔗 https://www.youtube.com/watch?v={video_id}"
            )

            return True

        logger.error(
            "❌ YouTube upload completed but no video ID returned"
        )

        return False

    except Exception as e:

        logger.exception(
            f"❌ YouTube upload error: {e}"
        )

        return False