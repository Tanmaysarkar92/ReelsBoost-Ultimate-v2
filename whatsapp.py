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

    try:

        # ====================================================
        # STEP 1 - UPLOAD VIDEO TO WHATSAPP
        # ====================================================

        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}"
        }

        logger.info(
            f"📤 Uploading video to WhatsApp: {video_path}"
        )

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

        logger.info(
            f"📦 WhatsApp media upload response: "
            f"{upload.status_code} {upload.text}"
        )

        if not upload.ok:

            logger.error(
                f"❌ WhatsApp media upload failed: "
                f"{upload.status_code} {upload.text}"
            )

            return False

        upload_data = upload.json()

        media_id = upload_data.get("id")

        if not media_id:

            logger.error(
                "❌ WhatsApp media ID missing"
            )

            return False

        logger.info(
            f"✅ WhatsApp media uploaded: {media_id}"
        )

        # ====================================================
        # STEP 2 - SEND VIDEO MESSAGE
        # ====================================================

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

        logger.info(
            f"📤 Sending WhatsApp video to: {to}"
        )

        response = requests.post(
            GRAPH_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        logger.info(
            f"📨 WhatsApp video response: "
            f"{response.status_code} {response.text}"
        )

        # ====================================================
        # STEP 3 - CHECK ACTUAL WHATSAPP RESPONSE
        # ====================================================

        if not response.ok:

            logger.error(
                f"❌ WhatsApp video message failed: "
                f"{response.status_code} {response.text}"
            )

            return False

        try:

            response_data = response.json()

        except Exception:

            logger.error(
                "❌ WhatsApp returned invalid JSON"
            )

            return False

        messages = response_data.get(
            "messages",
            []
        )

        if messages and messages[0].get("id"):

            message_id = messages[0]["id"]

            logger.info(
                f"✅ WhatsApp video message accepted: "
                f"{message_id}"
            )

            return True

        logger.error(
            f"❌ WhatsApp response did not contain message ID: "
            f"{response.text}"
        )

        return False

    except Exception as e:

        logger.exception(
            f"❌ WhatsApp video sending exception: {e}"
        )

        return False


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
