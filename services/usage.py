import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from services.database import SAAS_DB_PATH
from services.plans import PLANS, get_plan


def reserve_reel_slot(user_id, db_path=None):
    """Atomically reserve one monthly reel slot for a SaaS user."""
    database = Path(db_path or SAAS_DB_PATH)
    month = datetime.now().strftime("%Y-%m")

    with closing(sqlite3.connect(database, timeout=10)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")

            user = conn.execute(
                """
                SELECT plan, subscription_status
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

            if not user:
                conn.rollback()
                return {"allowed": False, "error": "user_not_found"}

            plan_name, subscription_status = user
            plan_name = str(plan_name or "").strip().lower()

            if plan_name not in PLANS:
                conn.rollback()
                return {"allowed": False, "error": "invalid_plan"}

            if plan_name != "free" and subscription_status not in (
                "active",
                "authenticated",
            ):
                conn.rollback()
                return {
                    "allowed": False,
                    "error": "subscription_inactive",
                }

            limit = int(get_plan(plan_name)["monthly_reels"])

            usage = conn.execute(
                """
                SELECT id, reels_used
                FROM usage
                WHERE user_id = ? AND month = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, month),
            ).fetchone()

            if usage:
                usage_id, used = usage
                used = int(used or 0)

                if used >= limit:
                    conn.rollback()
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
                        reels_limit = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
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
                    VALUES (?, 1, ?, ?)
                    """,
                    (user_id, limit, month),
                )

            conn.commit()

            return {
                "allowed": True,
                "plan": plan_name,
                "limit": limit,
                "used": used,
                "remaining": limit - used,
                "month": month,
            }

        except Exception:
            conn.rollback()
            raise
