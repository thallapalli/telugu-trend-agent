#!/usr/bin/env python3
"""One-time helper: turn a short-lived Facebook user token into a long-lived Page token and find
your Instagram professional account id.

    python scripts/get_ig_token.py --app-id ... --app-secret ... --user-token ...

Prints IG_USER_ID and IG_ACCESS_TOKEN to put in GitHub Actions secrets. Run it on your own machine;
the output contains a secret, so don't paste it anywhere public.
"""
import argparse
import sys

import requests

VERSION = "v24.0"  # bump to Meta's current Graph API version if rejected
BASE = f"https://graph.facebook.com/{VERSION}"


def get(path: str, **params) -> dict:
    resp = requests.get(f"{BASE}/{path}", params=params, timeout=30)
    if not resp.ok:
        sys.exit(f"Graph API error on {path}: {resp.status_code} {resp.text[:400]}")
    return resp.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--app-secret", required=True)
    ap.add_argument("--user-token", required=True, help="short-lived token from the Graph API Explorer")
    args = ap.parse_args()

    long_lived = get(
        "oauth/access_token",
        grant_type="fb_exchange_token",
        client_id=args.app_id,
        client_secret=args.app_secret,
        fb_exchange_token=args.user_token,
    )["access_token"]

    pages = get("me/accounts", access_token=long_lived, fields="id,name,access_token").get("data", [])
    if not pages:
        sys.exit("No Facebook Pages found for this user. Create a Page and link it to your Instagram account.")

    found = False
    for page in pages:
        info = get(page["id"], fields="instagram_business_account", access_token=page["access_token"])
        ig = info.get("instagram_business_account")
        if ig:
            found = True
            print(f"\nPage: {page['name']}")
            print(f"IG_USER_ID={ig['id']}")
            print(f"IG_ACCESS_TOKEN={page['access_token']}")
    if not found:
        sys.exit("None of your Pages has a linked Instagram professional account.")


if __name__ == "__main__":
    main()
