import os
import uuid
import requests
import logging

from config import META_ACCESS_TOKEN

logger = logging.getLogger("ReelsBoost")


GRAPH_API = "https://graph.facebook.com/v25.0"


def download_image(media_id):

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}"
    }

    try:

        # Step 1: Get download URL
        response = requests.get(
            f"{GRAPH_API}/{media_id}",
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        media_url = response.json()["url"]

        # Step 2: Download image
        image_response = requests.get(
            media_url,
            headers=headers,
            timeout=60
        )

        image_response.raise_for_status()

        os.makedirs("downloads", exist_ok=True)

        filename = os.path.join(
            "downloads",
            f"{uuid.uuid4()}.jpg"
        )

        with open(filename, "wb") as f:
            f.write(image_response.content)

        logger.info(f"Image saved: {filename}")

        return filename

    except Exception as e:

        logger.exception(e)

        return None