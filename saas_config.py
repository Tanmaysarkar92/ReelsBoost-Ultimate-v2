import os

APP_NAME = "ReelsBoost"
APP_VERSION = "3.0.0"
APP_ENV = os.getenv("APP_ENV", "production")

# Supported social platforms
SUPPORTED_PLATFORMS = [
    "facebook",
    "youtube",
    "instagram",
    "linkedin",
]

# Subscription plans
SUBSCRIPTION_PLANS = {
    "free": {
        "price_usd": 0,
        "monthly_reels": 3,
    },
    "starter": {
        "price_usd": 19,
        "monthly_reels": 20,
    },
    "pro": {
        "price_usd": 49,
        "monthly_reels": 100,
    },
    "agency": {
        "price_usd": 149,
        "monthly_reels": 300,
    },
}

# Payment providers
PAYMENT_PROVIDERS = [
    "razorpay",
    "stripe",
]

# Features
SAAS_FEATURES = {
    "ai_content_studio": True,
    "ai_agent": True,
    "content_calendar": True,
    "approval_workflow": True,
    "analytics": True,
    "multi_client_agency": True,
    "property_video_generator": True,
}
