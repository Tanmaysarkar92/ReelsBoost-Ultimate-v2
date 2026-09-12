import os
import re
import hmac
import hashlib
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_property_requests (
                whatsapp_number TEXT PRIMARY KEY,
                image_id TEXT NOT NULL,
                image_message_id TEXT,
                property_details TEXT DEFAULT '',
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


def normalize_phone(phone):
    phone = re.sub(r"\D", "", str(phone or ""))
    if phone.startswith("00"):
        phone = phone[2:]
    return phone


def activate_subscription(phone, subscription_id, plan):
    phone = normalize_phone(phone)
    if not phone or not subscription_id:
        return False
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.execute("""
            INSERT INTO subscribers (whatsapp_number, subscription_id, plan, status)
            VALUES (?, ?, ?, 'active')
            ON CONFLICT(whatsapp_number) DO UPDATE SET
                subscription_id = excluded.subscription_id,
                plan = excluded.plan,
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
        """, (phone, subscription_id, plan))
        conn.commit()
    return True


def subscription_is_active(phone):
    phone = normalize_phone(phone)
    if not phone:
        return False
    with sqlite3.connect(DATABASE_FILE) as conn:
        row = conn.execute(
            "SELECT status FROM subscribers WHERE whatsapp_number = ?",
            (phone,)
        ).fetchone()
    return bool(row and row[0] == "active")


@app.route("/verify-subscription", methods=["POST"])
def verify_subscription():
    try:
        data = request.get_json(silent=True) or {}
        payment_id = data.get("razorpay_payment_id", "")
        subscription_id = data.get("razorpay_subscription_id", "")
        signature = data.get("razorpay_signature", "")
        phone = normalize_phone(data.get("phone", ""))
        plan = data.get("plan", "")

        if not all([payment_id, subscription_id, signature, phone]):
            return jsonify({"success": False, "error": "Missing payment verification data"}), 400

        message = f"{payment_id}|{subscription_id}".encode("utf-8")
        expected = hmac.new(
            RAZORPAY_KEY_SECRET.encode("utf-8"),
            message,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("Razorpay subscription signature verification failed")
            return jsonify({"success": False, "error": "Payment verification failed"}), 400

        subscription = razorpay_client.subscription.fetch(subscription_id)
        actual_status = subscription.get("status")
        actual_plan_id = subscription.get("plan_id")
        resolved_plan = plan
        for name, plan_id in RAZORPAY_PLANS.items():
            if actual_plan_id == plan_id:
                resolved_plan = name
                break

        # Checkout authentication is verified here; access is granted immediately
        # for authenticated/active subscriptions. Webhook remains the authoritative
        # state-sync path for later renewals, halts, cancellations and completion.
        if actual_status in ("authenticated", "active"):
            activate_subscription(phone, subscription_id, resolved_plan)
            return jsonify({
                "success": True,
                "status": actual_status,
                "active": True
            }), 200

        return jsonify({
            "success": True,
            "status": actual_status,
            "active": False
        }), 200

    except Exception:
        logger.exception("Razorpay subscription verification failed")
        return jsonify({"success": False, "error": "Unable to verify payment"}), 500


@app.route("/subscription-status", methods=["GET"])
def subscription_status():
    phone = normalize_phone(request.args.get("phone", ""))
    if not phone:
        return jsonify({"success": False, "active": False}), 400
    return jsonify({"success": True, "active": subscription_is_active(phone)}), 200

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
        customer_phone = normalize_phone(data.get("phone", ""))

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

        whatsapp_number = normalize_phone(notes.get("customer_phone"))
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
                    "role": "system",
                    "content": (
                        "You are a professional luxury real-estate narrator. "
                        "Write ONLY the spoken voiceover script for an 18-second Reel. "
                        "Never reveal reasoning, analysis, instructions, headings, "
                        "labels, or phrases such as 'I cannot invent facts'. "
                        "Start directly with an energetic hook and use only details "
                        "clearly visible in the image."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this property photo and create one natural, "
                                "engaging real-estate narration for an 18-second video, "
                                "approximately 35-45 words. Mention only visible details. "
                                "Do not invent price, location, bedrooms, bathrooms, "
                                "amenities, ownership, or other facts. "
                                "Return ONLY the spoken narration."
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

            max_tokens=120,
            temperature=0.7,
            reasoning_effort="none"
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

def generate_youtube_metadata(image_path, property_details=""):

    try:

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
                                "Analyze this image carefully.\n\n"

                                "Create engaging YouTube metadata for Sarkar AI Quantum.\n\n"

                                "PROPERTY DETAILS PROVIDED BY THE USER:\n"
                                f"{property_details.strip() if property_details else '(No extra property details provided)'}\n\n"
                                "Use these user-provided details when present. They are trusted listing details supplied by the user, not facts to invent.\n\n"

                                "The channel covers:\n"
                                "- AI\n"
                                "- Robotics\n"
                                "- Real Estate\n"
                                "- AI-generated visual stories\n"
                                "- Futuristic technology\n"
                                "- Interesting visual experiments\n\n"

                                "IMPORTANT:\n"
                                "Choose the most appropriate content category "
                                "based on what is actually visible in the image.\n\n"

                                "If the image is clearly a property or real-estate "
                                "image, create real-estate content.\n\n"

                                "If the image is clearly about robotics or a robot, "
                                "create robotics/AI content.\n\n"

                                "If the image is suitable for an AI visual story, "
                                "create an interesting AI/futuristic story angle.\n\n"

                                "Do NOT claim that Sarkar AI Quantum owns, builds, "
                                "sells or develops any property unless that is "
                                "explicitly provided by the user.\n\n"

                                "Do not invent:\n"
                                "- price\n"
                                "- location\n"
                                "- bedrooms\n"
                                "- bathrooms\n"
                                "- specifications\n"
                                "- ownership\n"
                                "- company claims\n"
                                "- technical specifications not visible\n\n"

                                "TITLE RULES:\n"
                                "- Make the title interesting and curiosity-driven.\n"
                                "- Avoid repetitive generic titles.\n"
                                "- Use clearly visible information from the image.\n"
                                "- Never use generic titles such as 'Interesting Visual Story' or 'Visual Story'.\n"
                                "- If the image is clearly a property, the title MUST identify it as property, real estate, home, house, villa, apartment, or luxury home.\n"
                                "- Use a concrete visible hook such as modern design, exterior, interior, balcony, pool, architecture, or luxury feel when visible.\n"
                                "- Never invent price, location, bedrooms, bathrooms, amenities, or other facts.\n"
                                "- If user-provided property details include price, location, BHK, area, or a notable feature, use accurate details selectively in the title when they make the title more useful.\n"
                                "- Keep the title concise.\n"
                                "- Do not use clickbait that makes unsupported claims.\n"
                                "- Do not always start with the same words.\n"
                                "- Do not use 'Sarkar Robotics'.\n"
                                "- Brand the channel as 'Sarkar AI Quantum'.\n"
                                "- End the title with '| Sarkar AI Quantum'.\n\n"

                                "DESCRIPTION RULES:\n"
                                "- Write 3 to 5 natural sentences.\n"
                                "- Make the description different from previous videos.\n"
                                "- Explain what is interesting about the visual.\n"
                                "- Mention AI-generated visuals when appropriate.\n"
                                "- For property content, clearly state that the reel "
                                "was created from a property photo.\n"
                                "- Include relevant user-provided property details naturally when available.\n"
                                "- Never invent property facts beyond the supplied details or visible image.\n"
                                "- Do not make unsupported ownership or seller claims.\n"
                                "- End the description with this exact CTA line: 🔔 Subscribe to Sarkar AI Quantum for AI, Robotics, AI Stories and more.\n"
                                "- Mention Sarkar AI Quantum naturally.\n"
                                "- Include relevant hashtags at the end.\n\n"

                                "OUTPUT FORMAT:\n"
                                "Return EXACTLY these two lines:\n"
                                "TITLE: ...\n"
                                "DESCRIPTION: ...\n\n"

                                "Return ONLY those two fields.\n"
                                "Do not include analysis, explanations, markdown "
                                "or extra text."
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

            max_tokens=350,
            temperature=0.8
        )

        result = (
            response.choices[0]
            .message.content
            .strip()
        )

        title = None
        description = None

        # Parse the requested fields while tolerating a multi-line description.
        lines = result.splitlines()
        description_lines = []
        in_description = False

        for raw_line in lines:
            line = raw_line.strip()

            if line.upper().startswith("TITLE:"):
                title = line.split(":", 1)[1].strip()
                in_description = False

            elif line.upper().startswith("DESCRIPTION:"):
                description_lines.append(line.split(":", 1)[1].strip())
                in_description = True

            elif in_description and line:
                description_lines.append(line)

        if description_lines:
            description = "\n".join(description_lines).strip()

        # ====================================================
        # TITLE SAFETY
        # ====================================================

        if not title:
            title = "Property Tour"

        # Block old/generic AI output so it can never become the published title.
        generic_titles = {
            "interesting visual story",
            "visual story",
            "interesting visual story | sarkar ai quantum",
            "visual story | sarkar ai quantum"
        }
        if title.strip().lower() in generic_titles:
            title = "Property Tour"

        # When the user supplied property details, prefer a concrete title
        # built from those details over a vague AI-generated title.
        if property_details.strip():
            import re

            def detail_value(label):
                match = re.search(
                    rf"(?:^|\n)\s*{re.escape(label)}\s*:\s*(.+)",
                    property_details,
                    flags=re.IGNORECASE
                )
                return match.group(1).strip() if match else ""

            detail_price = detail_value("Price")
            detail_location = detail_value("Location")
            detail_bhk = detail_value("BHK")
            detail_type = detail_value("Property Type") or detail_value("Type")

            title_is_vague = (
                len(title.strip()) < 18
                or title.strip().lower() in {
                    "beautiful property",
                    "luxury property",
                    "beautiful home",
                    "property tour",
                    "home tour"
                }
            )

            if title_is_vague and (detail_bhk or detail_location or detail_price):
                title_parts = []
                if detail_bhk:
                    title_parts.append(detail_bhk)
                if detail_type:
                    title_parts.append(detail_type)
                elif detail_bhk:
                    title_parts.append("Property")
                else:
                    title_parts.append("Property")
                if detail_location:
                    title_parts.append(f"in {detail_location}")
                if detail_price:
                    title_parts.append(f"| {detail_price}")
                title = " ".join(title_parts)

        # Remove old branding

        title = title.replace(
            "| Sarkar Robotics",
            ""
        ).replace(
            "| Sarkar AI Quantum",
            ""
        ).strip()

        # Remove accidental duplicate pipes

        title = title.rstrip(" |")

        # Add new brand

        title = (
            title
            + " | Sarkar AI Quantum"
        )

        # YouTube title limit

        title = title[:100]

        # ====================================================
        # DESCRIPTION SAFETY
        # ====================================================

        if not description:

            description = (
                "Take a closer look at this interesting visual "
                "created with AI.\n\n"
                "Sarkar AI Quantum explores AI, robotics, real estate "
                "and interesting visual stories.\n\n"
                "🔔 Subscribe to Sarkar AI Quantum for AI, Robotics, AI Stories and more."
            )

        # Remove old branding

        description = description.replace(
            "Sarkar Robotics",
            "Sarkar AI Quantum"
        )

        # Remove accidental duplicate brand phrases

        description = description.replace(
            "Sarkar AI Quantum AI Quantum",
            "Sarkar AI Quantum"
        )

        # ====================================================
        # PROPERTY DETAILS BLOCK
        # ====================================================
        # Keep user-supplied listing details visible on BOTH YouTube
        # and Facebook. Facebook reuses youtube_description below.
        if property_details.strip():
            details_block = (
                "\n\nProperty Details:\n"
                + property_details.strip()
            )
            if "Property Details:" not in description:
                description += details_block

        # ====================================================
        # HASHTAGS
        # ====================================================

        hashtag_block = (
            "\n\n"
            "#SarkarAIQuantum "
            "#AI "
            "#Robotics "
            "#RealEstate "
            "#AIStory "
            "#Shorts"
        )

        # Avoid duplicate hashtag block

        if "#SarkarAIQuantum" not in description:

            description += hashtag_block

        # Keep the requested subscription CTA as the final line.
        cta = "🔔 Subscribe to Sarkar AI Quantum for AI, Robotics, AI Stories and more."
        description = description.replace(cta, "").rstrip()
        description += "\n\n" + cta

        # YouTube description limit

        description = description[:5000]

        logger.info(
            f"🎯 YouTube Title: {title}"
        )

        logger.info(
            f"📝 YouTube Description: {description}"
        )

        return title, description

    except Exception as e:

        logger.exception(
            f"❌ YouTube metadata generation failed: {e}"
        )

        return (
            "Property Tour | Sarkar AI Quantum",
            (
                "Take a closer look at this property visual created from "
                "a property photo.\n\n"
                "Sarkar AI Quantum creates AI-powered real estate and "
                "interesting visual content.\n\n"
                "🔔 Subscribe to Sarkar AI Quantum for AI, Robotics, AI Stories and more.\n\n"
                "#SarkarAIQuantum #RealEstate #Property #LuxuryHome #Shorts"
            )
        )

# ============================================================
# BACKGROUND IMAGE PROCESSING
# ============================================================

def process_image_message(
    phone_number,
    image_id,
    message_id,
    property_details=""
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

        if property_details:
            logger.info(
                f"📝 Property details received: {property_details}"
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

        youtube_title, youtube_description = generate_youtube_metadata(
            image_path,
            property_details
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

            # Reuse the AI-generated YouTube description for Facebook so
            # user-supplied property details and the new CTA stay consistent.
            caption = youtube_description

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
            youtube_title,
            youtube_description
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
                    "🚀 Sarkar AI Quantum Reel Engine সফলভাবে কাজ করছে!"
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

            # Normalize sender before processing.
            # IMPORTANT: Do not block the WhatsApp video pipeline on payment status.
            # Razorpay routes/webhooks remain available separately.
            sender = normalize_phone(sender)

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
                ).strip()

                logger.info(
                    f"📩 Text: {text}"
                )

                # A property photo is stored first. The next text message
                # becomes the property details for that photo.
                pending = None
                with sqlite3.connect(DATABASE_FILE) as conn:
                    row = conn.execute("""
                        SELECT image_id, image_message_id
                        FROM pending_property_requests
                        WHERE whatsapp_number = ?
                    """, (sender,)).fetchone()

                    if row:
                        pending = {
                            "image_id": row[0],
                            "image_message_id": row[1]
                        }
                        conn.execute("""
                            UPDATE pending_property_requests
                            SET property_details = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE whatsapp_number = ?
                        """, (text, sender))
                        conn.commit()

                if pending:
                    logger.info(
                        f"🚀 Property details linked to pending image: {pending['image_id']}"
                    )

                    # Remove the pending item before starting the job so a
                    # repeated webhook cannot start the same request twice.
                    with sqlite3.connect(DATABASE_FILE) as conn:
                        conn.execute("""
                            DELETE FROM pending_property_requests
                            WHERE whatsapp_number = ?
                        """, (sender,))
                        conn.commit()

                    executor.submit(
                        process_image_message,
                        sender,
                        pending["image_id"],
                        pending["image_message_id"] or message_id,
                        text
                    )

                    send_text_message(
                        sender,
                        "✅ Details received! এখন আপনার property photo + details দিয়ে Reel তৈরি হচ্ছে. 🎬\n\n"
                        "Price, location, BHK, area ও features ব্যবহার করে YouTube title/description তৈরি করা হবে. ❤️"
                    )
                else:
                    send_text_message(
                        sender,
                        "📋 আগে একটি property photo পাঠান, তারপর Price, Location, BHK, Area ও Features লিখে পাঠান."
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

                image_caption = image_data.get(
                    "caption",
                    ""
                ).strip()

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

                # Store the photo first. The next text message will be
                # attached to this image as property details.
                with sqlite3.connect(DATABASE_FILE) as conn:
                    conn.execute("""
                        INSERT INTO pending_property_requests
                        (whatsapp_number, image_id, image_message_id, property_details)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(whatsapp_number)
                        DO UPDATE SET
                            image_id = excluded.image_id,
                            image_message_id = excluded.image_message_id,
                            property_details = excluded.property_details,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        sender,
                        image_id,
                        message_id,
                        image_caption
                    ))
                    conn.commit()

                logger.info(
                    f"💾 Pending property request saved for {sender}"
                )

                if image_caption:
                    # WhatsApp image captions can carry the details in the
                    # same message, so process immediately in that case.
                    with sqlite3.connect(DATABASE_FILE) as conn:
                        conn.execute("""
                            DELETE FROM pending_property_requests
                            WHERE whatsapp_number = ?
                        """, (sender,))
                        conn.commit()

                    executor.submit(
                        process_image_message,
                        sender,
                        image_id,
                        message_id,
                        image_caption
                    )

                    logger.info(
                        "⚡ Image caption contains details; background processing submitted"
                    )
                else:
                    send_text_message(
                        sender,
                        "📷 Photo received! ❤️\n\n"
                        "এখন property details পাঠান, যেমন:\n"
                        "Price: ₹85 Lakh\n"
                        "Location: Kolkata\n"
                        "BHK: 3BHK\n"
                        "Area: 1450 sq ft\n"
                        "Features: Balcony, modular kitchen, parking"
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
