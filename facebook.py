import os
import logging
import requests

from config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN

logger = logging.getLogger("ReelsBoost")


def upload_to_facebook(video_path, caption=""):
    """
    Upload a generated MP4 video to the configured Facebook Page.

    Returns:
        True  -> upload successful
        False -> upload failed
    """

    try:
        if not video_path or not os.path.exists(video_path):
            logger.error(f"❌ Facebook: Video not found: {video_path}")
            return False

        if not FB_PAGE_ID:
            logger.error("❌ Facebook: FB_PAGE_ID is missing")
            return False

        if not FB_PAGE_ACCESS_TOKEN:
            logger.error("❌ Facebook: FB_PAGE_ACCESS_TOKEN is missing")
            return False

        url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos"

        logger.info("📘 Facebook upload started...")

        with open(video_path, "rb") as video_file:

            response = requests.post(
                url,
                data={
                    "access_token": FB_PAGE_ACCESS_TOKEN,
                    "description": caption,
                },
                files={
                    "source": (
                        os.path.basename(video_path),
                        video_file,
                        "video/mp4",
                    )
                },
                timeout=180,
            )

        logger.info(
            f"📘 Facebook response: "
            f"{response.status_code} {response.text[:1000]}"
        )

        if response.ok:
            result = response.json()

            post_id = result.get("id")

            logger.info(
                f"✅ Facebook upload successful: {post_id}"
            )

            return True

        logger.error(
            f"❌ Facebook upload failed: "
            f"{response.status_code} {response.text}"
        )

        return False

    except requests.RequestException as e:
        logger.exception(
            f"❌ Facebook network error: {e}"
        )
        return False

    except Exception as e:
        logger.exception(
            f"❌ Facebook upload error: {e}"
        )
        return False