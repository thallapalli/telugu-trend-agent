// Telegram webhook (Vercel serverless function).
//
// You tap Approve/Reject on a draft card in Telegram -> Telegram calls this function -> it checks the
// call is genuine and from you, answers the tap instantly, and commits data/decisions/<post_id>.json to
// the GitHub repo. That push starts the "Process approvals" workflow, which publishes to Instagram.
//
// One file per decision means rapid taps on several cards never overwrite or race each other.
//
// Environment variables (Vercel project settings):
//   TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID, TELEGRAM_WEBHOOK_SECRET,
//   GH_TOKEN (fine-grained PAT, this repo only, "Contents: Read and write"), GH_REPO ("owner/name"),
//   GH_BRANCH (optional, default "main")

const crypto = require("crypto");

const REQUIRED = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET", "GH_TOKEN", "GH_REPO"];

function safeEqual(a, b) {
  // Hash first so the comparison is constant-time even when the lengths differ.
  const ha = crypto.createHash("sha256").update(String(a)).digest();
  const hb = crypto.createHash("sha256").update(String(b)).digest();
  return crypto.timingSafeEqual(ha, hb);
}

async function telegram(token, method, payload) {
  try {
    const resp = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return resp.ok;
  } catch (err) {
    console.error(`telegram ${method} failed:`, err.message);
    return false;
  }
}

// Returns "ok" | "exists" | "error"
async function recordDecision(env, action, postId) {
  const url = `https://api.github.com/repos/${env.GH_REPO}/contents/data/decisions/${postId}.json`;
  const content = Buffer.from(
    JSON.stringify({ action, post_id: postId, decided_at: new Date().toISOString() }) + "\n"
  ).toString("base64");
  try {
    const resp = await fetch(url, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${env.GH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "telugu-approval-webhook",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: `decision: ${action} ${postId}`,
        content,
        branch: env.GH_BRANCH,
      }),
    });
    if (resp.status === 200 || resp.status === 201) return "ok";
    if (resp.status === 422) return "exists"; // a decision file for this post is already waiting
    console.error("github contents API failed:", resp.status, (await resp.text()).slice(0, 300));
    return "error";
  } catch (err) {
    console.error("github request failed:", err.message);
    return "error";
  }
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).send("method not allowed");

  const env = { ...process.env, GH_BRANCH: process.env.GH_BRANCH || "main" };
  const missing = REQUIRED.filter((name) => !env[name]);
  if (missing.length) {
    console.error("missing environment variables:", missing.join(", "));
    return res.status(500).send("server not configured");
  }

  // 1) Only Telegram knows the secret we registered with setWebhook.
  if (!safeEqual(req.headers["x-telegram-bot-api-secret-token"] || "", env.TELEGRAM_WEBHOOK_SECRET)) {
    return res.status(401).send("unauthorized");
  }

  // From here on always answer 200, otherwise Telegram keeps retrying the same update.
  let update = req.body;
  if (typeof update === "string") {
    try {
      update = JSON.parse(update);
    } catch {
      return res.status(200).send("ignored");
    }
  }
  const cb = update && update.callback_query;
  if (!cb || !cb.message || !cb.message.chat) return res.status(200).send("ignored");

  // 2) Only the owner's chat may approve or reject. Anyone else is silently ignored.
  if (String(cb.message.chat.id) !== String(env.TELEGRAM_OWNER_CHAT_ID)) return res.status(200).send("ignored");

  const match = /^(ap|rj):([a-f0-9]{8})$/.exec(cb.data || "");
  if (!match) return res.status(200).send("ignored");
  const [, action, postId] = match;

  const outcome = await recordDecision(env, action, postId);
  const token = env.TELEGRAM_BOT_TOKEN;
  const chatId = cb.message.chat.id;

  if (outcome === "ok") {
    const approved = action === "ap";
    await telegram(token, "answerCallbackQuery", {
      callback_query_id: cb.id,
      text: approved ? "Approved. Publishing in about a minute." : "Rejected.",
    });
    await telegram(token, "editMessageReplyMarkup", {
      chat_id: chatId,
      message_id: cb.message.message_id,
      reply_markup: { inline_keyboard: [] }, // remove the buttons so it can't be tapped twice
    });
    await telegram(token, "sendMessage", {
      chat_id: chatId,
      reply_to_message_id: cb.message.message_id,
      text: approved ? "✅ Approved. Publishing to Instagram shortly." : "❌ Rejected.",
    });
  } else if (outcome === "exists") {
    await telegram(token, "answerCallbackQuery", { callback_query_id: cb.id, text: "Already decided." });
  } else {
    await telegram(token, "answerCallbackQuery", {
      callback_query_id: cb.id,
      text: "Could not record your decision. Please tap again.",
      show_alert: true,
    });
  }
  return res.status(200).send("ok");
};
