#!/usr/bin/env python3
"""Point your Telegram bot at the Vercel function (or back to polling). Run on your own machine.

    export TELEGRAM_BOT_TOKEN=...        # from @BotFather
    export TELEGRAM_WEBHOOK_SECRET=...   # the same random string you put in Vercel
    python scripts/set_telegram_webhook.py set --url https://YOUR-PROJECT.vercel.app/api/telegram
    python scripts/set_telegram_webhook.py info
    python scripts/set_telegram_webhook.py delete      # back to polling every 30 minutes

The bot token is a secret: don't paste it into chats or commit it.
"""
import argparse
import json
import os
import sys

import requests


def call(token: str, method: str, **payload) -> dict:
    resp = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        sys.exit(f"Telegram error from {method}: {data}")
    return data["result"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["set", "info", "delete"])
    ap.add_argument("--url", help="https URL of /api/telegram on your Vercel project (for 'set')")
    args = ap.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN") or sys.exit("Set TELEGRAM_BOT_TOKEN")

    if args.command == "set":
        secret = os.getenv("TELEGRAM_WEBHOOK_SECRET") or sys.exit("Set TELEGRAM_WEBHOOK_SECRET")
        if not args.url or not args.url.startswith("https://"):
            sys.exit("--url must be an https:// URL")
        call(
            token,
            "setWebhook",
            url=args.url,
            secret_token=secret,
            allowed_updates=["callback_query"],
            drop_pending_updates=False,
        )
        print("Webhook set.")
    elif args.command == "delete":
        call(token, "deleteWebhook", drop_pending_updates=False)
        print("Webhook removed; the scheduled workflow will poll Telegram again.")

    info = call(token, "getWebhookInfo")
    info.pop("ip_address", None)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
