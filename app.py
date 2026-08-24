import os
import logging
import requests
import sqlite3
from flask import Flask, request, jsonify, render_template
from concurrent.futures import ThreadPoolExecutor
from groq import Groq
import base64
import razorpay

from config import (
    VERIFY_TOKEN,
    META_ACCESS_TOKEN,
    IMAGE_FOLDER,
    GROQ_API_KEY,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    RAZORPAY_WEBHOOK_SECRET
)

groq_client = Groq(
    api_key=GROQ_API_KEY
)

razorpay_client = razorpay.Client(
    auth=(
        RAZORPAY_KEY_ID,
        RAZORPAY_KEY_SECRET
    )
)
RAZORPAY_PLANS = {
    "starter": "plan_TT8KV0NLz3Ocli",
    "pro": "plan_TT8Np2cEB3rwr8",
    "business": "plan_TT8PWX69j1s5Qz"
}
# ============================================================
# CUSTOMER SUBSCRIPTION DATABASE
# ============================================================

DATABASE_FILE = "users.db"


def init_database():

    with sqlite3.connect(DATABASE_FILE) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                whatsapp_number TEXT UNIQUE,
                subscription_id TEXT UNIQUE,
                plan TEXT,
                status TEXT DEFAULT 'inactive',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


init_database()
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

@app.route("/payment", methods=["GET"])
def payment_page():
    return render_template(
        "payment.html",
        razorpay_key_id=RAZORPAY_KEY_ID
    )

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("ReelsBoost")
# ============================================================
# RAZORPAY SUBSCRIPTION
# ============================================================

@app.route("/create-subscription", methods=["POST"])
def create_subscription():

    try:
        data = request.get_json(silent=True) or {}

        plan = data.get("plan")
        customer_name = data.get("name", "")
        customer_email = data.get("email", "")
        customer_phone = data.get("phone", "")

        if plan not in RAZORPAY_PLANS:
            return jsonify({
                "success": False,
                "error": "Invalid plan"
            }), 400

        subscription = razorpay_client.subscription.create({
            "plan_id": RAZORPAY_PLANS[plan],
            "total_count": 12,
            "customer_notify": 1,
            "notes": {
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "plan": plan
            }
        })

        return jsonify({
            "success": True,
            "subscription_id": subscription["id"],
            "plan": plan
        }), 200

    except Exception as e:

        logger.exception(
            "Razorpay subscription creation failed"
        )

        return jsonify({
            "success": False,
            "error": "Unable to create subscription"
        }), 500

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("ReelsBoost")
# ============================================================
# RAZORPAY WEBHOOK
# ============================================================

