import os
import logging
import requests
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor

from config import (
    VERIFY_TOKEN,
    META_ACCESS_TOKEN,
    IMAGE_FOLDER
)

from video_generator import generate_video
from voice_generator import generate_voice
from whatsapp import (
    send_text_message,
    send_video_message
)


# ============================================================
# APP
# ============================================================

app = Flask(__name__)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("ReelsBoost")


# ============================================================
# GLOBALS
# ============================================================

processed_messages = set()

# Only one heavy video-generation job at a time.
# This is safer for a small Render instance.
executor = ThreadPoolExecutor(max_workers=1)


# ============================================================
# MAKE SURE FOLDERS EXIST
# ============================================================

os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("downloads", exist_ok=True)


# ============================================================
# DOWNLOAD WHATSAPP IMAGE
# ============================================================

def download_whatsapp_image(image_id):

    try:

        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}"
        }

        logger.info(
            f"📥 Getting WhatsApp media URL: {image_id}"
        )

        # ----------------------------------------------------
        # Get Media Information
        # ----------------------------------------------------

        response = requests.get(
            f"https://graph.facebook.com/v25.0/{image_id}",
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        media = response.json()

        logger.info(
            f"📦 Media Info: {media}"
        )

        media_url = media.get("url")

        if not media_url:

            logger.error(
                "❌ Image URL not found"
            )

            return None

        # ----------------------------------------------------
        # Download Actual Image
        # ----------------------------------------------------

        logger.info(
            "⬇️ Downloading WhatsApp image..."
        )

        image_response = requests.get(
            media_url,
            headers=headers,
            timeout=60
        )

        image_response.raise_for_status()

        # ----------------------------------------------------
        # Unique filename
        # ----------------------------------------------------

        file_path = os.path.join(
            IMAGE_FOLDER,
            f"input_{image_id}.jpg"
        )

        with open(file_path, "wb") as f:
            f.write(image_response.content)

        logger.info(
            f"✅ Image Saved: {file_path}"
        )

        return file_path

    except Exception as e:

        logger.exception(
            f"❌ Image download failed: {e}"
        )

        return None


# ============================================================
# BACKGROUND IMAGE PROCESSING
# ============================================================

def process_image_message(
    phone_number,
    image_id,
    message_id
):

    image_path = None
    voice_path = None
    video_path = None

    try:

        logger.info(
            "=================================================="
        )

        logger.info(
            f"🚀 BACKGROUND PROCESS STARTED"
        )

        logger.info(
            f"🆔 Message ID: {message_id}"
        )

        logger.info(
            f"📷 Image ID: {image_id}"
        )

        logger.info(
            f"📱 Phone: {phone_number}"
        )

        logger.info(
            "=================================================="
        )

        # ====================================================
        # STEP 1 - DOWNLOAD IMAGE
        # ====================================================

        image_path = download_whatsapp_image(
            image_id
        )

        if not image_path:

            logger.error(
                "❌ Image download failed"
            )

            send_text_message(
                phone_number,
                "❌ Image download failed. Please try again."
            )

            return

        logger.info(
            f"✅ Image ready: {image_path}"
        )

        # ====================================================
        # STEP 2 - CAPTION
        # ====================================================

        caption = (
            "Beautiful property available for sale. "
            "Contact us for more details."
        )

        logger.info(
            f"📝 Caption: {caption}"
        )

        # ====================================================
        # STEP 3 - GENERATE VOICE
        # ====================================================

        logger.info(
            "🎤 Generating voice..."
        )

        voice_path = generate_voice(
            caption
        )

        if not voice_path:

            logger.error(
                "❌ Voice generation failed"
            )

            send_text_message(
                phone_number,
                "❌ Voice generation failed."
            )

            return

        logger.info(
            f"✅ Voice Generated: {voice_path}"
        )

        # ====================================================
        # STEP 4 - GENERATE VIDEO
        # ====================================================

        logger.info(
            "🎬 Starting video generation..."
        )

        # IMPORTANT:
        # voice_path is now passed into generate_video()

        video_path = generate_video(
            image_path,
            voice_path
        )

        if not video_path:

            logger.error(
                "❌ Video generation failed"
            )

            send_text_message(
                phone_number,
                "❌ Video Generate Failed."
            )

            return

        logger.info(
            f"✅ Video Generated: {video_path}"
        )

               # ====================================================
        # STEP 5 - AUTO POST TO FACEBOOK + YOUTUBE
        # ====================================================

        logger.info(
            "📤 Starting Facebook + YouTube auto-post..."
        )

        try:

            from facebook import upload_to_facebook
            from youtube import upload_to_youtube

            caption = (
                "🏡 Luxury Property Available!\n\n"
                "Beautiful real estate property available for sale.\n"
                "Contact us for more details.\n\n"
                "#RealEstate #PropertyForSale "
                "#LuxuryProperty #SarkarRobotics"
            )

            # =================================================
            # FACEBOOK
            # =================================================

            logger.info(
                "📘 Uploading video to Facebook..."
            )

            facebook_result = upload_to_facebook(
                video_path,
                caption
            )

            if facebook_result:

                logger.info(
                    "✅ Facebook auto-post successful"
                )

            else:

                logger.error(
                    "❌ Facebook auto-post failed"
                )

            # =================================================
            # YOUTUBE
            # =================================================

            logger.info(
                "▶️ Uploading video to YouTube..."
            )

            youtube_result = upload_to_youtube(
                video_path,
                "Luxury Property | Sarkar Robotics",
                caption
            )

            if youtube_result:

                logger.info(
                    "✅ YouTube auto-post successful"
                )

            else:

                logger.error(
                    "❌ YouTube auto-post failed"
                )

            # =================================================
            # POST STATUS
            # =================================================

            if facebook_result and youtube_result:

                logger.info(
                    "🎉 Facebook + YouTube auto-post completed"
                )

                send_text_message(
                    phone_number,
                    "🎬 তন্ময় ভাই, আপনার Luxury Property Reel Ready! ❤️\n\n"
                    "✅ Facebook Page-এ পোস্ট হয়েছে\n"
                    "✅ YouTube-এ পোস্ট হয়েছে\n\n"
                    "🚀 Sarkar Robotics AI Reel Engine সফলভাবে কাজ করছে!"
                )

            elif facebook_result:

                send_text_message(
                    phone_number,
                    "🎬 Reel তৈরি হয়েছে!\n\n"
                    "✅ Facebook Page-এ পোস্ট হয়েছে\n"
                    "⚠️ YouTube-এ পোস্ট হয়নি।"
                )

            elif youtube_result:

                send_text_message(
                    phone_number,
                    "🎬 Reel তৈরি হয়েছে!\n\n"
                    "⚠️ Facebook-এ পোস্ট হয়নি\n"
                    "✅ YouTube-এ পোস্ট হয়েছে"
                )

            else:

                send_text_message(
                    phone_number,
                    "🎬 Reel তৈরি হয়েছে, কিন্তু Facebook ও YouTube-এ পোস্ট করা যায়নি।"
                )

        except Exception as e:

            logger.exception(
                f"❌ Social media auto-post failed: {e}"
            )

            send_text_message(
                phone_number,
                "🎬 Reel তৈরি হয়েছে, কিন্তু Facebook/YouTube auto-post করতে সমস্যা হয়েছে।"
            )


        # ====================================================
        # STEP 6 - SEND VIDEO TO WHATSAPP
        # ====================================================

        logger.info(
            "🚀 Sending video to WhatsApp..."
        )

        success = send_video_message(
            phone_number,
            video_path
        )

        logger.info(
            f"📤 Video Send Status: {success}"
        )

        if success:

            logger.info(
                "🎉 REELSBOOST REEL COMPLETED SUCCESSFULLY"
            )

        else:

            logger.error(
                "❌ WhatsApp video sending failed"
            )

            send_text_message(
                phone_number,
                "❌ Reel তৈরি হয়েছে, কিন্তু WhatsApp-এ পাঠানো যায়নি।"
            )


    except Exception as e:

        logger.exception(
            f"❌ Background processing failed: {e}"
        )

        try:

            send_text_message(
                phone_number,
                "❌ Reel তৈরি করতে সমস্যা হয়েছে। Please try again."
            )

        except Exception as send_error:

            logger.exception(
                f"❌ Error message could not be sent: {send_error}"
            )

    finally:

        logger.info(
            f"🏁 Background job finished: {message_id}"
        )


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "project": "ReelsBoost Ultimate v2",
        "message": "WhatsApp AI Bot Running Successfully"
    }), 200


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "healthy",
        "project": "ReelsBoost Ultimate v2"
    }), 200


