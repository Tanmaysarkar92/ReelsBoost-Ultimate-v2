from video_generator import generate_video
from whatsapp import send_text_message
import os
import logging
import requests

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

            if msg["type"] == "text":

                text = msg["text"]["body"]

                logger.info(f"📩 Text : {text}")

            elif msg["type"] == "image":

                image_id = msg["image"]["id"]

                logger.info(f"📷 Image ID : {image_id}")
                
                logger.info(f"🆔 Message ID : {msg['id']}")
                
                image_path = download_whatsapp_image(image_id)

                logger.info(f"Saved : {image_path}")

                video_path = generate_video(image_path)

                logger.info(f"🎬 Video : {video_path}")

                logger.info("🚀 Sending Video Ready Message")
                
                send_text_message(
                    msg["from"],
                    "✅ Video ready hoyeche backend e."
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


# ==========================
# Run
# ==========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
