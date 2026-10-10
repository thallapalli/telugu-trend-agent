"""Where facts come from. Never from the model's memory: only from sources we can check.

- Heritage and history topics: the Wikipedia article text (the post may only use facts found in it).
- Saamethalu: a curated proverb list in content/saamethalu.json (the model may not invent a proverb).
"""
import json
import random

import requests

from . import config, store

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "telugu-trend-agent/0.3 (cultural heritage page; https://github.com/thallapalli/telugu-trend-agent)"
PROVERBS_FILE = config.ROOT / "content" / "saamethalu.json"


def wikipedia_extract(title: str) -> dict | None:
    """Return {"title", "url", "text"} for a Wikipedia article, or None if it is missing or ambiguous."""
    if config.DRY_RUN:
        return {
            "title": title,
            "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
            "text": f"{title} is a historic heritage site in India associated with the Vijayanagara and Kakatiya "
            "traditions. It is known for fine stone sculpture and notable engineering features.",
        }
    try:
        resp = requests.get(
            WIKI_API,
            params={
                "action": "query",
                "format": "json",
                "prop": "extracts|info",
                "inprop": "url",
                "explaintext": 1,
                "redirects": 1,
                "titles": title,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
        pages = resp.json()["query"]["pages"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"[sources] wikipedia lookup failed for {title!r}: {exc}")
        return None
    page = next(iter(pages.values()), {})
    text = (page.get("extract") or "").strip()
    if "missing" in page or not text:
        print(f"[sources] no Wikipedia article for {title!r}")
        return None
    if "may refer to" in text[:300]:
        print(f"[sources] {title!r} is a disambiguation page, skipping")
        return None
    return {
        "title": page.get("title", title),
        "url": page.get("fullurl") or "https://en.wikipedia.org/wiki/" + page.get("title", title).replace(" ", "_"),
        "text": text[: config.SOURCE_MAX_CHARS],
    }


def load_proverbs() -> list[dict]:
    return json.loads(PROVERBS_FILE.read_text(encoding="utf-8"))["items"]


def pick_proverb(exclude: set[str] = frozenset()) -> dict | None:
    """Choose a proverb not posted before (and not in `exclude`); once all are used, start over."""
    items = [i for i in load_proverbs() if i["proverb"] not in exclude]
    if not items:
        return None
    used = {p["topic"] for p in store.load_posts() if p.get("format") == "saametha"}
    fresh = [item for item in items if item["proverb"] not in used] or items
    return fresh[0] if config.DRY_RUN else random.choice(fresh)


HACKS_FILE = config.ROOT / "content" / "hacks.json"


def pick_hacks(n: int) -> list[dict]:
    """Choose up to n verified hacks not posted yet; once every hack has been used, start over."""
    items = [h for h in json.loads(HACKS_FILE.read_text(encoding="utf-8"))["items"] if h.get("verified") is True]
    used = {p["topic"] for p in store.load_posts() if p.get("format") == "hack"}
    fresh = [h for h in items if h["title"] not in used] or items
    if not config.DRY_RUN:
        random.shuffle(fresh)
    return fresh[:n]


def hack_source_text(hack: dict) -> str:
    facts = "\n".join(f"- {f}" for f in hack["facts"])
    text = f"{hack['title']} ({hack['platform']})\nOfficial source: {hack['source_url']}\n\nFacts:\n{facts}"
    if hack.get("not_stated"):
        text += "\n\nNot stated by the source (do not claim): " + "; ".join(hack["not_stated"])
    return text


def proverb_source_text(item: dict) -> str:
    return f"Proverb: {item['proverb']}\nMeaning: {item['meaning_en']}\nLesson: {item['lesson_en']}"
