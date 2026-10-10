# Telugu Trend Agent

An agent that follows what's trending in India, writes short Telugu posts (jokes, facts, Tenglish memes, quotes, explainers), turns each into an image card, and **publishes to your Instagram account**. You approve each draft with one tap in a private Telegram chat first.

**Total running cost: $0.** Everything runs on free tiers.

| Piece | Service | Free limit (check current terms) |
|---|---|---|
| Scheduler + compute | GitHub Actions | Unlimited minutes on public repos |
| LLM | Google Gemini API (AI Studio free tier) | Rate-limited free usage; about 7 calls/day used |
| LLM fallback (optional) | Groq free tier | Rate-limited free usage |
| Trend data | Google Trends RSS + Google News RSS (Telugu) | No key needed |
| Image cards | Pillow + bundled Noto Sans Telugu font (OFL) | Free |
| Image hosting | Your public GitHub repo (raw URL) | Free |
| Publishing | Instagram Graph API content publishing | Free (max 100 API posts / 24h) |
| Approval inbox | Telegram Bot API | Free |
| Storage | JSON files committed to this repo | Free |

## How it works

```
06:00 IST  daily.yml
  trends.py   collect Google Trends + Telugu news RSS, drop sensitive items
  Picker      LLM chooses N safe topics + a format for each
  Writer      LLM writes the Telugu post
  Reviewer    LLM scores Telugu quality (1-5), checks safety, fixes or rejects
  imagegen    renders a 1080x1350 JPEG card (Instagram needs an image or video)
  git push    card is committed so it has a public URL
  Telegram    card + caption sent to you with Approve / Reject buttons

every 30 min  approvals.yml
  polls Telegram for your taps, then publishes approved cards to Instagram
```

Why the repo must be **public**: Instagram does not accept uploads; Meta downloads the image from a URL. The card is served from `raw.githubusercontent.com` in your repo. No secrets are in the repo.

Details and diagram: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup

### 1. Instagram (the one-time Meta setup, about 20 minutes)

