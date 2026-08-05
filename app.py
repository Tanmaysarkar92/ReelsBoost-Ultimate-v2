from video_generator import generate_video
from voice_generator import generate_voice
from whatsapp import send_text_message, send_video_message
import os
import logging
import requests
processed_messages = set()
from flask import Flask, request, jsonify

from config import (
    VERIFY_TOKEN,
    META_ACCESS_TOKEN,
    IMAGE_FOLDER
)

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("ReelsBoost")


# ==========================
# Download WhatsApp Image
# ==========================

def download_whatsapp_image(image_id):

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}"
    }

    # Get Media URL
    response = requests.get(
        f"https://graph.facebook.com/v25.0/{image_id}",
        headers=headers
    )

    media = response.json()

    logger.info(media)

    media_url = media.get("url")

    if not media_url:
        logger.error("Image URL not found")
        return None

    # Download Image
    image = requests.get(
        media_url,
        headers=headers
    )

    file_path = os.path.join(IMAGE_FOLDER, "input.jpg")

    with open(file_path, "wb") as f:
        f.write(image.content)

    logger.info(f"✅ Image Saved : {file_path}")

    return file_path


# ==========================
# Home
# ==========================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "project": "ReelsBoost Ultimate v2",
        "message": "WhatsApp AI Bot Running Successfully"
    }), 200


# ==========================
# Health
# ==========================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy"
    }), 200


# ==========================
# Verify Webhook
# ==========================

@app.route("/webhook", methods=["GET"])
def verify_webhook():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    logger.info(f"TOKEN FROM META: {token}")
    logger.info(f"TOKEN FROM ENV: {VERIFY_TOKEN}")

    if mode == "subscribe" and token == VERIFY_TOKEN:

        logger.info("Webhook verified successfully.")

        return challenge, 200

    logger.warning("Webhook verification failed.")

    return "Verification Failed", 403


# ==========================
# Receive WhatsApp Message
# ==========================

@app.route("/webhook", methods=["POST"])
def receive_message():

    data = request.get_json(force=True)

    logger.info(f"Incoming webhook: {data}")

    try:

        value = data["entry"][0]["changes"][0]["value"]

        if "messages" in value:

            msg = value["messages"][0]
            message_id = msg["id"]

            if message_id in processed_messages:
                logger.info(f"⚠️ Duplicate Message Ignored: {message_id}")
                return jsonify({"status": "duplicate"}), 200

            processed_messages.add(message_id)

            if msg["type"] == "text":

                text = msg["text"]["body"]
                logger.info(f"📩 Text : {text}")

            elif msg["type"] == "image":

                image_id = msg["image"]["id"]

                logger.info(f"📷 Image ID : {image_id}")
                
                logger.info(f"🆔 Message ID : {message_id}")

                image_path = download_whatsapp_image(image_id)

                logger.info(f"Saved : {image_path}")

                caption = "Beautiful property available for sale."

                voice_path = generate_voice(caption)

                logger.info(f"🎤 Voice : {voice_path}")

                video_path = generate_video(image_path)

                logger.info(f"🎬 Video : {video_path}")

                logger.info("🚀 Sending Video")

                if video_path:

                    success = send_video_message(
                        msg["from"],
                        video_path
                    )

                    logger.info(f"✅ Video Send Status : {success}")

                else:

                    send_text_message(
                        msg["from"],
                        "❌ Video Generate Failed"
                    )

            else:

                logger.info(f"Unsupported Message Type : {msg['type']}")

        if "statuses" in value:

            logger.info(value["statuses"])

    except Exception as e:

        logger.exception(e)

    return jsonify({
        "status": "received"
    }), 200
