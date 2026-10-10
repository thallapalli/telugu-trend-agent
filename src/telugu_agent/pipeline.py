"""Daily generation + approval handling.

Post lifecycle: pending -> approved -> published   (or pending -> rejected)
Publishing to Instagram only ever happens from process_approvals(), after the image has been
committed and pushed, because Instagram downloads the image from a public URL.
"""
import json
import re
from datetime import datetime, timezone

from . import agents, carousel, config, guards, imagegen, instagram, sources, store, telegram, trends

MAX_HASHTAGS = 30  # Instagram's limit
DECISION_ID = re.compile(r"^[a-f0-9]{8}$")


def _hashtags(tags: list[str]) -> str:
    cleaned = [t if t.startswith("#") else f"#{t}" for t in tags]
    return " ".join(cleaned[:MAX_HASHTAGS])


def _caption(post: dict) -> str:
    caption = post["text"]
    if post.get("source_url") and post["source_url"] not in caption:  # hack captions already end with the link
        caption += f"\n\nSource: {post['source_url']}"
    if post.get("hashtags"):
        caption += "\n\n" + _hashtags(post["hashtags"])
    return caption[:2200]  # Instagram caption limit


def _owner_note(text: str) -> None:
    telegram.send_message(config.TELEGRAM_OWNER_CHAT_ID, text)


def _approval_buttons(post_id: str) -> list[list[dict]]:
    return [[
        {"text": "✅ Approve", "callback_data": f"ap:{post_id}"},
        {"text": "❌ Reject", "callback_data": f"rj:{post_id}"},
    ]]


def _send_carousel_for_approval(post: dict) -> None:
    """Send the slides as an album, then a message with the caption, checks and the Approve/Reject buttons
    (Telegram albums cannot carry buttons)."""
    review = post["review"]
    paths = [str(config.ROOT / p) for p in post["images"]]
    telegram.send_media_group(config.TELEGRAM_OWNER_CHAT_ID, paths, f"📝 Draft {post['id']} · hack · {post['topic']}")
    details = (
        f"Caption that will be posted:\n\n{_caption(post)}\n\n"
        f"Reviewer: accuracy {review.get('accuracy', '?')}/5, safety {review.get('safety', '?')}\n"
        f"Verify against the official page: {post['source_url']}"
    )
    if review.get("issues"):
        details += "\nNotes: " + "; ".join(review["issues"])
    if config.AUTO_PUBLISH:
        telegram.send_message(config.TELEGRAM_OWNER_CHAT_ID, details + "\n\n(auto-publish is ON)")
    else:
        telegram.send_message(config.TELEGRAM_OWNER_CHAT_ID, details, _approval_buttons(post["id"]))


def _send_for_approval(post: dict, image_path) -> None:
    review = post["review"]
    caption = f"📝 Draft {post['id']} · {post['format']} · {post['topic']}\n\n{_caption(post)}\n\n"
    caption += (
        f"Reviewer: accuracy {review.get('accuracy', '?')}/5, Telugu {review.get('telugu_quality', '?')}/5, "
        f"safety {review.get('safety', '?')}"
    )
    if post.get("source_url"):
        caption += f"\nVerify against the source: {post['source_url']}"
    elif post["format"] == "saametha":
        caption += "\nProverb is from content/saamethalu.json (check it is genuine)"
    if review.get("issues"):
        caption += "\nNotes: " + "; ".join(review["issues"])
    if config.AUTO_PUBLISH:
        telegram.send_photo(config.TELEGRAM_OWNER_CHAT_ID, str(image_path), caption + "\n\n(auto-publish is ON)")
        return
    telegram.send_photo(config.TELEGRAM_OWNER_CHAT_ID, str(image_path), caption, _approval_buttons(post["id"]))


