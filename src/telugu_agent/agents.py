"""The three LLM agents: Picker (what to post), Writer (the post), Reviewer (quality + safety)."""
import json

from . import config, llm


def _prompt(name: str, **values) -> str:
    text = (config.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    text = text.replace("{{style_guide}}", (config.PROMPTS_DIR / "style_guide.md").read_text(encoding="utf-8"))
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
    return text


def pick_topics(trends: list[dict], recent: list[str], n: int) -> list[dict]:
    result = llm.complete_json(
        "pick",
        _prompt(
            "picker",
            trends=[{k: t[k] for k in ("title", "source", "summary", "traffic")} for t in trends],
            recent=recent,
            n=str(n),
            formats=", ".join(config.FORMATS),
        ),
        temperature=0.6,
    )
    return result.get("picks", [])[:n]


def write_post(pick: dict) -> dict:
    return llm.complete_json(
        "write",
        _prompt("writer", topic=pick["topic"], angle=pick.get("angle", ""), format=pick["format"]),
        temperature=0.95,
    )


def review_post(pick: dict, draft: dict) -> dict:
    return llm.complete_json(
        "review",
        _prompt("reviewer", topic=pick["topic"], format=pick["format"], draft=draft),
        temperature=0.2,
    )
