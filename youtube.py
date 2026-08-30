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
                "=ƒöÉ Loading YouTube OAuth token from environment..."
            )

            token_data = json.loads(token_json)

            creds = Credentials.from_authorized_user_info(
                token_data,
                SCOPES
            )

            logger.info(
                "G£à YouTube OAuth token loaded from environment"
            )

        except Exception as e:

            logger.exception(
                f"G¥î Failed to load YOUTUBE_TOKEN_JSON: {e}"
            )

            creds = None

    # ====================================================
    # STEP 2 - LOCAL TOKEN FILE
    # ====================================================

    if creds is None and os.path.exists(YOUTUBE_TOKEN_FILE):

        try:

            logger.info(
                f"=ƒöÉ Loading local YouTube token: "
                f"{YOUTUBE_TOKEN_FILE}"
            )

            creds = Credentials.from_authorized_user_file(
                YOUTUBE_TOKEN_FILE,
                SCOPES
            )

            logger.info(
                "G£à Local YouTube token loaded"
            )

        except Exception as e:

            logger.exception(
                f"G¥î Failed to load local YouTube token: {e}"
            )

            creds = None

    # ====================================================
    # STEP 3 - REFRESH EXPIRED TOKEN
    # ====================================================

    if creds and creds.expired and creds.refresh_token:

        try:

            logger.info(
                "=ƒöä Refreshing expired YouTube OAuth token..."
            )

            creds.refresh(Request())

            logger.info(
                "G£à YouTube OAuth token refreshed"
            )

        except Exception as e:

            logger.exception(
                f"G¥î YouTube token refresh failed: {e}"
            )

            creds = None

    # ====================================================
    # STEP 4 - FIRST TIME LOCAL OAUTH
    # ====================================================

    if not creds or not creds.valid:

        # Render should NOT try browser OAuth
        if os.getenv("RENDER"):

            logger.error(
                "G¥î YouTube OAuth credentials are invalid "
                "or missing on Render."
            )

            return None

        if not YOUTUBE_CLIENT_SECRET:

            logger.error(
                "G¥î YOUTUBE_CLIENT_SECRET is missing from .env"
            )

            return None

        if not os.path.exists(YOUTUBE_CLIENT_SECRET):

            logger.error(
                f"G¥î Client secret file not found: "
                f"{YOUTUBE_CLIENT_SECRET}"
            )

            return None

        logger.info(
            "=ƒöÉ Starting YouTube OAuth..."
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
                f"G£à YouTube token saved: "
                f"{YOUTUBE_TOKEN_FILE}"
            )

        except Exception as e:

            logger.exception(
                f"G¥î YouTube OAuth failed: {e}"
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
            "G£à YouTube API service ready"
        )

        return youtube

    except Exception as e:

        logger.exception(
            f"G¥î Failed to build YouTube service: {e}"
        )

        return None