def publish(post: dict) -> str | None:
    """Publish to Instagram (and mirror to the optional Telegram channel). Raises on failure.
    Posts with an "images" list are carousels; others are a single image."""
    caption = _caption(post)
    mode = post.get("mode", "heritage")
    carousel = bool(post.get("images"))
    if not (config.DRY_RUN or instagram.configured(mode)):
        raise instagram.InstagramError("Instagram user id / access token are not set")
    if carousel:
        media_id = instagram.publish_carousel(post["images"], caption, mode)
    else:
        media_id = instagram.publish_image(post["image"], caption, mode)  # dry-run: prints only
    if config.TELEGRAM_CHANNEL_ID:
        if carousel:
            telegram.send_media_group(config.TELEGRAM_CHANNEL_ID, [str(config.ROOT / p) for p in post["images"]], caption)
        else:
            telegram.send_photo(config.TELEGRAM_CHANNEL_ID, str(config.ROOT / post["image"]), caption)
    return media_id


def _slots(n: int) -> list[str]:
    """One pillar per post, rotating daily so every pillar gets covered even at 1 post a day."""
    day = datetime.now(timezone.utc).toordinal()
    return [config.FORMATS[(day + i) % len(config.FORMATS)] for i in range(n)]


def _candidates(slots: list[str], headlines: list[dict]) -> list[dict]:
    """Choose what to write about AND fetch its source text first. A post is only ever written from a source."""
    cands: list[dict] = []
    recent = store.recent_topics()
    recent_lower = {r.lower() for r in recent}

    wiki_slots = [s for s in slots if s != "saametha"]
    if wiki_slots:
        for pick in agents.pick_topics(headlines, recent, wiki_slots)[: len(wiki_slots)]:
            if pick.get("format") not in wiki_slots:
                print(f"[pipeline] skipped pick with unexpected format: {pick}")
                continue
            src = sources.wikipedia_extract(pick.get("wikipedia_title") or pick.get("topic", ""))
            if not src:
                print(f"[pipeline] skipped, no usable Wikipedia source for: {pick}")
                continue
            if src["title"].lower() in recent_lower:
                print(f"[pipeline] skipped, posted recently: {src['title']}")
                continue
            cands.append(
                {
                    "topic": pick["topic"],
                    "angle": pick.get("angle", ""),
                    "format": pick["format"],
                    "source_text": f"{src['title']}\n\n{src['text']}",
                    "source_title": src["title"],
                    "source_url": src["url"],
                    "proverb": None,
                }
            )

    taken: set[str] = set()
    for _ in [s for s in slots if s == "saametha"]:
        item = sources.pick_proverb(exclude=taken)
        if not item:
            break
        taken.add(item["proverb"])
        cands.append(
            {
                "topic": item["proverb"],
                "angle": item["lesson_en"],
                "format": "saametha",
                "source_text": sources.proverb_source_text(item),
                "source_title": None,
                "source_url": None,
                "proverb": item["proverb"],
            }
        )
    return cands


def _gate(review: dict) -> str | None:
    """Reason to drop the post, or None if the reviewer's verdict passes."""
    if review.get("verdict") == "reject" or review.get("safety") != "ok":
        return f"reviewer rejected: {review.get('issues')}"
    if review.get("unsupported_claims"):
        return f"unsupported claims: {review['unsupported_claims']}"
    if int(review.get("accuracy") or 0) < config.MIN_ACCURACY:
        return f"accuracy {review.get('accuracy')} < {config.MIN_ACCURACY}"
    if int(review.get("telugu_quality") or 0) < config.MIN_TELUGU_QUALITY:
        return f"Telugu quality {review.get('telugu_quality')} < {config.MIN_TELUGU_QUALITY}"
    return None


