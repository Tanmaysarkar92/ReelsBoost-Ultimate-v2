import os
from dotenv import load_dotenv

load_dotenv()

# ==============================
# WhatsApp Cloud API
# ==============================

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# ==============================
# Facebook Page
# ==============================

FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")

# ==============================
# YouTube
# ==============================

YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_TOKEN_FILE = "youtube_token.json"

# ==============================
# AI
# ==============================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ==============================
# Project
# ==============================

APP_NAME = "ReelsBoost Ultimate v2"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

FPS = 30

VIDEO_DURATION = 8

OUTPUT_FOLDER = "outputs"

IMAGE_FOLDER = "downloads"

LOGO_FILE = "assets/logo.png"

MUSIC_FILE = "assets/music.mp3"

FONT_FILE = "assets/font.ttf"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)