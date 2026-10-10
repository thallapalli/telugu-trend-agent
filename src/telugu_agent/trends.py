"""Collect what's trending from free RSS sources."""
import html
import re

import feedparser
import requests

from . import config

_TAG = re.compile(r"<[^>]+>")


def _clean(text: str, limit: int = 200) -> str:
    return html.unescape(_TAG.sub(" ", text or "")).strip()[:limit]


def _blocked(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in config.BLOCKLIST)


def fetch_feed(feed: dict) -> list[dict]:
    try:
        resp = requests.get(feed["url"], timeout=20, headers={"User-Agent": "telugu-trend-agent/0.1"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[trends] {feed['name']} failed: {exc}")
        return []
    parsed = feedparser.parse(resp.content)
    items = []
    for entry in parsed.entries[: config.MAX_PER_FEED]:
        title = _clean(entry.get("title", ""), 160)
        if not title or _blocked(title):
            continue
        items.append(
            {
                "title": title,
                "source": feed["name"],
                "summary": _clean(entry.get("summary", "")),
                "traffic": entry.get("ht_approx_traffic", ""),
            }
        )
    return items


def collect() -> list[dict]:
    """Return de-duplicated trend items across all feeds."""
    if config.DRY_RUN:
        return [
            {
                "title": "పిట్ట కొంచెం కూత ఘనం - సామెత వెనుక జీవన సత్యం",
                "source": "dry_run",
                "summary": "తెలుగు సామెత తాత్పర్యం",
                "traffic": "500K+",
            },
            {
                "title": "లేపాక్షి వీరభద్ర ఆలయం - వేలాడే స్తంభం అద్భుత ఇంజనీరింగ్ రహస్యం",
                "source": "dry_run",
                "summary": "పురాతన ఆలయ వాస్తు విజ్ఞానం",
                "traffic": "300K+",
            },
            {
                "title": "రాణి రుద్రమదేవి కాకతీయ వీరగాథ మరియు చారిత్రక వైభవం",
                "source": "dry_run",
                "summary": "భారతీయ చరిత్ర మరియు వారసత్వం",
                "traffic": "250K+",
            },
        ]
    seen, out = set(), []
    for feed in config.FEEDS:
        for item in fetch_feed(feed):
            key = item["title"].lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out
