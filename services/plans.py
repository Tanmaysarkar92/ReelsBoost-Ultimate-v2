# ============================================================
# REELSBOOST SAAS PLAN CONFIGURATION
# ============================================================

PLANS = {
    "free": {
        "name": "Free",
        "monthly_reels": 3,
        "ai_voice": False,
        "facebook_auto_post": False,
        "youtube_auto_post": False,
        "priority_processing": False,
    },

    "starter": {
        "name": "Starter",
        "monthly_reels": 20,
        "ai_voice": False,
        "facebook_auto_post": False,
        "youtube_auto_post": False,
        "priority_processing": False,
    },

    "pro": {
        "name": "Pro",
        "monthly_reels": 100,
        "ai_voice": True,
        "facebook_auto_post": True,
        "youtube_auto_post": True,
        "priority_processing": False,
    },

    "business": {
        "name": "Business",
        "monthly_reels": 300,
        "ai_voice": True,
        "facebook_auto_post": True,
        "youtube_auto_post": True,
        "priority_processing": True,
    },
}


def get_plan(plan_name):
    """
    Return plan configuration.
    Unknown plans safely fall back to Free.
    """
    return PLANS.get(
        str(plan_name or "free").lower(),
        PLANS["free"]
    )


def get_monthly_reel_limit(plan_name):
    return get_plan(plan_name)["monthly_reels"]


def has_feature(plan_name, feature_name):
    return bool(
        get_plan(plan_name).get(feature_name, False)
    )