def upload_to_youtube(
    video_path,
    title=None,
    description=None,
    tags=None
):
    """Upload an MP4 video to YouTube with dynamic metadata."""

    try:

        # ====================================================
        # STEP 1 - CHECK VIDEO
        # ====================================================

        if not video_path or not os.path.exists(video_path):

            logger.error(
                f"âŒ YouTube: Video not found: {video_path}"
            )

            return False

        # ====================================================
        # STEP 2 - GET YOUTUBE SERVICE
        # ====================================================

        youtube = get_youtube_service()

        if youtube is None:

            logger.error(
                "âŒ YouTube service unavailable"
            )

            return False

        # ====================================================
        # STEP 3 - DYNAMIC YOUTUBE METADATA
        # ====================================================

        if not title or not description:

            # Use the video filename to create a stable variation.
            filename = os.path.basename(video_path)

            # Remove extension and clean common generated names.
            video_name = os.path.splitext(filename)[0]

            # Create a small deterministic index so repeated
            # uploads don't always use the exact same wording.
            variation_index = (
                sum(ord(char) for char in video_name)
                % 8
            )

            title_variations = [

                "ðŸ  This Property Is Seriously Worth Seeing! #Shorts",

                "ðŸ¡ Would You Live In This Property? #Shorts",

                "âœ¨ A Property Tour You Don't Want To Miss! #Shorts",

                "ðŸ”¥ One Property, So Many Possibilities! #Shorts",

                "ðŸ  Take A Look Inside This Amazing Property! #Shorts",

                "ðŸ’° Is This Your Next Dream Property? #Shorts",

                "ðŸ¡ Another Interesting Property Tour! #Shorts",

                "ðŸ‘€ Wait Until You See This Property! #Shorts"
            ]

            description_variations = [

                "ðŸ  Take a quick look at this interesting property.\n\n"
                "From the location to the overall property appeal, "
                "there is always something interesting to discover.\n\n"
                "ðŸ“© Want property details? Contact us for more information.\n\n"
                "ðŸ”” Subscribe to Sarkar Robotics for more AI-powered "
                "property tours, real estate stories and interesting visuals.\n\n"
                "#Shorts #RealEstate #Property #PropertyTour #SarkarRobotics",

                "ðŸ¡ Discover another interesting real estate property.\n\n"
                "This short video gives you a quick visual look at the property "
                "and its potential.\n\n"
                "ðŸ“© Contact us for property details and availability.\n\n"
                "ðŸ”” Subscribe for more property tours and AI-powered real estate content.\n\n"
                "#Shorts #RealEstate #Property #RealEstateIndia #SarkarRobotics",

                "âœ¨ What do you think about this property?\n\n"
                "Watch the full short and explore the space, design and overall feel.\n\n"
                "ðŸ“© For more information about the property, get in touch with us.\n\n"
                "ðŸ”” Follow Sarkar Robotics for more interesting property videos.\n\n"
                "#Shorts #Property #RealEstate #PropertyForSale #SarkarRobotics",

                "ðŸ”¥ Another property worth a quick look!\n\n"
                "Real estate can look very different from property to property. "
                "Here is another one to explore.\n\n"
                "ðŸ“© Interested? Contact us for more details.\n\n"
                "ðŸ”” Subscribe to Sarkar Robotics for more real estate visuals and stories.\n\n"
                "#Shorts #RealEstate #PropertyTour #LuxuryProperty #SarkarRobotics"
            ]

            if not title:
                title = title_variations[variation_index]

            if not description:
                description = description_variations[
                    variation_index % len(description_variations)
                ]

        # ====================================================
        # STEP 4 - DEFAULT TAGS
        # ====================================================

        if tags is None:

            tags = [
                "real estate",
                "property",
                "property tour",
                "property for sale",
                "real estate india",
                "house tour",
                "luxury property",
                "real estate property",
                "property listing",
                "Sarkar Robotics"
            ]

        # ====================================================
        # STEP 5 - VIDEO METADATA
        # ====================================================

        body = {

            "snippet": {

                "title": title[:100],

                "description": description[:5000],

                "tags": tags,

                "categoryId": "22"
            },

            "status": {

                "privacyStatus": "public",

                "selfDeclaredMadeForKids": False
            }
        }

        # ====================================================
        # STEP 6 - UPLOAD
        # ====================================================

        logger.info(
            f"â–¶ï¸ YouTube upload started..."
        )

        logger.info(
            f"ðŸŽ¯ YouTube title: {title}"
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
        # STEP 7 - RESULT
        # ====================================================

        video_id = response.get("id")

        if video_id:

            logger.info(
                f"âœ… YouTube upload successful: "
                f"{video_id}"
            )

            logger.info(
                f"ðŸ”— https://www.youtube.com/watch?v={video_id}"
            )

            return True

        logger.error(
            "âŒ YouTube upload completed but no video ID returned"
        )

        return False

    except Exception as e:

        logger.exception(
            f"âŒ YouTube upload error: {e}"
        )

        return False