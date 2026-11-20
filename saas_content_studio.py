
import os
from flask import Blueprint, request, jsonify, session
from groq import Groq

content_studio = Blueprint(
    "content_studio",
    __name__,
    url_prefix="/api/content"
)

ALLOWED_TASKS = {
    "caption": "Write an engaging social media caption.",
    "script": "Create a short vertical video reel script.",
    "hashtags": "Generate relevant and effective hashtags.",
    "ideas": "Generate creative social media content ideas.",
    "description": "Write an engaging YouTube video description."
}

SYSTEM_PROMPT = """
You are ReelsBoost AI Content Studio.

You understand Bengali, Banglish and English.

Create original, engaging and professional social media content.

Support:
- Facebook Reels
- YouTube Shorts
- Instagram Reels
- Real estate marketing
- Business promotion
- Personal brands

Follow the user's requested language.
Make content clear, engaging and ready to edit.
Never invent property specifications or business facts.
"""


@content_studio.route("/generate", methods=["POST"])
def generate_content():

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "error": "Please login first"
        }), 401

    data = request.get_json(silent=True) or {}

    task = str(data.get("task", "caption")).lower().strip()
    topic = str(data.get("topic", "")).strip()
    language = str(data.get("language", "Bengali")).strip()
    platform = str(data.get("platform", "Facebook")).strip()

    if task not in ALLOWED_TASKS:
        return jsonify({
            "error": "Unsupported content task"
        }), 400

    if not topic:
        return jsonify({
            "error": "Please enter a topic or content description"
        }), 400

    if len(topic) > 4000:
        return jsonify({
            "error": "Topic is too long"
        }), 400

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return jsonify({
            "error": "AI service is not configured"
        }), 503

    prompt = f"""
Task: {ALLOWED_TASKS[task]}

Platform: {platform}
Language: {language}
Topic: {topic}

Create the requested content.
"""

    try:
        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            model=os.getenv(
                "GROQ_MODEL",
                "llama-3.3-70b-versatile"
            ),
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.8,
            max_tokens=1800
        )

        result = response.choices[0].message.content

        return jsonify({
            "success": True,
            "user_id": user_id,
            "task": task,
            "platform": platform,
            "language": language,
            "content": result
        })

    except Exception:
        return jsonify({
            "error": "Content generation is temporarily unavailable"
        }), 503
