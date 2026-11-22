
from datetime import datetime

from services.database import get_connection
from services.plans import PLANS, get_plan


def reserve_reel_slot(user_id, db_path=None):
    """Atomically reserve one monthly reel slot for a SaaS user."""
    month = datetime.now().strftime("%Y-%m")

    with get_connection() as conn:
        try:
            user = conn.execute(
                """
                SELECT plan, subscription_status
                FROM users
                WHERE id = %s
                FOR UPDATE
                """,
                (user_id,),
            ).fetchone()

            if not user:
                return {"allowed": False, "error": "user_not_found"}

            plan_name = str(user["plan"] or "").strip().lower()
            subscription_status = user["subscription_status"]

            if plan_name not in PLANS:
                return {"allowed": False, "error": "invalid_plan"}

            if plan_name != "free" and subscription_status not in (
                "active",
                "authenticated",
            ):
                return {
                    "allowed": False,
                    "error": "subscription_inactive",
                }

            limit = int(get_plan(plan_name)["monthly_reels"])

            usage = conn.execute(
                """
                SELECT id, reels_used
                FROM usage
                WHERE user_id = %s AND month = %s
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (user_id, month),
            ).fetchone()

            if usage:
                usage_id = usage["id"]
                used = int(usage["reels_used"] or 0)

                if used >= limit:
                    return {
                        "allowed": False,
                        "error": "monthly_limit_reached",
                        "limit": limit,
                        "used": used,
                    }

                conn.execute(
                    """
                    UPDATE usage
                    SET reels_used = reels_used + 1,
                        reels_limit = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (limit, usage_id),
                )
                used += 1

            else:
                used = 1
                conn.execute(
                    """
                    INSERT INTO usage
                        (user_id, reels_used, reels_limit, month)
                    VALUES (%s, 1, %s, %s)
                    """,
                    (user_id, limit, month),
                )

            return {
                "allowed": True,
                "plan": plan_name,
                "limit": limit,
                "used": used,
                "remaining": limit - used,
                "month": month,
            }

        except Exception:
            raise
