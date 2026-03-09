"""Telegram Bot auto-responder using long polling + Anthropic Claude.

Runs as a persistent process. Designed for deployment on Fly.io.
"""

import os
import sys
import time
import traceback
import logging

import httpx
import anthropic

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("telegram-bot")

# --- Config ---
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 30  # seconds for long polling

# --- Anthropic client ---
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Model to use — change to "claude-3-haiku-20240307" for cheaper/faster responses
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# --- Per-user conversation history (in-memory) ---
conversations: dict[int, list[dict]] = {}
MAX_HISTORY = int(os.environ.get("MAX_HISTORY", "20"))

SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a helpful, concise AI assistant responding via Telegram. "
    "Keep responses clear and reasonably brief since this is a chat interface. "
    "Use plain text — avoid markdown. Be friendly and conversational.",
)


def send_message(chat_id: int, text: str) -> None:
    """Send a message back via Telegram Bot API."""
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)]
    with httpx.Client(timeout=30) as http:
        for chunk in chunks:
            resp = http.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": chunk},
            )
            if not resp.json().get("ok"):
                log.warning("sendMessage failed: %s", resp.text)


def send_typing(chat_id: int) -> None:
    """Send typing indicator."""
    try:
        with httpx.Client(timeout=10) as http:
            http.post(
                f"{TELEGRAM_API}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
            )
    except Exception:
        pass  # Non-critical


def get_ai_response(chat_id: int, user_message: str) -> str:
    """Get a response from Claude with conversation history."""
    if chat_id not in conversations:
        conversations[chat_id] = []

    conversations[chat_id].append({"role": "user", "content": user_message})

    if len(conversations[chat_id]) > MAX_HISTORY:
        conversations[chat_id] = conversations[chat_id][-MAX_HISTORY:]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=conversations[chat_id],
        )
        assistant_text = response.content[0].text
        conversations[chat_id].append(
            {"role": "assistant", "content": assistant_text}
        )
        return assistant_text
    except anthropic.APIError as e:
        conversations[chat_id].pop()
        log.error("Anthropic API error: %s", e)
        return f"Sorry, I hit an API error. Please try again in a moment."
    except Exception as e:
        conversations[chat_id].pop()
        log.error("Unexpected error: %s", e)
        return "Sorry, something went wrong. Please try again."


def handle_message(message: dict) -> None:
    """Process a single incoming message."""
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    first_name = message.get("from", {}).get("first_name", "there")

    if not text:
        send_message(chat_id, "I can only process text messages for now.")
        return

    if text == "/start":
        send_message(
            chat_id,
            f"Hey {first_name}! I'm your AI assistant powered by Claude.\n\n"
            "Send me any message and I'll respond.\n\n"
            "Commands:\n"
            "/clear - Reset conversation history\n"
            "/start - Show this message",
        )
        return

    if text == "/clear":
        conversations.pop(chat_id, None)
        send_message(chat_id, "Conversation history cleared. Fresh start!")
        return

    send_typing(chat_id)
    response_text = get_ai_response(chat_id, text)
    send_message(chat_id, response_text)
    log.info(
        "Replied to %s (%d): %s → %s",
        first_name,
        chat_id,
        text[:80],
        response_text[:80],
    )


def poll_loop() -> None:
    """Main long-polling loop. Runs forever."""
    log.info("Bot starting up...")

    # Clear any existing webhook so getUpdates works
    with httpx.Client(timeout=30) as http:
        resp = http.post(
            f"{TELEGRAM_API}/deleteWebhook",
            json={"drop_pending_updates": False},
        )
        log.info("Webhook cleared: %s", resp.json())

    log.info("Listening for messages (model=%s, history=%d)...", MODEL, MAX_HISTORY)

    offset = None

    while True:
        try:
            params: dict = {
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message"],
            }
            if offset is not None:
                params["offset"] = offset

            with httpx.Client(timeout=POLL_TIMEOUT + 10) as http:
                resp = http.get(f"{TELEGRAM_API}/getUpdates", params=params)
                data = resp.json()

            if not data.get("ok"):
                log.error("Telegram error: %s", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                if "message" in update:
                    msg = update["message"]
                    user = msg.get("from", {})
                    log.info(
                        "Message from %s (%s): %s",
                        user.get("first_name", "?"),
                        user.get("id", "?"),
                        msg.get("text", "[no text]")[:100],
                    )
                    try:
                        handle_message(msg)
                    except Exception:
                        log.exception("Error handling message")

        except httpx.TimeoutException:
            continue  # Normal — long poll timed out
        except Exception:
            log.exception("Polling error")
            time.sleep(5)


if __name__ == "__main__":
    poll_loop()
