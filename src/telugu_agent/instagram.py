"""Publish to Instagram via the Graph API (content publishing).

Single image:  POST /{ig-user-id}/media (image_url, caption) -> wait FINISHED -> POST /{ig-user-id}/media_publish
Carousel:      one child container per image (is_carousel_item=true) -> parent container (media_type=CAROUSEL,
               children=<ids>, caption) -> wait FINISHED -> media_publish
Meta fetches every image_url itself, so each must be publicly reachable when we publish.

mode "heritage" uses IG_USER_ID / IG_ACCESS_TOKEN. mode "hacks" uses IG_HACKS_USER_ID / IG_HACKS_ACCESS_TOKEN
when set (a separate Instagram account), otherwise the main account.
"""
import time

import requests

from . import config


class InstagramError(RuntimeError):
    pass


def _creds(mode: str = "heritage") -> tuple[str, str]:
    if mode == "hacks":
        return (config.IG_HACKS_USER_ID or config.IG_USER_ID, config.IG_HACKS_ACCESS_TOKEN or config.IG_ACCESS_TOKEN)
    return config.IG_USER_ID, config.IG_ACCESS_TOKEN


def configured(mode: str = "heritage") -> bool:
    user_id, token = _creds(mode)
    return bool(user_id and token) and not config.DRY_RUN


def image_url(relative_path: str) -> str:
    if config.IMAGE_BASE_URL:
        return f"{config.IMAGE_BASE_URL.rstrip('/')}/{relative_path}"
    if not config.GITHUB_REPOSITORY:
        raise InstagramError("Set GITHUB_REPOSITORY (automatic in Actions) or IMAGE_BASE_URL for a public image URL")
    return f"https://raw.githubusercontent.com/{config.GITHUB_REPOSITORY}/{config.GIT_BRANCH}/{relative_path}"


def _url(path: str) -> str:
    return f"https://{config.IG_API_HOST}/{config.IG_API_VERSION}/{path}"


def _check(resp: requests.Response) -> dict:
    if not resp.ok:
        raise InstagramError(f"{resp.status_code}: {resp.text[:500]}")
    return resp.json()


def _create_container(user_id: str, token: str, params: dict) -> str:
    """Create a media container. Retries: raw.githubusercontent.com can lag a moment after a push."""
    for attempt in range(4):
        resp = requests.post(_url(f"{user_id}/media"), data={**params, "access_token": token}, timeout=60)
        if resp.ok:
            return resp.json()["id"]
        print(f"[instagram] container attempt {attempt + 1} failed: {resp.status_code} {resp.text[:200]}")
        time.sleep(15)
    raise InstagramError("could not create media container (is the repo public and the image pushed?)")


def _wait_ready(container: str, token: str) -> None:
    for _ in range(24):  # up to ~2 minutes
        status = _check(requests.get(_url(container), params={"fields": "status_code", "access_token": token}, timeout=30))
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise InstagramError(f"container {container} status {code}")
        time.sleep(5)
    raise InstagramError(f"container {container} not ready in time")


def _publish(user_id: str, token: str, creation_id: str) -> str:
    data = _check(
        requests.post(
            _url(f"{user_id}/media_publish"), data={"creation_id": creation_id, "access_token": token}, timeout=60
        )
    )
    return data["id"]


def publish_image(image_relative_path: str, caption: str, mode: str = "heritage") -> str | None:
    """Returns the published media id (None in dry-run / unconfigured)."""
    if not configured(mode):
        print(f"[instagram:dry] would publish {image_relative_path}\n{caption}\n")
        return None
    user_id, token = _creds(mode)
    container = _create_container(user_id, token, {"image_url": image_url(image_relative_path), "caption": caption})
    _wait_ready(container, token)
    return _publish(user_id, token, container)


def publish_carousel(image_relative_paths: list[str], caption: str, mode: str = "hacks") -> str | None:
    """Publish 2 to 10 images as one swipeable carousel post. Returns the media id (None in dry-run)."""
    if not 2 <= len(image_relative_paths) <= 10:
        raise InstagramError(f"a carousel needs 2 to 10 images, got {len(image_relative_paths)}")
    if not configured(mode):
        print(f"[instagram:dry] would publish carousel of {len(image_relative_paths)}: {image_relative_paths}\n{caption}\n")
        return None
    user_id, token = _creds(mode)
    children = []
    for path in image_relative_paths:
        children.append(_create_container(user_id, token, {"image_url": image_url(path), "is_carousel_item": "true"}))
    for child in children:
        _wait_ready(child, token)
    parent = _create_container(
        user_id, token, {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}
    )
    _wait_ready(parent, token)
    return _publish(user_id, token, parent)
