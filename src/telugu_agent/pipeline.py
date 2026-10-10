"""Daily generation + approval handling."""
from . import agents, config, store, telegram, trends


def _format_hashtags(tags: list[str]) -> str:
    return " ".join(t if t.startswith("#") else f"#{t}" for t in tags)


def publish(post: dict) -> None:
    body = post["text"]
    if post.get("hashtags"):
        body += "\n\n" + _format_hashtags(post["hashtags"])
    telegram.send_message(config.TELEGRAM_CHANNEL_ID, body)
    store.update_post(post["id"], status="published", published_at=store.now())


def _send_for_approval(post: dict) -> None:
    review = post["review"]
    header = f"📝 Draft {post['id']} · {post['format']} · {post['topic']}"
    footer = f"Reviewer: Telugu {review.get('telugu_quality', '?')}/5, safety {review.get('safety', '?')}"
    if review.get("issues"):
        footer += "\nNotes: " + "; ".join(review["issues"])
    body = f"{header}\n\n{post['text']}\n\n{_format_hashtags(post.get('hashtags', []))}\n\n{footer}"
    buttons = [[
        {"text": "✅ Approve", "callback_data": f"ap:{post['id']}"},
        {"text": "❌ Reject", "callback_data": f"rj:{post['id']}"},
    ]]
    telegram.send_message(config.TELEGRAM_OWNER_CHAT_ID, body, buttons)


def generate() -> int:
    items = trends.collect()
    print(f"[pipeline] {len(items)} trend items collected")
    if not items:
        return 0

    picks = agents.pick_topics(items, store.recent_topics(), config.POSTS_PER_DAY)
    created = 0
    for pick in picks:
        draft = agents.write_post(pick)
        review = agents.review_post(pick, draft)

        if review.get("verdict") == "reject" or review.get("safety") != "ok":
            print(f"[pipeline] rejected by reviewer: {pick['topic']} {review.get('issues')}")
            continue
        if int(review.get("telugu_quality", 0)) < config.MIN_TELUGU_QUALITY:
            print(f"[pipeline] Telugu quality too low: {pick['topic']}")
            continue

        text = review.get("final_text") or draft["text"]
        post = {
            "id": store.new_id(pick["topic"]),
            "topic": pick["topic"],
            "format": pick["format"],
            "text": text,
            "hashtags": draft.get("hashtags", []),
            "review": review,
            "status": "pending",
            "created_at": store.now(),
        }
        store.add_post(post)
        created += 1

        if config.AUTO_PUBLISH:
            publish(post)
        else:
            _send_for_approval(post)
    print(f"[pipeline] {created} posts created")
    return created


def process_approvals() -> int:
    """Poll Telegram for button taps from the owner; publish approved drafts."""
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
            publish(post)
            telegram.answer_callback(cb["id"], "Published")
            telegram.clear_buttons(chat_id, message_id, "✅ Published to channel")
        else:
            store.update_post(post_id, status="rejected")
            telegram.answer_callback(cb["id"], "Rejected")
            telegram.clear_buttons(chat_id, message_id, "❌ Rejected")
        handled += 1
    store.save_state(state)
    print(f"[approvals] {handled} handled")
    return handled
