"""Free-tier LLM access: Gemini first, optional Groq fallback. Always returns parsed JSON."""
import json
import re
import time

import requests

from . import config


class LLMError(RuntimeError):
    pass


def _gemini(prompt: str, temperature: float) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    resp = requests.post(url, json=body, headers={"x-goog-api-key": config.GEMINI_API_KEY}, timeout=90)
    if resp.status_code in (429, 500, 503):
        raise LLMError(f"gemini transient {resp.status_code}")
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt: str, temperature: float) -> str:
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json={
            "model": config.GROQ_MODEL,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def _stub(task: str) -> dict:
    """Canned answers so the whole pipeline can be exercised offline with no keys."""
    if task == "pick":
        return {
            "picks": [
                {
                    "topic": "పిట్ట కొంచెం కూత ఘనం",
                    "angle": "సామర్థ్యం రూపంలో కాదు సాధనలో ఉంటుంది",
                    "format": "saametha",
                },
                {
                    "topic": "లేపాక్షి వీరభద్ర ఆలయం వేలాడే స్తంభం",
                    "angle": "పురాతన భారతీయ వాస్తు ఇంజనీరింగ్ అద్భుతం",
                    "format": "ancient_secrets",
                },
                {
                    "topic": "రాణి రుద్రమదేవి కాకతీయ వీరగాథ",
                    "angle": "ఓరుగల్లు వీర నారి చారిత్రక శౌర్యం",
                    "format": "history_heritage",
                },
            ]
        }
    if task == "write":
        return {
            "text": "\"పిట్ట కొంచెం కూత ఘనం\"\nరూపంలో చిన్నదైనా ప్రతిభలో గొప్పగా ఉండవచ్చనేది ఈ సామెత అంతరార్థం.\nమనిషి ఔన్నత్యం బాహ్య రూపంలో కాదు, వారు చేసే సత్కార్యాలలోనే దాగి ఉంటుంది.",
            "hashtags": ["#TeluguHeritage", "#TeluguSaamethalu", "#TeluguCulture", "#AncientWisdom"],
        }
    if task == "review":
        return {"verdict": "approve", "safety": "ok", "telugu_quality": 5, "issues": [], "final_text": ""}
    raise LLMError(f"no stub for {task}")


def complete_json(task: str, prompt: str, temperature: float = 0.8) -> dict:
    if config.DRY_RUN:
        return _stub(task)

    backends = []
    if config.GEMINI_API_KEY:
        backends.append(("gemini", _gemini))
    if config.GROQ_API_KEY:
        backends.append(("groq", _groq))
    if not backends:
        raise LLMError("Set GEMINI_API_KEY (free) or GROQ_API_KEY")

    last_error: Exception | None = None
    for name, fn in backends:
        for attempt in range(3):
            try:
                return _parse(fn(prompt, temperature))
            except (LLMError, requests.RequestException, json.JSONDecodeError, KeyError) as exc:
                last_error = exc
                print(f"[llm] {name} attempt {attempt + 1} failed: {exc}")
                time.sleep(2 ** attempt * 3)
    raise LLMError(f"all LLM backends failed: {last_error}")
