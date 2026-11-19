
from flask import Blueprint, jsonify, session
from datetime import datetime, timezone

from saas_database import get_db

saas_dashboard = Blueprint(
    "saas_dashboard",
    __name__,
    url_prefix="/api/dashboard"
)


@saas_dashboard.route("/", methods=["GET"])
def dashboard():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Please login first"}), 401

    current_period = datetime.now(timezone.utc).strftime("%Y-%m")

    with get_db() as db:
        user = db.execute(
            """
            SELECT id, email, name, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if not user:
            session.clear()
            return jsonify({"error": "User not found"}), 404

        subscription = db.execute(
            """
            SELECT plan, status, provider, current_period_end
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        usage = db.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM usage
            WHERE user_id = ? AND period = ?
            """,
            (user_id, current_period)
        ).fetchone()

    plan = subscription["plan"] if subscription else "free"

    plan_limits = {
        "free": 3,
        "starter": 20,
        "pro": 100,
        "agency": 300,
    }

    monthly_limit = plan_limits.get(plan, 3)
    reels_used = usage["total"] if usage else 0

    return jsonify({
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "joined": user["created_at"],
        },
        "subscription": {
            "plan": plan,
            "status": subscription["status"] if subscription else "active",
            "provider": subscription["provider"] if subscription else None,
            "current_period_end": (
                subscription["current_period_end"]
                if subscription else None
            ),
        },
        "usage": {
            "reels_used": reels_used,
            "monthly_limit": monthly_limit,
            "remaining": max(0, monthly_limit - reels_used),
            "period": current_period,
        },
        "features": {
            "ai_content_studio": True,
            "ai_agent": True,
            "content_calendar": True,
            "analytics": True,
        }
    })
