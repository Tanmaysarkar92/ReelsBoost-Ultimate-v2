
import os
from flask import Blueprint, request, jsonify, session
from groq import Groq

saas_agent = Blueprint(
    "saas_agent",
    __name__,
    url_prefix="/api/agent"
)

SYSTEM_PROMPT = """
You are ReelsBoost AI, an intelligent social media management assistant.

You understand and respond in Bengali, English, and Banglish.

You help users with:
- Social media content ideas
- Reel scripts and captions
- Hashtags and descriptions
- Facebook and YouTube content planning
- Property marketing videos
- Content calendar suggestions
- Social media growth strategies

Always reply in the user's preferred language.

IMPORTANT:
Never claim that a video was created, scheduled, uploaded,
or published unless the corresponding action was actually
completed by an integrated service.

For actions that are not yet connected, explain that clearly.
"""

@saas_agent.route("/chat", methods=["POST"])
def chat():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Please login first"}), 401

    data = request.get_json(silent=True) or {}

    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Please enter a message"}), 400

    if len(message) > 5000:
        return jsonify({"error": "Message is too long"}), 400

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return jsonify({
            "error": "AI service is not configured yet"
        }), 503

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
                    "content": message
                }
            ],
            temperature=0.7,
            max_tokens=1500
        )

        answer = response.choices[0].message.content

        return jsonify({
            "success": True,
            "user_id": user_id,
            "reply": answer
        })

    except Exception:
        return jsonify({
            "error": "AI assistant is temporarily unavailable"
        }), 503