You need a Meta developer app that is yours. While the app stays in Development mode and you are its admin, you can publish to your own account without App Review (Meta's rules change, so confirm in the [content publishing docs](https://developers.facebook.com/docs/instagram-platform/content-publishing)).

1. Switch your Instagram to a **Professional account** (Creator or Business). It's free: Instagram app > Settings > Account type and tools.
2. Create a **Facebook Page** and link it to the Instagram account (Instagram > Edit profile > Page).
3. Create an app at https://developers.facebook.com/apps (type: Business) and add the Instagram product. Note the **App ID** and **App Secret**.
4. In the [Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your app, generate a **User token** with permissions `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`.
5. Run the helper to exchange it for a long-lived Page token and find your Instagram user id:
   ```bash
   python scripts/get_ig_token.py --app-id APP_ID --app-secret APP_SECRET --user-token SHORT_LIVED_TOKEN
   ```
   It prints `IG_USER_ID` and `IG_ACCESS_TOKEN`. A Page token derived from a long-lived user token normally does not expire (I could not confirm this on Meta's publishing page, so check the token in Meta's [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) after step 5). If publishing later fails with an auth error, re-run this step.

### 2. Everything else

1. **Push this repo to GitHub as a public repo.**
2. **Gemini key:** free at https://aistudio.google.com/apikey.
3. **Telegram bot (private approval inbox):** talk to [@BotFather](https://t.me/BotFather), `/newbot`, copy the token. Message [@userinfobot](https://t.me/userinfobot) for your chat id, then open your bot and press Start.
4. **GitHub secrets** (Settings > Secrets and variables > Actions > Secrets):
   - `GEMINI_API_KEY`
   - `IG_USER_ID`, `IG_ACCESS_TOKEN`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`
   - optional: `GROQ_API_KEY`, `TELEGRAM_CHANNEL_ID` (mirror to a public Telegram channel too)
5. **GitHub variables** (same page > Variables): `IG_HANDLE` (shown on each card, e.g. `@my_telugu_page`). Optional: `POSTS_PER_DAY` (default 3), `AUTO_PUBLISH` (`true` skips approval; keep `false` until you trust the quality), `IG_API_VERSION` (default `v24.0`; bump it to Meta's current Graph API version if calls are rejected as outdated).
6. **Run it:** Actions tab > "Daily generate" > Run workflow. Cards show up in Telegram. Tap Approve; within 30 minutes "Process approvals" publishes to Instagram (or run that workflow manually for instant publishing).

Start with 1 post/day and approval on, and check the first few results on Instagram before raising the volume.

**Want Approve in Telegram to publish right away, without opening GitHub?** Set up the free Vercel webhook: [docs/INSTANT_APPROVAL.md](docs/INSTANT_APPROVAL.md).

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python -m telugu_agent dry-run      # offline, no keys: renders cards into data/dryrun/images
```

Telugu rendering needs libraqm (bundled in Pillow wheels on most platforms; on Linux `apt install libraqm0` if the renderer complains).

## Where the facts come from (accuracy)

The AI is never trusted to remember facts. Each post is written from a source text it must stay inside:

- **Heritage and history posts:** the English Wikipedia article for the subject. News headlines are only used to spark ideas. The caption ends with `Source: <article link>` and the Telegram approval card shows the same link so you can check it in seconds.
- **Saamethalu:** only proverbs listed in `content/saamethalu.json`. The AI may explain them but cannot invent one. **Please have a native speaker check that file** and then set `reviewed_by_native` to `true`. Add more proverbs there any time.
- **Code checks before the reviewer:** every number in a post must appear in the source, and the exact proverb must appear in a saametha post.
- **Reviewer:** scores accuracy and lists unsupported claims; any unsupported claim, accuracy below 4, or Telugu quality below 4 drops the post.
- If nothing passes the checks, the run fails (red in Actions) instead of posting something weak.

This greatly reduces invented facts but cannot remove them. Keep approval on and glance at the source link before tapping Approve.

## Life-hacks mode (English carousels)

A second content mode next to Telugu Locals: 5-slide Instagram carousels about phone, software and web tricks (hook, problem, two steps, save-and-share slide), plus a caption and 5 to 8 hashtags. Each one is approved in Telegram like any other post: you get the 5 slides as an album, then the caption, the reviewer's scores, the official link, and the Approve / Reject buttons.

- **Facts come only from `content/hacks.json`.** Every entry was checked against an official help page (Google, Apple, Microsoft) and records what that page does NOT say, so the AI cannot fill the gap with invention. To add one, open the official page, copy only what it says, and set `verified` to `true`. Entries with `verified: false` are never used. Menus change, so re-check old entries now and then.
- **Code checks before the reviewer:** slide word limits (hook 12 words, other slides 15), every number must be in the source, no "most people" / "99%" style claims, a "Comment ..." line and 5 to 8 hashtags must be present.
- **The caption asks viewers to comment `HACK` but does not promise a link in return**, because nothing here auto-replies. The official page link is printed in the caption instead, so the promise is never broken.
- **Same or separate Instagram account:** by default hacks post to the same account as Telugu Locals. To use another account, add `IG_HACKS_USER_ID` and `IG_HACKS_ACCESS_TOKEN` as GitHub secrets (and optionally `IG_HACKS_HANDLE` as a variable). The Telegram approval chat is shared, and each card says which kind it is.
- **Volume:** `HACKS_PER_DAY` (default 1; 0 turns it off). The 7 starter entries rotate and then repeat, so add more entries over time.
- Run only this mode offline: `DRY_RUN=1 PYTHONPATH=src python -m telugu_agent generate-hacks`.

## Customizing

- Trend sources, blocklist, formats, quality thresholds: `src/telugu_agent/config.py`
- Tone, humor rules, safety rules: `prompts/style_guide.md`. Add 10-15 of your favorite Telugu posts as examples; this is the biggest quality lever.
- Card look (colors, sizes, footer): `src/telugu_agent/imagegen.py`

## Things to know

- **Images only.** Instagram needs an image or video for every post, and accepts JPEG only for single images. Cards are JPEG.
- **Repo growth.** Each card is about 150 KB, so 3 per day is roughly 160 MB a year. Delete old files in `data/images/` now and then (published posts don't need them).
- **Failed publishes retry.** If Instagram rejects a post, it stays approved, you get a Telegram note once, and the next 30-minute run retries.
- **Automation on Instagram.** Keep approval on, keep volume modest, and review Meta's platform terms for automated posting.

## Roadmap (all still free)

1. Carousels (joke in 3 slides) and Reels via Telugu text-to-speech + ffmpeg in Actions.
2. Engagement loop: pull post insights from the Graph API and feed top performers back into the style guide.
3. Auto-reply to comments with the same agent.
4. Static archive site on GitHub Pages generated from `data/posts.json`.

## Safety

The agent avoids politics, religion disputes, tragedies and crime by design (blocklist, picker rules, reviewer pass), and every post goes through your approval by default. Telegram button taps are only accepted from `TELEGRAM_OWNER_CHAT_ID`.
