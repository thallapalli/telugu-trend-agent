"""Tiny JSON-file store committed to the repo (free, versioned, no database)."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from . import config

POSTS = config.DATA_DIR / "posts.json"
STATE = config.DATA_DIR / "state.json"


def _read(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_posts() -> list[dict]:
    return _read(POSTS, [])


def save_posts(posts: list[dict]) -> None:
    _write(POSTS, posts)


def new_id(topic: str) -> str:
    return hashlib.sha1(f"{topic}{now()}".encode()).hexdigest()[:8]


def add_post(post: dict) -> None:
    posts = load_posts()
    posts.append(post)
    save_posts(posts)


def update_post(post_id: str, **fields) -> dict | None:
    posts = load_posts()
    for post in posts:
        if post["id"] == post_id:
            post.update(fields)
            save_posts(posts)
            return post
    return None


def get_post(post_id: str) -> dict | None:
    return next((p for p in load_posts() if p["id"] == post_id), None)


def recent_topics(days: int | None = None) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days or config.RECENT_DAYS)
    out: list[str] = []
    for p in load_posts():
        if datetime.fromisoformat(p["created_at"]) >= cutoff:
            out.append(p["topic"])
            if p.get("source_title"):
                out.append(p["source_title"])
    return out


def load_state() -> dict:
    return _read(STATE, {"update_offset": 0})


def save_state(state: dict) -> None:
    _write(STATE, state)