def generate() -> int:
    """Telugu Locals heritage posts (saamethalu, ancient secrets, history)."""
    if config.POSTS_PER_DAY <= 0:
        print("[pipeline] heritage mode is off (POSTS_PER_DAY=0)")
        return 0
    headlines = trends.collect()
    print(f"[pipeline] {len(headlines)} headlines collected (inspiration only, never a source of facts)")
    if not headlines:
        print("[pipeline] warning: no headlines today; picking evergreen subjects without them")

    created = 0
    for cand in _candidates(_slots(config.POSTS_PER_DAY), headlines):
        pick = {"topic": cand["topic"], "angle": cand["angle"], "format": cand["format"]}
        draft = agents.write_post(pick, cand["source_text"])
        text = (draft.get("text") or "").strip()
        if draft.get("skip") or not text:
            print(f"[pipeline] writer skipped (not enough in the source): {cand['topic']}")
            continue

        problems = guards.check_post(text, cand["source_text"], cand["proverb"])
        if problems:
            print(f"[pipeline] guard rejected {cand['topic']}: {'; '.join(problems)}")
            continue

        review = agents.review_post(pick, draft, cand["source_text"])
        reason = _gate(review)
        if reason:
            print(f"[pipeline] dropped {cand['topic']}: {reason}")
            continue

        final = (review.get("final_text") or "").strip() or text
        if final != text:  # a polished rewrite must pass the same code checks
            problems = guards.check_post(final, cand["source_text"], cand["proverb"])
            if problems:
                print(f"[pipeline] guard rejected the reviewer's rewrite of {cand['topic']}: {'; '.join(problems)}")
                continue

        post_id = store.new_id(cand["topic"])
        image_path = imagegen.render(final, post_id, config.DATA_DIR / "images")
        post = {
            "id": post_id,
            "topic": cand["topic"],
            "format": cand["format"],
            "text": final,
            "hashtags": draft.get("hashtags", []),
            "image": str(image_path.relative_to(config.ROOT)),
            "source_title": cand["source_title"],
            "source_url": cand["source_url"],
            "facts_used": draft.get("facts_used", []),
            "review": review,
            "status": "approved" if config.AUTO_PUBLISH else "pending",
            "created_at": store.now(),
        }
        store.add_post(post)
        created += 1
        _send_for_approval(post, image_path)

    print(f"[pipeline] {created} posts created")
    if created == 0:
        # Show red in GitHub Actions instead of a silent success when nothing passed the checks.
        raise RuntimeError("no post passed the source, guard and review checks today")
    return created


def _gate_hack(review: dict) -> str | None:
    if review.get("verdict") != "approve" or review.get("safety") != "ok":
        return f"reviewer rejected: {review.get('issues')}"
    if review.get("unsupported_claims"):
        return f"unsupported claims: {review['unsupported_claims']}"
    if int(review.get("accuracy") or 0) < config.MIN_ACCURACY:
        return f"accuracy {review.get('accuracy')} < {config.MIN_ACCURACY}"
    return None


def generate_hacks() -> int:
    """English life-hack carousels, written only from verified entries in content/hacks.json."""
    if config.HACKS_PER_DAY <= 0:
        print("[pipeline] hacks mode is off (HACKS_PER_DAY=0)")
        return 0
    created = 0
    for hack in sources.pick_hacks(config.HACKS_PER_DAY):
        source_text = sources.hack_source_text(hack)
        draft = agents.write_hack(hack, source_text)
        slides = draft.get("slides") or {}
        caption = (draft.get("caption") or "").replace("**", "").strip()
        hashtags = [h for h in draft.get("hashtags", []) if isinstance(h, str)][:8]
        if draft.get("skip") or not slides or not caption:
            print(f"[pipeline] writer skipped (not enough in the source): {hack['title']}")
            continue

        problems = guards.check_hack(slides, caption, hashtags, source_text)
        if problems:
            print(f"[pipeline] guard rejected {hack['title']}: {'; '.join(problems)}")
            continue

        review = agents.review_hack(hack, draft, source_text)
        reason = _gate_hack(review)
        if reason:
            print(f"[pipeline] dropped {hack['title']}: {reason}")
            continue

        post_id = store.new_id(hack["title"])
        paths = carousel.render(slides, post_id, config.DATA_DIR / "images")
        rel = [str(p.relative_to(config.ROOT)) for p in paths]
        post = {
            "id": post_id,
            "mode": "hacks",
            "topic": hack["title"],
            "format": "hack",
            "text": caption,
            "slides": slides,
            "hashtags": hashtags,
            "image": rel[0],
            "images": rel,
            "source_title": hack["title"],
            "source_url": hack["source_url"],
            "facts_used": draft.get("facts_used", []),
            "review": review,
            "status": "approved" if config.AUTO_PUBLISH else "pending",
            "created_at": store.now(),
        }
        store.add_post(post)
        created += 1
        _send_carousel_for_approval(post)

    print(f"[pipeline] {created} hack carousels created")
    if created == 0:
        raise RuntimeError("no hack carousel passed the source, guard and review checks today")
    return created


