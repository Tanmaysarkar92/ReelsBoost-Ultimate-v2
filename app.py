import os
import logging
from flask import Flask, request, jsonify

from config import VERIFY_TOKEN

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("ReelsBoost")


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "project": "ReelsBoost Ultimate v2",
        "message": "WhatsApp AI Bot Running Successfully"
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy"
    }), 200


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


@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()

    logger.info(f"Incoming webhook: {data}")

    # এখানে পরে WhatsApp Message Processing যোগ হবে

    return jsonify({
        "status": "received"
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)