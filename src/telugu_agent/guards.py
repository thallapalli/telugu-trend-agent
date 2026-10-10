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


def check_post(text: str, source_text: str, proverb: str | None = None) -> list[str]:
    """Return a list of problems; an empty list means the post passed."""
    problems = []
    bad = unsupported_numbers(text, source_text)
    if bad:
        problems.append(f"numbers not found in the source: {', '.join(bad)}")
    if proverb and not contains_proverb(text, proverb):
        problems.append("the proverb is missing or altered")
    return problems
