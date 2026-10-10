"""Daily generation + approval handling.

Post lifecycle: pending -> approved -> published   (or pending -> rejected)
Publishing to Instagram only ever happens from process_approvals(), after the image has been
committed and pushed, because Instagram downloads the image from a public URL.
"""
from . import agents, config, imagegen, instagram, store, telegram, trends

MAX_HASHTAGS = 30  # Instagram's limit


def _hashtags(tags: list[str]) -> str:
    cleaned = [t if t.startswith("#") else f"#{t}" for t in tags]
    return " ".join(cleaned[:MAX_HASHTAGS])


def _caption(post: dict) -> str:
    caption = post["text"]
    if post.get("hashtags"):
        caption += "\n\n" + _hashtags(post["hashtags"])
    return caption[:2200]  # Instagram caption limit


def _owner_note(text: str) -> None:
    telegram.send_message(config.TELEGRAM_OWNER_CHAT_ID, text)


def _send_for_approval(post: dict, image_path) -> None:
    review = post["review"]
    caption = f"📝 Draft {post['id']} · {post['format']} · {post['topic']}\n\n{_caption(post)}\n\n"
    caption += f"Reviewer: Telugu {review.get('telugu_quality', '?')}/5, safety {review.get('safety', '?')}"
    if review.get("issues"):
        caption += "\nNotes: " + "; ".join(review["issues"])
    if config.AUTO_PUBLISH:
        telegram.send_photo(config.TELEGRAM_OWNER_CHAT_ID, str(image_path), caption + "\n\n(auto-publish is ON)")
        return
    buttons = [[
        {"text": "✅ Approve", "callback_data": f"ap:{post['id']}"},
        {"text": "❌ Reject", "callback_data": f"rj:{post['id']}"},
    ]]
    telegram.send_photo(config.TELEGRAM_OWNER_CHAT_ID, str(image_path), caption, buttons)


def publish(post: dict) -> str | None:
    """Publish to Instagram (and mirror to the optional Telegram channel). Raises on failure."""
    caption = _caption(post)
    if config.DRY_RUN:
        media_id = instagram.publish_image(post["image"], caption)  # prints only
    elif instagram.configured():
        media_id = instagram.publish_image(post["image"], caption)
    else:
        raise instagram.InstagramError("IG_USER_ID / IG_ACCESS_TOKEN are not set")
    if config.TELEGRAM_CHANNEL_ID:
        telegram.send_photo(config.TELEGRAM_CHANNEL_ID, str(config.ROOT / post["image"]), caption)
    return media_id


def generate() -> int:
    items = trends.collect()
    print(f"[pipeline] {len(items)} trend items collected")
    if not items:
        # Fail the run so a broken feed shows up red in GitHub Actions instead of a silent "success".
        raise RuntimeError("no trend items collected: all feeds failed or were filtered out")

    picks = agents.pick_topics(items, store.recent_topics(), config.POSTS_PER_DAY)
    created = 0
    for pick in picks:
        if pick.get("format") not in config.FORMATS:
            print(f"[pipeline] skipped, not one of the allowed pillars {config.FORMATS}: {pick}")
            continue
        draft = agents.write_post(pick)
        review = agents.review_post(pick, draft)

        if review.get("verdict") == "reject" or review.get("safety") != "ok":
            print(f"[pipeline] rejected by reviewer: {pick['topic']} {review.get('issues')}")
            continue
        if int(review.get("telugu_quality", 0)) < config.MIN_TELUGU_QUALITY:
            print(f"[pipeline] Telugu quality too low: {pick['topic']}")
            continue

        post_id = store.new_id(pick["topic"])
        text = review.get("final_text") or draft["text"]
        image_path = imagegen.render(text, post_id, config.DATA_DIR / "images")
        post = {
            "id": post_id,
            "topic": pick["topic"],
            "format": pick["format"],
            "text": text,
            "hashtags": draft.get("hashtags", []),
            "image": str(image_path.relative_to(config.ROOT)),
            "review": review,
            "status": "approved" if config.AUTO_PUBLISH else "pending",
            "created_at": store.now(),
        }
        store.add_post(post)
        created += 1
        _send_for_approval(post, image_path)
    print(f"[pipeline] {created} posts created")
    return created


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


def process_approvals() -> int:
    """Poll Telegram for the owner's button taps, then publish everything approved."""
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
    published = _publish_approved()
    print(f"[approvals] {handled} taps handled, {published} published")
    return handled
