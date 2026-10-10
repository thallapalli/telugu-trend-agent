"""Free-tier LLM access: Gemini first, optional Groq fallback. Always returns parsed JSON."""
import json
import re
import time

import requests

from . import config


class LLMError(RuntimeError):
    """retry_after: seconds the provider asked us to wait. permanent: retrying this backend is pointless
    (daily quota used up, wrong model name, bad key), so move on to the next backend immediately."""

    def __init__(self, message: str, retry_after: float | None = None, permanent: bool = False):
        super().__init__(message)
        self.retry_after = retry_after
        self.permanent = permanent


_last_call = 0.0


def _pace() -> None:
    """Free tiers enforce requests-per-minute; space calls out instead of bursting."""
    global _last_call
    wait = config.LLM_MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _retry_after(resp: requests.Response) -> float | None:
    header = resp.headers.get("Retry-After")
    if header and header.replace(".", "", 1).isdigit():
        return float(header)
    match = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', resp.text)  # Gemini's RetryInfo
    return float(match.group(1)) if match else None


def _check(name: str, resp: requests.Response) -> None:
    """Turn an HTTP error into an LLMError that carries the provider's own explanation."""
    if resp.ok:
        return
    detail = f"{name} HTTP {resp.status_code}: {resp.text[:300].strip()}"
    if resp.status_code == 429:
        # A per-day quota will not clear within this run; a per-minute one will.
        raise LLMError(detail, retry_after=_retry_after(resp), permanent="PerDay" in resp.text)
    if resp.status_code >= 500:
        raise LLMError(detail, retry_after=_retry_after(resp))
    raise LLMError(detail, permanent=True)  # 400/401/403/404: our request or key is wrong, retrying won't help


def _gemini(prompt: str, temperature: float) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    resp = requests.post(url, json=body, headers={"x-goog-api-key": config.GEMINI_API_KEY}, timeout=90)
    _check("gemini", resp)
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
    _check("groq", resp)
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
                    "topic": "Lepakshi temple",
                    "wikipedia_title": "Lepakshi",
                    "angle": "Fine stone sculpture of the Vijayanagara era",
                    "format": "ancient_secrets",
                },
                {
                    "topic": "Kakatiya dynasty",
                    "wikipedia_title": "Kakatiya dynasty",
                    "angle": "A Telugu dynasty's lasting legacy",
                    "format": "history_heritage",
                },
            ]
        }
    if task == "write":
        return {
            "skip": False,
            "text": "\"పిట్ట కొంచెం కూత ఘనం\"\nరూపంలో చిన్నదైనా ప్రతిభలో గొప్పగా ఉండవచ్చనేది ఈ సామెత అంతరార్థం.\nమనిషి ఔన్నత్యం బాహ్య రూపంలో కాదు, వారు చేసే సత్కార్యాలలోనే దాగి ఉంటుంది.",
            "hashtags": ["#TeluguHeritage", "#TeluguSaamethalu", "#TeluguCulture", "#AncientWisdom"],
            "facts_used": ["Small bird, mighty call: a small person can have great ability."],
        }
    if task == "review":
        return {
            "verdict": "approve",
            "safety": "ok",
            "telugu_quality": 5,
            "accuracy": 5,
            "unsupported_claims": [],
            "issues": [],
            "final_text": "",
        }
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

    errors: list[str] = []
    for name, fn in backends:
        for attempt in range(3):
            _pace()
            try:
                return _parse(fn(prompt, temperature))
            except (LLMError, requests.RequestException, json.JSONDecodeError, KeyError) as exc:
                print(f"[llm] {name} attempt {attempt + 1} failed: {exc}")
                if isinstance(exc, LLMError) and exc.permanent:
                    errors.append(str(exc))
                    break  # skip the remaining attempts, try the next backend
                if attempt == 2:
                    errors.append(str(exc))
                    break
                delay = exc.retry_after if isinstance(exc, LLMError) and exc.retry_after else 0
                time.sleep(min(max(delay + 1, 10 * 2 ** attempt), 90))
    raise LLMError("all LLM backends failed: " + " | ".join(errors))
