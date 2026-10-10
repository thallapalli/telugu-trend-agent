"""Deterministic checks on generated posts. The reviewer is the same kind of AI as the writer and can miss
invented facts, so anything checkable by plain code is checked here."""
import re

_TELUGU_DIGITS = str.maketrans("౦౧౨౩౪౫౬౭౮౯", "0123456789")
_NUMBER = re.compile(r"[0-9౦-౯][0-9౦-౯,.]*")


def _numbers(text: str) -> set[str]:
    found = set()
    for token in _NUMBER.findall(text.translate(_TELUGU_DIGITS)):
        token = token.replace(",", "").strip(".")
        if token:
            found.add(token)
    return found


def unsupported_numbers(text: str, source_text: str) -> list[str]:
    """Numbers (years, counts, measurements) in the post that do not appear in the source."""
    return sorted(_numbers(text) - _numbers(source_text))


def _squash(text: str) -> str:
    return re.sub(r"[\s\"'“”‘’.,;:!?\-–—]+", "", text)


def contains_proverb(text: str, proverb: str) -> bool:
    """The exact proverb must appear in the post (ignoring spacing and quote marks)."""
    return _squash(proverb) in _squash(text)


HACK_WORD_LIMITS = {"hook": 12, "problem": 15, "step1": 15, "step2": 15, "cta": 15}
_BANNED_CLAIMS = ("most people", "nobody knows", "no one knows", "99%", "90%", "doctors hate", "guaranteed")
_COMMENT_KEYWORD = re.compile(r"comment\s+[\"'“‘]?[A-Za-z]{3,12}[\"'”’]?", re.IGNORECASE)


def check_hack(slides: dict, caption: str, hashtags: list[str], source_text: str) -> list[str]:
    """Deterministic checks for a life-hack carousel: slide word limits, numbers, banned claims, CTA, hashtags."""
    problems = []
    for key, limit in HACK_WORD_LIMITS.items():
        text = (slides.get(key) or "").replace("**", "").strip()
        if not text:
            problems.append(f"slide '{key}' is empty")
        elif len(text.split()) > limit:
            problems.append(f"slide '{key}' has {len(text.split())} words (limit {limit})")
    everything = " ".join([*(str(v) for v in slides.values()), caption]).replace("**", "")
    bad = unsupported_numbers(everything, source_text)
    if bad:
        problems.append(f"numbers not found in the source: {', '.join(bad)}")
    lowered = everything.lower()
    for phrase in _BANNED_CLAIMS:
        if phrase in lowered:
            problems.append(f"unverifiable claim: '{phrase}'")
    if not _COMMENT_KEYWORD.search(caption):
        problems.append("caption has no 'Comment \"KEYWORD\"' line")
    if len(hashtags) < 5:
        problems.append(f"only {len(hashtags)} hashtags (need 5 to 8)")
    return problems


def check_post(text: str, source_text: str, proverb: str | None = None) -> list[str]:
    """Return a list of problems; an empty list means the post passed."""
    problems = []
    bad = unsupported_numbers(text, source_text)
    if bad:
        problems.append(f"numbers not found in the source: {', '.join(bad)}")
    if proverb and not contains_proverb(text, proverb):
        problems.append("the proverb is missing or altered")
    return problems
