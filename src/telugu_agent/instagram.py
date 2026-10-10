"""Publish a single-image post via the Instagram Graph API (content publishing).

Flow: POST /{ig-user-id}/media (image_url, caption) -> poll status -> POST /{ig-user-id}/media_publish.
Meta fetches image_url itself, so it must be publicly reachable when we publish.
"""
import time

import requests

from . import config


class InstagramError(RuntimeError):
    pass


def configured() -> bool:
    return bool(config.IG_USER_ID and config.IG_ACCESS_TOKEN) and not config.DRY_RUN


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


def publish_image(image_relative_path: str, caption: str) -> str | None:
    """Returns the published media id (None in dry-run / unconfigured)."""
    if not configured():
        print(f"[instagram:dry] would publish {image_relative_path}\n{caption}\n")
        return None

    token = {"access_token": config.IG_ACCESS_TOKEN}
    url = image_url(image_relative_path)

    # 1) create container (retry: the raw.githubusercontent URL can lag a moment after a push)
    container = None
    for attempt in range(4):
        resp = requests.post(
            _url(f"{config.IG_USER_ID}/media"), data={"image_url": url, "caption": caption, **token}, timeout=60
        )
        if resp.ok:
            container = resp.json()["id"]
            break
        print(f"[instagram] container attempt {attempt + 1} failed: {resp.status_code} {resp.text[:200]}")
        time.sleep(15)
    if not container:
        raise InstagramError("could not create media container (is the repo public and the image pushed?)")

    # 2) wait until Meta has fetched and processed the image
    for _ in range(24):  # up to ~2 minutes
        status = _check(requests.get(_url(container), params={"fields": "status_code", **token}, timeout=30))
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise InstagramError(f"container status {code}")
        time.sleep(5)
    else:
        raise InstagramError("container not ready in time")

    # 3) publish
    data = _check(
        requests.post(_url(f"{config.IG_USER_ID}/media_publish"), data={"creation_id": container, **token}, timeout=60)
    )
    return data["id"]