@app.route("/razorpay/webhook", methods=["POST"])
def razorpay_webhook():

    try:
        body = request.get_data()
        signature = request.headers.get("X-Razorpay-Signature")

        if not signature:
            return jsonify({"status": "missing signature"}), 400

        razorpay_client.utility.verify_webhook_signature(
            body,
            signature,
            RAZORPAY_WEBHOOK_SECRET
        )

        data = request.get_json(silent=True) or {}
        event = data.get("event")

        logger.info(f"Razorpay event: {event}")

        subscription = (
            data
            .get("payload", {})
            .get("subscription", {})
            .get("entity", {})
        )

        subscription_id = subscription.get("id")

        if not subscription_id:
            return jsonify({"status": "received"}), 200

        notes = subscription.get("notes") or {}

        whatsapp_number = notes.get("customer_phone")
        plan = notes.get("plan")

        if event == "subscription.activated":

            if whatsapp_number:

                with sqlite3.connect(DATABASE_FILE) as conn:

                    conn.execute("""
                        INSERT INTO subscribers
                        (
                            whatsapp_number,
                            subscription_id,
                            plan,
                            status
                        )
                        VALUES (?, ?, ?, 'active')

                        ON CONFLICT(whatsapp_number)
                        DO UPDATE SET
                            subscription_id = excluded.subscription_id,
                            plan = excluded.plan,
                            status = 'active',
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        whatsapp_number,
                        subscription_id,
                        plan
                    ))

                    conn.commit()

                logger.info(
                    f"Subscription ACTIVE: "
                    f"{whatsapp_number} | {plan}"
                )

        elif event in (
            "subscription.halted",
            "subscription.cancelled",
            "subscription.completed"
        ):

            new_status = {
                "subscription.halted": "halted",
                "subscription.cancelled": "cancelled",
                "subscription.completed": "completed"
            }[event]

            with sqlite3.connect(DATABASE_FILE) as conn:

                conn.execute("""
                    UPDATE subscribers
                    SET status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE subscription_id = ?
                """, (
                    new_status,
                    subscription_id
                ))

                conn.commit()

        return jsonify({"status": "ok"}), 200

    except Exception as e:

        logger.exception(
            f"Razorpay webhook error: {e}"
        )

        return jsonify({
            "status": "invalid webhook"
        }), 400

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
# AI PROPERTY CAPTION
# ============================================================

def generate_ai_caption(image_path):

    try:

        if not image_path or not os.path.exists(image_path):

            logger.warning(
                f"⚠️ Caption image not found: {image_path}"
            )

            return (
                "Beautiful property available for sale. "
                "Contact us for more details."
            )

        logger.info(
            "🤖 Generating AI property caption..."
        )

        # Read image
        with open(image_path, "rb") as image_file:

            image_data = base64.b64encode(
                image_file.read()
            ).decode("utf-8")

        response = groq_client.chat.completions.create(

            model="qwen/qwen3.6-27b",

            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this property photo and create "
                                "one short natural real-estate narration "
                                "for an 8-second video. "
                                "Mention only details visible in the image. "
                                "Do not invent price, location, bedrooms, "
                                "amenities, or other facts. "
                                "Return ONLY the final narration. "
                                "Do not include thinking, analysis, "
                                "explanations, bullet points, or "
                                "<think> tags."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/jpeg;base64,"
                                    f"{image_data}"
                                )
                            }
                        }
                    ]
                }
            ],

            max_tokens=80,
            temperature=0.7
        )

        caption = (
            response.choices[0]
            .message.content
            .strip()
        )

                # ----------------------------------------------------
        # REMOVE QWEN THINKING / REASONING
        # ----------------------------------------------------

        if "<think>" in caption:

            caption = caption.split(
                "<think>",
                1
            )[1]

        if "</think>" in caption:

            caption = caption.split(
                "</think>",
                1
            )[1]

        # ----------------------------------------------------
        # REMOVE COMMON REASONING TEXT
        # ----------------------------------------------------

        reasoning_markers = [
            "The user wants",
            "The user is asking",
            "I need to",
            "I should",
            "Let's analyze",
            "Let's think",
            "Analysis:",
            "Reasoning:",
            "We need to",
            "The image shows"
        ]

        for marker in reasoning_markers:

            if marker.lower() in caption.lower():

                parts = caption.split(
                    marker,
                    1
                )

                if len(parts) == 2:

                    possible_caption = (
                        parts[1].strip()
                    )

                    if len(possible_caption) > 20:

                        caption = possible_caption

        # ----------------------------------------------------
        # CLEAN EXTRA MARKDOWN
        # ----------------------------------------------------

        caption = caption.replace(
            "```text",
            ""
        )

        caption = caption.replace(
            "```",
            ""
        )

        caption = caption.replace(
            "**",
            ""
        )

        caption = caption.strip()

        # ----------------------------------------------------
        # EMPTY RESPONSE CHECK
        # ----------------------------------------------------

        if not caption:

            raise ValueError(
                "AI returned empty caption"
            )

        # ----------------------------------------------------
        # FINAL CAPTION
        # ----------------------------------------------------

        logger.info(
            f"🤖 AI Caption: {caption}"
        )

        return caption

    except Exception as e:

        logger.warning(
            f"⚠️ AI caption failed, using fallback: {e}"
        )

        return (
            "Beautiful property available for sale. "
            "Contact us for more details."
        )
    
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
        # STEP 2 - AI CAPTION
        # ====================================================

        caption = generate_ai_caption(
            image_path
        )

        logger.info(
            f"📝 AI Caption: {caption}"
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
    "📌 Subscribe to Sarkar Robotics for more property videos, "
    "real estate updates, and luxury property listings.\n\n"
    "#RealEstate #PropertyForSale #LuxuryProperty #SarkarRobotics"
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
