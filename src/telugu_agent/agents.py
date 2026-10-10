"""The three LLM agents: Picker (what to post), Writer (the post), Reviewer (quality + safety + accuracy).

Facts never come from the model's memory: the writer and reviewer are handed a SOURCE text
(a Wikipedia article or a curated proverb entry) and must stay inside it.
"""
import json

from . import config, llm


def _prompt(name: str, **values) -> str:
    text = (config.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    text = text.replace("{{style_guide}}", (config.PROMPTS_DIR / "style_guide.md").read_text(encoding="utf-8"))
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
    return text


def pick_topics(trends: list[dict], recent: list[str], slots: list[str]) -> list[dict]:
    """Pick one Wikipedia-backed subject per slot (slots are pillar names like 'ancient_secrets')."""
    result = llm.complete_json(
        "pick",
        _prompt(
            "picker",
            trends=[{k: t[k] for k in ("title", "source", "summary", "traffic")} for t in trends],
            recent=recent,
            slots=slots,
            n=str(len(slots)),
        ),
        temperature=0.6,
    )
    return result.get("picks", [])


def write_post(pick: dict, source_text: str) -> dict:
    return llm.complete_json(
        "write",
        _prompt(
            "writer",
            topic=pick["topic"],
            angle=pick.get("angle", ""),
            format=pick["format"],
            source=source_text,
        ),
        temperature=0.7,
    )


def write_hack(hack: dict, source_text: str) -> dict:
    return llm.complete_json(
        "write_hack",
        _prompt(
            "hacks_writer",
            topic=hack["title"],
            category=hack["category"],
            source=source_text,
            source_url=hack["source_url"],
        ),
        temperature=0.7,
    )


def review_hack(hack: dict, draft: dict, source_text: str) -> dict:
    return llm.complete_json(
        "review_hack",
        _prompt("hacks_reviewer", topic=hack["title"], draft=draft, source=source_text),
        temperature=0.1,
    )


def review_post(pick: dict, draft: dict, source_text: str) -> dict:
    return llm.complete_json(
        "review",
        _prompt("reviewer", topic=pick["topic"], format=pick["format"], draft=draft, source=source_text),
        temperature=0.1,
    )
