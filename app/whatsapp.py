"""
WhatsApp Cloud API Integration for Zero-Click Kirana Store Operator.
Handles Meta Webhook verification, incoming message parsing, and sending replies.
"""
import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from .config import WHATSAPP_TOKEN, PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN, supabase
from . import tools
from .agent import process_chat_turn

DEFAULT_STORE_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"  # Sharma Kirana Depot Indore


def verify_whatsapp_webhook(mode: Optional[str], token: Optional[str], challenge: Optional[str]) -> Optional[str]:
    """
    Validates Meta webhook subscription during setup.
    """
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge
    return None


def send_whatsapp_message(to_phone: str, text: str) -> Dict[str, Any]:
    """
    Sends a WhatsApp message using Meta Graph API v19.0.
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("[WHATSAPP] Token or Phone Number ID not configured.")
        return {"error": "WhatsApp credentials missing"}

    clean_phone = str(to_phone).strip().replace("+", "").replace("-", "").replace(" ", "")
    # Ensure country code (default to 91 for Indian numbers if 10 digits)
    if len(clean_phone) == 10 and not clean_phone.startswith("91"):
        clean_phone = f"91{clean_phone}"

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "data": data}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"[WHATSAPP ERROR] HTTP {e.code}: {error_body}")
        return {"error": error_body}
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        return {"error": str(e)}


def handle_incoming_whatsapp_payload(payload: Dict[str, Any], store_id: str = DEFAULT_STORE_ID) -> Dict[str, Any]:
    """
    Parses incoming webhook payload from Meta, executes the agent/onboarding loop,
    and dispatches the reply back to the WhatsApp user.
    """
    try:
        entry = payload.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "ignored", "reason": "No messages in payload (e.g. status update)"}

        msg_obj = messages[0]
        sender_phone = msg_obj.get("from", "")
        msg_type = msg_obj.get("type", "")

        msg_text = ""
        if msg_type == "text":
            msg_text = msg_obj.get("text", {}).get("body", "")
        elif msg_type == "button":
            msg_text = msg_obj.get("button", {}).get("text", "")
        elif msg_type == "interactive":
            interactive = msg_obj.get("interactive", {})
            msg_text = interactive.get("button_reply", {}).get("title", "") or interactive.get("list_reply", {}).get("title", "")
        else:
            msg_text = "Namaste"

        if not sender_phone or not msg_text:
            return {"status": "ignored", "reason": "Empty sender or text"}

        # 1. Get or create customer (initiates onboarding if first time)
        customer = tools.get_or_create_customer(store_id, sender_phone)
        order = tools.get_or_create_draft_order(store_id, customer["id"])

        # 2. Process conversation turn (onboarding or 7-step ordering agent)
        agent_result = process_chat_turn(
            store_id=store_id,
            order_id=order["id"],
            phone=sender_phone,
            message=msg_text
        )

        reply = agent_result.get("reply", "Namaste! Order mein kya chahiye?")

        # 3. Send response back to customer's WhatsApp
        send_res = send_whatsapp_message(sender_phone, reply)

        return {
            "status": "processed",
            "sender": sender_phone,
            "reply": reply,
            "delivery": send_res
        }

    except Exception as e:
        print(f"[WHATSAPP WEBHOOK ERROR] {e}")
        return {"status": "error", "error": str(e)}
