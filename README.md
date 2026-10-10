# Telugu Trend Agent

An agent that follows what's trending in India and writes short Telugu posts (jokes, facts, Tenglish memes, quotes, explainers). You approve each draft with one tap in Telegram, and approved posts go to your Telegram channel.

**Total running cost: $0.** Everything runs on free tiers.

| Piece | Service | Free limit (check current terms) |
|---|---|---|
| Scheduler + compute | GitHub Actions | Unlimited minutes on public repos; 2,000 min/month on private |
| LLM | Google Gemini API (AI Studio free tier) | Rate-limited free usage; we use about 7 calls/day |
| LLM fallback (optional) | Groq free tier | Rate-limited free usage |
| Trend data | Google Trends RSS + Google News RSS (Telugu) | No key needed |
| Approval + publishing | Telegram Bot API | Free |
| Storage | JSON files committed to this repo | Free |

## How it works

```
06:00 IST  daily.yml
  trends.py   collect Google Trends + Telugu news RSS, drop sensitive items
  Picker      LLM chooses N safe topics + a format for each
  Writer      LLM writes the Telugu post
  Reviewer    LLM scores Telugu quality (1-5), checks safety, fixes or rejects
  Telegram    draft sent to you with Approve / Reject buttons

every 30 min  approvals.yml
  polls Telegram for your taps, publishes approved drafts to the channel
```

Details and diagram: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup (about 15 minutes)

1. **Push this repo to GitHub.** Make it **public** if you want unlimited Actions minutes (no secrets are stored in the repo). Private works too but see the minutes note below.
2. **Gemini key:** create a free key at https://aistudio.google.com/apikey.
3. **Telegram bot:** talk to [@BotFather](https://t.me/BotFather), run `/newbot`, copy the token.
4. **Your chat id:** message [@userinfobot](https://t.me/userinfobot) and copy your id. Then open your new bot and press Start so it can message you.
5. **Channel:** create a public Telegram channel (e.g. `@my_telugu_funny`), add your bot as an admin with permission to post.
6. **GitHub secrets** (Settings > Secrets and variables > Actions):
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_OWNER_CHAT_ID`
   - `TELEGRAM_CHANNEL_ID` (for example `@my_telugu_funny`)
   - optional: `GROQ_API_KEY`
7. **Run it:** Actions tab > "Daily generate" > Run workflow. Drafts show up in your Telegram. Tap Approve; within 30 minutes the "Process approvals" workflow publishes to the channel (or run it manually for instant publishing).

Optional repository variables: `POSTS_PER_DAY` (default 3), `AUTO_PUBLISH` (`true` skips approval; keep `false` until you trust the quality).

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python -m telugu_agent dry-run          # offline, no keys, uses canned data
GEMINI_API_KEY=... python -m telugu_agent generate
```

## Private repo minutes

The approvals poll uses roughly 1 billed minute per run. At every 30 minutes that is about 1,440 min/month, plus about 30 for the daily job, which fits in the 2,000 free private minutes. If you add more schedules, make the repo public or lower the poll frequency.

## Customizing

- Trend sources, blocklist, formats, quality threshold: `src/telugu_agent/config.py`
- Tone, humor rules, safety rules: `prompts/style_guide.md`
- Add your own best-performing posts as examples in the style guide; this is the biggest quality lever for Telugu.

## Roadmap (all still free)

1. Engagement loop: record views/reactions per post and feed top performers back into the style guide.
2. Instagram/Facebook publishing via the Meta Graph API (free, needs a business account and app setup).
3. Reels/Shorts: Telugu text-to-speech plus ffmpeg inside GitHub Actions, upload via the YouTube Data API.
4. Request bot: followers ask for a joke on a topic (needs an always-on webhook; Cloudflare Workers free tier fits).
5. Static archive site on GitHub Pages generated from `data/posts.json`.

## Safety

The agent avoids politics, religion disputes, tragedies and crime by design (blocklist, picker rules, reviewer pass), and every post goes through your approval by default. Telegram button taps are only accepted from `TELEGRAM_OWNER_CHAT_ID`.
