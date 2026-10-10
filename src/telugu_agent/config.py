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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# llama-3.3-70b-versatile was retired by Groq on 2026-08-16 (HTTP 404). Check console.groq.com/docs/deprecations.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
LLM_MIN_INTERVAL = float(os.getenv("LLM_MIN_INTERVAL", "6"))  # seconds between LLM calls (free-tier RPM)

# --- Instagram (publish target; Meta Graph API content publishing is free) ---
IG_USER_ID = os.getenv("IG_USER_ID", "")  # Instagram professional account id
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
# Facebook Login path (Page token, recommended): graph.facebook.com
# Instagram Login path: graph.instagram.com
IG_API_HOST = os.getenv("IG_API_HOST", "graph.facebook.com")
IG_API_VERSION = os.getenv("IG_API_VERSION", "v24.0")  # bump to Meta's current version if calls are rejected
IG_HANDLE = os.getenv("IG_HANDLE", "")  # shown in the footer of each card, e.g. @my_telugu_page
# Life-hacks carousels can go to a different Instagram account. Leave these empty to post them to the main one.
IG_HACKS_USER_ID = os.getenv("IG_HACKS_USER_ID", "")
IG_HACKS_ACCESS_TOKEN = os.getenv("IG_HACKS_ACCESS_TOKEN", "")
IG_HACKS_HANDLE = os.getenv("IG_HACKS_HANDLE", "")  # footer on hack slides; falls back to IG_HANDLE
# Instagram fetches the image from a public URL. We serve it from this (public) repo.
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")  # set automatically in GitHub Actions
GIT_BRANCH = os.getenv("GIT_BRANCH", os.getenv("GITHUB_REF_NAME", "main"))
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "")  # override, e.g. a GitHub Pages URL

# --- Telegram (free): private approval inbox for drafts; optional public channel mirror ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_CHAT_ID = os.getenv("TELEGRAM_OWNER_CHAT_ID", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")  # optional

# --- Behaviour ---
POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "3"))  # Telugu Locals heritage posts per day
HACKS_PER_DAY = int(os.getenv("HACKS_PER_DAY", "1"))  # English life-hack carousels per day (0 turns the mode off)
AUTO_PUBLISH = _bool("AUTO_PUBLISH", False)
RECENT_DAYS = 7  # don't repeat a topic used in the last N days
MIN_TELUGU_QUALITY = 4  # reviewer score (1-5) below this => post is dropped
MIN_ACCURACY = 4  # reviewer's source-faithfulness score (1-5) below this => post is dropped
SOURCE_MAX_CHARS = 4000  # how much Wikipedia text the writer and reviewer are given

# One pillar per slot, rotating daily so POSTS_PER_DAY=1 still covers all three over time.
FORMATS = ["saametha", "ancient_secrets", "history_heritage"]

# --- Cultural & Heritage sources (all free, no API key). ---
FEEDS = [
    {
        "name": "telugu_culture_literature",
        "url": "https://news.google.com/rss/search?q=%E0%B0%A4%E0%B1%86%E0%B0%B2%E0%B1%81%E0%B0%97%E0%B1%81+%E0%B0%B8%E0%B0%82%E0%B0%B8%E0%B1%8D%E0%B0%95%E0%B1%83%E0%B0%A4%E0%B0%BF+OR+%E0%B0%B8%E0%B0%BE%E0%B0%AE%E0%B1%86%E0%B0%A4%E0%B0%B2%E0%B1%81+OR+%E0%B0%B8%E0%B0%BE%E0%B0%B9%E0%B0%BF%E0%B0%A4%E0%B1%8D%E0%B0%AF%E0%B0%82&hl=te&gl=IN&ceid=IN:te",
    },
    {
        "name": "temple_architecture_secrets",
        "url": "https://news.google.com/rss/search?q=ancient+Indian+temple+architecture+OR+Indian+heritage+archaeology&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "name": "indian_history_heritage",
        "url": "https://news.google.com/rss/search?q=ancient+Indian+history+OR+Indian+heritage+archaeology+OR+Indian+dynasties&hl=en-IN&gl=IN&ceid=IN:en",
    },
    {
        "name": "telugu_heritage_temples",
        "url": "https://news.google.com/rss/search?q=%E0%B0%AA%E0%B1%81%E0%B0%B0%E0%B0%BE%E0%B0%A4%E0%B0%A8+%E0%B0%A6%E0%B1%87%E0%B0%B5%E0%B0%BE%E0%B0%B2%E0%B0%AF%E0%B0%BE%E0%B0%B2%E0%B1%81+OR+%E0%B0%B6%E0%B0%BF%E0%B0%B2%E0%B1%8D%E0%B0%AA%E0%B0%95%E0%B0%B3+OR+%E0%B0%9A%E0%B0%B0%E0%B0%BF%E0%B0%A4%E0%B1%8D%E0%B0%B0&hl=te&gl=IN&ceid=IN:te",
    },
]
MAX_PER_FEED = 12

# Deterministic safety and category filter (drops tragedies, modern politics, film gossip, crimes)
BLOCKLIST = [
    "died", "death", "dead", "killed", "murder", "rape", "suicide", "accident", "blast", "riot",
    "arrest", "scam", "election", "bjp", "congress", "ysrcp", "tdp", "janasena", "cinema review",
    "box office", "collections", "ott release", "remand", "jail",
    "మృతి", "మరణ", "హత్య", "ఆత్మహత్య", "అత్యాచార", "ప్రమాదం", "పేలుడు", "అల్లర్లు",
    "అరెస్ట్", "ఎన్నికలు", "రాజకీయ", "రివ్యూ", "బాక్సాఫీస్", "కలెక్షన్లు", "రిమాండ్", "జైలు",
]