def generate_all() -> int:
    """Run every mode. One mode failing never blocks the other, but the run still fails (red in Actions)."""
    total, errors = 0, []
    for name, fn in (("heritage", generate), ("hacks", generate_hacks)):
        try:
            total += fn()
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            print(f"[pipeline] {name} mode failed: {exc}")
            errors.append(f"{name}: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return total


def _publish_approved() -> int:
    published = 0
    for post in [p for p in store.load_posts() if p["status"] == "approved"]:
        try:
            media_id = publish(post)
        except Exception as exc:  # keep the post approved so the next run retries
            error = str(exc)[:300]
            print(f"[approvals] publish failed for {post['id']}: {error}")
            if post.get("last_error") != error:  # don't spam the owner every 30 minutes
                store.update_post(post["id"], last_error=error)
                _owner_note(f"⚠️ Instagram publish failed for {post['id']}:\n{error}\nWill retry automatically.")
            continue
        store.update_post(post["id"], status="published", published_at=store.now(), media_id=media_id, last_error=None)
        _owner_note(f"🚀 Published to Instagram: {post['id']} · {post['topic']}")
        published += 1
    return published


def process_decisions() -> int:
    """Apply approve/reject decisions that the Vercel webhook wrote as data/decisions/<post_id>.json.

    One file per decision means taps never overwrite or conflict with each other. Files are
    deleted once applied, and a decision for a post that is no longer pending is ignored.
    """
    folder = config.DATA_DIR / "decisions"
    if not folder.exists():
        return 0
    handled = 0
    for path in sorted(folder.glob("*.json")):
        try:
            decision = json.loads(path.read_text(encoding="utf-8"))
            action, post_id = decision["action"], decision["post_id"]
            if action not in ("ap", "rj") or not DECISION_ID.match(post_id):
                raise ValueError(f"unexpected values {decision!r}")
        except (ValueError, KeyError, TypeError) as exc:
            print(f"[decisions] ignoring invalid {path.name}: {exc}")
            path.unlink()
            continue
        post = store.get_post(post_id)
        if post and post["status"] == "pending":
            if action == "ap":
                store.update_post(post_id, status="approved", approved_at=store.now())
            else:
                store.update_post(post_id, status="rejected")
            handled += 1
            print(f"[decisions] {post_id}: {'approved' if action == 'ap' else 'rejected'}")
        else:
            print(f"[decisions] {post_id}: not pending, ignored")
        path.unlink()
    return handled


def process_approvals() -> int:
    """Handle the owner's decisions (webhook files, plus Telegram polling when no webhook is set),
    then publish everything approved."""
    state = store.load_state()
    handled = 0
    for update in telegram.get_updates(state["update_offset"]):
        state["update_offset"] = update["update_id"] + 1
        cb = update.get("callback_query")
        if not cb:
            continue
        # Security: only the owner may approve.
        if str(cb["message"]["chat"]["id"]) != str(config.TELEGRAM_OWNER_CHAT_ID):
            continue
        action, _, post_id = cb["data"].partition(":")
        post = store.get_post(post_id)
        if not post or post["status"] != "pending":
            telegram.answer_callback(cb["id"], "Already handled")
            continue
        chat_id, message_id = cb["message"]["chat"]["id"], cb["message"]["message_id"]
        if action == "ap":
            store.update_post(post_id, status="approved", approved_at=store.now())
            telegram.answer_callback(cb["id"], "Approved")
            telegram.clear_buttons(chat_id, message_id, "✅ Approved, publishing to Instagram")
        else:
            store.update_post(post_id, status="rejected")
            telegram.answer_callback(cb["id"], "Rejected")
            telegram.clear_buttons(chat_id, message_id, "❌ Rejected")
        handled += 1
    store.save_state(state)
    handled += process_decisions()
    published = _publish_approved()
    print(f"[approvals] {handled} taps handled, {published} published")
    return handled
