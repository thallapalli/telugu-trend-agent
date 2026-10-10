"""All settings. Secrets come from environment variables; everything else is edited here."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "prompts"


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


DRY_RUN = _bool("DRY_RUN")
DATA_DIR = ROOT / "data" / ("dryrun" if DRY_RUN else "")

# --- LLM (free tiers) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Instagram (publish target; Meta Graph API content publishing is free) ---
IG_USER_ID = os.getenv("IG_USER_ID", "")  # Instagram professional account id
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
# Facebook Login path (Page token, recommended): graph.facebook.com
# Instagram Login path: graph.instagram.com
IG_API_HOST = os.getenv("IG_API_HOST", "graph.facebook.com")
IG_API_VERSION = os.getenv("IG_API_VERSION", "v24.0")  # bump to Meta's current version if calls are rejected
IG_HANDLE = os.getenv("IG_HANDLE", "")  # shown in the footer of each card, e.g. @my_telugu_page
# Instagram fetches the image from a public URL. We serve it from this (public) repo.
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")  # set automatically in GitHub Actions
GIT_BRANCH = os.getenv("GIT_BRANCH", os.getenv("GITHUB_REF_NAME", "main"))
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "")  # override, e.g. a GitHub Pages URL

# --- Telegram (free): private approval inbox for drafts; optional public channel mirror ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_CHAT_ID = os.getenv("TELEGRAM_OWNER_CHAT_ID", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")  # optional

# --- Behaviour ---
POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "3"))
AUTO_PUBLISH = _bool("AUTO_PUBLISH", False)
RECENT_DAYS = 7  # don't repeat a topic used in the last N days
MIN_TELUGU_QUALITY = 3  # reviewer score (1-5) below this => post is dropped

FORMATS = ["joke", "fact", "tenglish_meme", "quote", "explainer"]

# --- Trend sources (all free, no API key). Edit freely. ---
FEEDS = [
    {"name": "google_trends_in", "url": "https://trends.google.com/trending/rss?geo=IN"},
    {"name": "news_telugu_top", "url": "https://news.google.com/rss?hl=te&gl=IN&ceid=IN:te"},
    {
        "name": "news_telugu_entertainment",
        "url": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=te&gl=IN&ceid=IN:te",
    },
    {
        "name": "news_telugu_sports",
        "url": "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=te&gl=IN&ceid=IN:te",
    },
]
MAX_PER_FEED = 12

# Cheap deterministic pre-filter (the LLM picker and reviewer also check safety).
BLOCKLIST = [
    "died", "death", "dead", "killed", "murder", "rape", "suicide", "accident", "blast", "riot",
    "మృతి", "మరణ", "హత్య", "ఆత్మహత్య", "అత్యాచార", "ప్రమాదం", "పేలుడు", "అల్లర్లు",
]
