# Instant approval: tap in Telegram, never open GitHub

Without this, tapping Approve only records your choice on Telegram's side, and the "Process approvals"
workflow finds it on its next 30-minute poll. With this, the tap is handled in about a second and the post
is on Instagram about a minute later. Cost: $0.

```
Telegram tap -> Vercel function (/api/telegram) -> commits data/decisions/<id>.json to the repo
             -> that push starts "Process approvals" -> publishes to Instagram
```

Why a file per decision instead of starting the workflow directly: GitHub keeps only one *waiting* run per
concurrency group, so tapping Approve on three cards quickly could silently drop two of them. Separate files
cannot conflict, and every workflow run processes all pending decisions, so no tap is ever lost.

## Setup (about 15 minutes, in this order)

1. **Merge this branch to `main`.** The workflow's push trigger only works once it is on `main`.

2. **Create a GitHub token** (the function uses it to write decision files):
   GitHub > Settings > Developer settings > Personal access tokens > **Fine-grained tokens** > Generate new token.
   - Repository access: **Only select repositories** > `telugu-trend-agent`
   - Repository permissions: **Contents: Read and write** (nothing else)
   - Expiration: the longest offered. Put a reminder in your calendar; when it expires, taps show a
     "Could not record your decision" alert.

3. **Make a webhook secret:** run `openssl rand -hex 32` and keep the output.

4. **Create the Vercel project:** Vercel dashboard > Add New > Project > import `telugu-trend-agent`.
   Framework preset **Other**, leave build settings empty. Before deploying, add Environment Variables:

   | Name | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | same bot token as in GitHub secrets |
   | `TELEGRAM_OWNER_CHAT_ID` | same chat id as in GitHub secrets |
   | `TELEGRAM_WEBHOOK_SECRET` | the random string from step 3 |
   | `GH_TOKEN` | the token from step 2 |
   | `GH_REPO` | `thallapalli/telugu-trend-agent` |

   Deploy. Vercel gives you a URL like `https://telugu-trend-agent.vercel.app`.

5. **Check the function is public:**
   `curl -i https://YOUR-PROJECT.vercel.app/api/telegram` should answer `405 method not allowed`.
   If you get a Vercel login page or `401` instead, turn off Deployment Protection for this project
   (Project > Settings > Deployment Protection).

6. **Point Telegram at it** (on your own machine, the bot token is a secret):
   ```bash
   export TELEGRAM_BOT_TOKEN=...
   export TELEGRAM_WEBHOOK_SECRET=...        # same string as step 3
   python scripts/set_telegram_webhook.py set --url https://YOUR-PROJECT.vercel.app/api/telegram
   ```
   The output should show your URL and `pending_update_count`. Run `... info` any time to re-check, and
   look at `last_error_message` there if taps ever do nothing.

7. **Test:** run "Daily generate" (or use an existing pending card), tap Approve, and watch. You should see
   a toast, the buttons disappear, "Approved. Publishing to Instagram shortly", then in the Actions tab a
   "Process approvals" run started by a push, and finally "Published to Instagram" in Telegram.

## How it stays safe

- Only Telegram knows the webhook secret; requests without it get 401 and do nothing.
- Only taps from your own chat id are accepted; anyone else is ignored.
- The callback data must match `ap:` or `rj:` plus 8 hex characters, so it cannot be used to write other paths.
- The GitHub token can only write file contents in this one repo, and cannot change settings or secrets.
- Instagram credentials never go to Vercel. Only the GitHub workflow can publish.

## Good to know

- **The 30-minute schedule stays on** as a safety net: it retries any failed Instagram publish. With a webhook
  active it no longer polls Telegram (Telegram refuses polling while a webhook is set, and the code handles that).
- **Back to polling:** `python scripts/set_telegram_webhook.py delete`.
- **Vercel's free plan** is intended for non-commercial use. If the page becomes a business, the same function
  runs on Cloudflare Workers' free plan with small changes.
- Each tap adds a small commit (`decision: ap <id>`) to the repo history, followed by the bot's `data: approvals` commit.
- Pushes made by the workflow itself do not start new workflow runs, so there are no loops.
