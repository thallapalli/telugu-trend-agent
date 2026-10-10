"""Minimal Telegram Bot API wrapper (free). Used as the private approval inbox. Prints when unconfigured/dry-run."""
import json

import requests

from . import config

API = "https://api.telegram.org/bot{token}/{method}"


def _enabled() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN) and not config.DRY_RUN


def _call(method: str, **payload) -> dict:
    resp = requests.post(API.format(token=config.TELEGRAM_BOT_TOKEN, method=method), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def send_message(chat_id: str, text: str, buttons: list[list[dict]] | None = None) -> dict | None:
    if not _enabled() or not chat_id:
        print(f"[telegram:dry] -> {chat_id or '(no chat)'}\n{text}\n")
        return None
    payload = {"chat_id": chat_id, "text": text}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    return _call("sendMessage", **payload)


def send_photo(chat_id: str, photo_path: str, caption: str, buttons: list[list[dict]] | None = None) -> dict | None:
    if not _enabled() or not chat_id:
        print(f"[telegram:dry] photo {photo_path} -> {chat_id or '(no chat)'}\n{caption}\n")
        return None
    data = {"chat_id": chat_id, "caption": caption[:1000]}
    if buttons:
        data["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    with open(photo_path, "rb") as fh:
        resp = requests.post(
            API.format(token=config.TELEGRAM_BOT_TOKEN, method="sendPhoto"), data=data, files={"photo": fh}, timeout=60
        )
    resp.raise_for_status()
    return resp.json()


def send_media_group(chat_id: str, photo_paths: list[str], caption: str = "") -> dict | None:
    """Send several photos as one swipeable album (Telegram allows 2 to 10)."""
    if not _enabled() or not chat_id:
        print(f"[telegram:dry] album of {len(photo_paths)} -> {chat_id or '(no chat)'}\n{caption}\n")
        return None
    media, files = [], {}
    try:
        for i, path in enumerate(photo_paths):
            files[f"photo{i}"] = open(path, "rb")
            item = {"type": "photo", "media": f"attach://photo{i}"}
            if i == 0 and caption:
                item["caption"] = caption[:1000]
            media.append(item)
        resp = requests.post(
            API.format(token=config.TELEGRAM_BOT_TOKEN, method="sendMediaGroup"),
            data={"chat_id": chat_id, "media": json.dumps(media)},
            files=files,
            timeout=120,
        )
    finally:
        for fh in files.values():
            fh.close()
    resp.raise_for_status()
    return resp.json()


def get_updates(offset: int) -> list[dict]:
    if not _enabled():
        return []
    try:
        return _call("getUpdates", offset=offset, timeout=0, allowed_updates=["callback_query"]).get("result", [])
    except requests.HTTPError as exc:
        # Telegram answers 409 when a webhook is set: taps then arrive via the Vercel function, not polling.
        if exc.response is not None and exc.response.status_code == 409:
            print("[telegram] webhook is active, skipping getUpdates polling")
            return []
        raise


def answer_callback(callback_id: str, text: str) -> None:
    if _enabled():
        _call("answerCallbackQuery", callback_query_id=callback_id, text=text)


def clear_buttons(chat_id: str, message_id: int, status_line: str) -> None:
    if _enabled():
        _call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id, reply_markup={"inline_keyboard": []})
        _call("sendMessage", chat_id=chat_id, text=status_line, reply_to_message_id=message_id)
