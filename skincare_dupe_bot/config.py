"""Central config, all overridable via environment variables. No secrets committed here."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
VIDEO_OUTPUT_DIR = OUTPUT_DIR / "videos"
READY_TO_UPLOAD_DIR = OUTPUT_DIR / "ready_to_upload"

DB_PATH = os.environ.get("SKINCARE_DB_PATH", str(BASE_DIR / "skincare_dupes.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

# --- Email alerts ---
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # use an app password, never a real account password
ALERT_RECIPIENT = os.environ.get("ALERT_RECIPIENT", "nkamath1988@gmail.com")
PRICE_DROP_ALERT_THRESHOLD_PCT = float(os.environ.get("PRICE_DROP_ALERT_THRESHOLD_PCT", "20"))

# --- Scraping ---
SCRAPE_USER_AGENT = os.environ.get(
    "SCRAPE_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)
SCRAPE_MIN_DELAY_SECONDS = float(os.environ.get("SCRAPE_MIN_DELAY_SECONDS", "3.0"))
SCRAPE_MAX_DELAY_SECONDS = float(os.environ.get("SCRAPE_MAX_DELAY_SECONDS", "7.0"))
SCRAPE_TIMEOUT_SECONDS = float(os.environ.get("SCRAPE_TIMEOUT_SECONDS", "10.0"))

# --- Video generation ---
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
SECONDS_PER_SCENE = float(os.environ.get("SECONDS_PER_SCENE", "3.5"))

# --- Scheduler ---
PRICE_CHECK_CRON = os.environ.get("PRICE_CHECK_CRON", "0 9 * * *")  # daily 9am
VIDEO_GEN_CRON = os.environ.get("VIDEO_GEN_CRON", "0 10 * * *")  # daily 10am
VIDEOS_PER_RUN = int(os.environ.get("VIDEOS_PER_RUN", "1"))

# --- Web dashboard ---
WEB_HOST = os.environ.get("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))
