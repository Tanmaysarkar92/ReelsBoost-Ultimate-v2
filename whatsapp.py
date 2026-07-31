import os
import requests
import logging

from config import META_ACCESS_TOKEN, PHONE_NUMBER_ID

logger = logging.getLogger("ReelsBoost")

GRAPH_URL = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
MEDIA_URL = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/media"


def send_text_message(to, message):

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message
        }
    }

    response = requests.post(
        GRAPH_URL,
        headers=headers,
        json=payload,
        timeout=30
    )

    logger.info(response.text)

    return response.status_code == 200


def send_video_message(to, video_path):

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}"
    }

    with open(video_path, "rb") as video_file:

        files = {
            "file": (
                os.path.basename(video_path),
                video_file,
                "video/mp4"
            )
        }

        data = {
            "messaging_product": "whatsapp"
        }

        upload = requests.post(
            MEDIA_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=180
        )

    logger.info(upload.text)

    if upload.status_code != 200:
        return False

    media_id = upload.json()["id"]

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "video",
        "video": {
            "id": media_id,
            "caption": "🎬 Sarkar Robotics AI Reel Ready!"
        }
    }

    response = requests.post(
        GRAPH_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    logger.info(response.text)

    return response.status_code == 200


def parse_message(data):

    try:

        entry = data["entry"][0]
        change = entry["changes"][0]
        value = change["value"]

        if "messages" not in value:
            return None

        message = value["messages"][0]

        result = {
            "from": message["from"],
            "id": message["id"],
            "type": message["type"]
        }

        if message["type"] == "text":
            result["text"] = message["text"]["body"]

        elif message["type"] == "image":
            result["media_id"] = message["image"]["id"]

        return result

    except Exception as e:

        logger.exception(e)
        return None
