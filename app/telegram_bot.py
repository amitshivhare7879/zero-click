"""
Telegram Bot Integration for Zero-Click Kirana Store Operator.
Supports both Webhook mode (POST /webhook/telegram) and optional background Polling.
"""
import os
import json
import urllib.request
import urllib.error
import asyncio
from typing import Dict, Any, Optional
from .config import TELEGRAM_BOT_TOKEN, supabase
from . import tools
from .agent import process_chat_turn

DEFAULT_STORE_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"  # Sharma Kirana Depot Indore


def send_telegram_message(chat_id: str, text: str) -> Dict[str, Any]:
    """
    Sends a message to a Telegram chat using standard Telegram Bot API.
    """
    token = TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("telegram_access_token") or ""
    token = token.strip()
    if not token:
        print("[TELEGRAM] Token not configured in .env.")
        return {"error": "TELEGRAM_BOT_TOKEN not configured"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "data": data}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"[TELEGRAM ERROR] HTTP {e.code}: {error_body}")
        return {"error": error_body}
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")
        return {"error": str(e)}


def handle_telegram_update(update: Dict[str, Any], store_id: str = DEFAULT_STORE_ID) -> Dict[str, Any]:
    """
    Processes an incoming Telegram update payload (Webhook or Polling).
    """
    try:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return {"status": "ignored", "reason": "No message in update"}

        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "").strip()
        from_user = message.get("from", {})
        user_first_name = from_user.get("first_name", "")

        if not chat_id or not text:
            return {"status": "ignored", "reason": "Missing chat_id or text"}

        # 1. Lookup customer by telegram_chat_id
        customer = tools.get_customer_by_telegram(chat_id)

        # Handle /start command
        if text.startswith("/start"):
            if not customer:
                # Create customer awaiting onboarding
                synthetic_phone = f"tg_{chat_id[-6:]}"
                customer = tools.get_or_create_customer(
                    store_id=store_id,
                    phone=synthetic_phone,
                    telegram_chat_id=chat_id
                )
                # Ensure status is awaiting_name
                tools.update_customer_profile(customer["id"], {
                    "onboarding_step": "awaiting_name",
                    "telegram_chat_id": chat_id
                })
                welcome_msg = (
                    f"Namaste {user_first_name or 'Friend'}! 🙏 Welcome to *Sharma Kirana Store* on Telegram!\n\n"
                    "Since this is your first time ordering with us, could you please tell us your *Full Name*?"
                )
                send_telegram_message(chat_id, welcome_msg)
                return {"status": "onboarding_started", "chat_id": chat_id}
            else:
                welcome_back = (
                    f"Namaste {customer.get('name', 'ji')}! 🙏 Welcome back to Sharma Kirana.\n"
                    f"📍 Current delivery address: {customer.get('address', 'Indore')}\n\n"
                    "Aap kya mangwana chahte hain aaj? Jaise:\n"
                    "• '2 packet atta, 1 litre oil aur 3 maggi'\n"
                    "• 'Tata salt aur 1 packet butter bhej do'"
                )
                send_telegram_message(chat_id, welcome_back)
                return {"status": "welcome_back", "chat_id": chat_id}

        # If customer doesn't exist yet, create and start onboarding
        if not customer:
            synthetic_phone = f"tg_{chat_id[-6:]}"
            customer = tools.get_or_create_customer(
                store_id=store_id,
                phone=synthetic_phone,
                telegram_chat_id=chat_id
            )

        order = tools.get_or_create_draft_order(store_id, customer["id"])

        # 2. Process chat turn (runs onboarding state machine or ordering agent)
        agent_result = process_chat_turn(
            store_id=store_id,
            order_id=order["id"],
            phone=customer.get("phone", f"tg_{chat_id}"),
            message=text
        )

        reply = agent_result.get("reply", "Namaste! Kya order karna hai?")

        # 3. Send response to Telegram user
        delivery = send_telegram_message(chat_id, reply)

        return {
            "status": "processed",
            "chat_id": chat_id,
            "reply": reply,
            "delivery": delivery
        }

    except Exception as e:
        print(f"[TELEGRAM UPDATE ERROR] {e}")
        return {"status": "error", "error": str(e)}


async def start_telegram_polling_loop(store_id: str = DEFAULT_STORE_ID):
    """
    Background polling worker for Telegram bot without needing public Webhooks / ngrok.
    """
    token = TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("telegram_access_token") or ""
    token = token.strip()
    if not token:
        print("[TELEGRAM] Polling skipped: TELEGRAM_BOT_TOKEN not provided.")
        return

    print("[TELEGRAM] Starting Telegram Bot background polling loop...")
    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    while True:
        try:
            req_url = f"{url}?offset={offset}&timeout=20"
            req = urllib.request.Request(req_url)
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                updates = data.get("result", [])
                for upd in updates:
                    offset = max(offset, upd.get("update_id", 0) + 1)
                    handle_telegram_update(upd, store_id)
        except Exception as e:
            await asyncio.sleep(5)
        await asyncio.sleep(1)