# ============================================================
# VERIFY WHATSAPP WEBHOOK
# ============================================================

@app.route("/webhook", methods=["GET"])
def verify_webhook():

    mode = request.args.get(
        "hub.mode"
    )

    token = request.args.get(
        "hub.verify_token"
    )

    challenge = request.args.get(
        "hub.challenge"
    )

    logger.info(
        f"TOKEN FROM META: {token}"
    )

    logger.info(
        f"TOKEN FROM ENV: {VERIFY_TOKEN}"
    )

    if (
        mode == "subscribe"
        and token == VERIFY_TOKEN
    ):

        logger.info(
            "✅ Webhook verified successfully."
        )

        return challenge, 200

    logger.warning(
        "❌ Webhook verification failed."
    )

    return "Verification Failed", 403


# ============================================================
# RECEIVE WHATSAPP MESSAGE
# ============================================================

@app.route("/webhook", methods=["POST"])
def receive_message():

    try:

        data = request.get_json(
            force=True
        )

        logger.info(
            f"📩 Incoming webhook: {data}"
        )

        # ====================================================
        # BASIC VALIDATION
        # ====================================================

        if not data:

            logger.warning(
                "⚠️ Empty webhook received"
            )

            return jsonify({
                "status": "empty"
            }), 200

        # ====================================================
        # GET VALUE
        # ====================================================

        entry = data.get(
            "entry",
            []
        )

        if not entry:

            logger.warning(
                "⚠️ No entry in webhook"
            )

            return jsonify({
                "status": "no_entry"
            }), 200

        changes = entry[0].get(
            "changes",
            []
        )

        if not changes:

            logger.warning(
                "⚠️ No changes in webhook"
            )

            return jsonify({
                "status": "no_changes"
            }), 200

        value = changes[0].get(
            "value",
            {}
        )

        # ====================================================
        # MESSAGES
        # ====================================================

        if "messages" in value:

            messages = value.get(
                "messages",
                []
            )

            if not messages:

                return jsonify({
                    "status": "no_messages"
                }), 200

            msg = messages[0]

            message_id = msg.get(
                "id"
            )

            message_type = msg.get(
                "type"
            )

            sender = msg.get(
                "from"
            )

            # =================================================
            # DUPLICATE MESSAGE CHECK
            # =================================================

            if message_id in processed_messages:

                logger.info(
                    f"⚠️ Duplicate Message Ignored: {message_id}"
                )

                return jsonify({
                    "status": "duplicate"
                }), 200

            processed_messages.add(
                message_id
            )

            logger.info(
                f"🆔 Message ID: {message_id}"
            )

            logger.info(
                f"📱 Sender: {sender}"
            )

            logger.info(
                f"📦 Message Type: {message_type}"
            )

            # =================================================
            # TEXT MESSAGE
            # =================================================

            if message_type == "text":

                text = msg.get(
                    "text",
                    {}
                ).get(
                    "body",
                    ""
                )

                logger.info(
                    f"📩 Text: {text}"
                )

            # =================================================
            # IMAGE MESSAGE
            # =================================================

            elif message_type == "image":

                image_data = msg.get(
                    "image",
                    {}
                )

                image_id = image_data.get(
                    "id"
                )

                logger.info(
                    f"📷 Image ID: {image_id}"
                )

                if not image_id:

                    logger.error(
                        "❌ Image ID missing"
                    )

                    send_text_message(
                        sender,
                        "❌ Image পাওয়া যায়নি। Please send the image again."
                    )

                    return jsonify({
                        "status": "image_id_missing"
                    }), 200

                # =============================================
                # IMPORTANT
                # =============================================
                # DO NOT download image here
                # DO NOT generate voice here
                # DO NOT generate video here
                #
                # Start background job instead.
                # =============================================

                executor.submit(
                    process_image_message,
                    sender,
                    image_id,
                    message_id
                )

                logger.info(
                    "⚡ Background processing submitted"
                )

            # =================================================
            # OTHER MESSAGE TYPE
            # =================================================

            else:

                logger.info(
                    f"⚠️ Unsupported Message Type: {message_type}"
                )

        # ====================================================
        # STATUS EVENTS
        # ====================================================

        if "statuses" in value:

            logger.info(
                f"📊 WhatsApp Status: {value['statuses']}"
            )

        # ====================================================
        # VERY IMPORTANT
        # RETURN IMMEDIATELY
        # ====================================================

        return jsonify({
            "status": "received"
        }), 200

    except Exception as e:

        logger.exception(
            f"❌ Webhook Error: {e}"
        )

        # Even if our processing has an error,
        # acknowledge the webhook.
        return jsonify({
            "status": "received"
        }), 200


# ============================================================
# RUN LOCAL
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    logger.info(
        f"🚀 ReelsBoost starting on port {port}"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )