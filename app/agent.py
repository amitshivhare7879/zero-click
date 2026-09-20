"""
Agent module for Zero-Click Kirana Store Operator.
Coordinates the 7-step autonomous agent loop:
  1. Understand intent & Customer Onboarding state
  2. Identify requested products
  3. Check inventory/pricing & Alternatives
  4. Calculate order total
  5. Check and flag anomalies
  6. Update draft order
  7. Confirm customer & deduct inventory
"""
import re
import base64
from typing import Tuple, List, Dict, Any, Optional
from .config import GEMINI_API_KEY, HAS_GEMINI_KEY
from . import tools
from .models import AuditStep

# Optional GenAI import
genai = None
if HAS_GEMINI_KEY:
    try:
        import google.generativeai as genai_module
        genai_module.configure(api_key=GEMINI_API_KEY)
        genai = genai_module
    except Exception as e:
        print(f"[AGENT] Notice: Gemini SDK initialization error: {e}")
        genai = None


SYSTEM_INSTRUCTION = """
You are an elite autonomous store operator AI for an Indian neighborhood kirana store.
Customers message you in conversational Hinglish, Hindi, or English to place and modify orders.

Your strictly followed 7-step loop:
1. Understand Customer Intent: Determine if customer wants to add products, modify quantities, remove an item, ask questions, or confirm their order.
2. Identify Requested Product(s): Extract product names, quantities, and units.
3. Check Inventory & Pricing: Always call lookup_product(store_id, product_name) for THIS store. If stock is 0, proactively offer alternatives.
4. Calculate Total: Tools automatically compute line totals and grand totals.
5. Check & Flag Anomalies: For every product being added or updated, call check_and_flag_anomaly(store_id, order_id, product, qty).
6. Update Order: Call add_item, edit_qty, or remove_item to update the draft order. If product is unavailable or stock is 0, call suggest_alternatives.
7. Confirm Order: When customer says 'confirm', 'haan', 'pakka', 'yes', 'bhej do', call confirm_order(order_id).

Tone: Friendly, concise, warm Indian shopkeeper (Bhaiya/Didi), responding in natural Hinglish or customer's language. Never output raw technical IDs.
"""

AGENT_TOOLS = [
    tools.lookup_product,
    tools.suggest_alternatives,
    tools.add_item,
    tools.remove_item,
    tools.edit_qty,
    tools.check_and_flag_anomaly,
    tools.confirm_order,
]

_gemini_sessions: Dict[Tuple[str, str], Any] = {}

HINDI_NUMBERS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
    "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "half": 1, "aadha": 1
}


def parse_quantity_and_items(text: str) -> List[Tuple[str, int]]:
    """
    Parses compound Hinglish messages like:
    '2 maggie, 1kg aata, 1kg poha'
    or '2kg poha krdo'
    into [('maggie', 2), ('aata', 1), ('poha', 1)]
    """
    clean_text = text.lower()
    # Separate numbers attached to units: '1kg' -> '1 kg', '2maggie' -> '2 maggie'
    clean_text = re.sub(r"(\d+)\s*([a-zA-Z]+)", r"\1 \2", clean_text)

    segments = re.split(r"[,+;]|\s+aur\s+", clean_text)
    parsed_items = []

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        num = 1
        num_match = re.search(r"\b(\d+)\b", seg)
        if num_match:
            num = int(num_match.group(1))
            name_part = re.sub(r"\b\d+\b", "", seg)
        else:
            found_word_num = False
            for word, val in HINDI_NUMBERS.items():
                if re.search(rf"\b{word}\b", seg):
                    num = val
                    name_part = re.sub(rf"\b{word}\b", "", seg)
                    found_word_num = True
                    break
            if not found_word_num:
                name_part = seg

        name_clean = re.sub(
            r"\b(bhaiya|bhej\s*do|chahiye|de\s*do|packet|packets|pkt|pkts|pouch|pouches|pc|pcs|bottle|bottles|kg|kilo|gm|g|gram|grams|l|lt|ltr|litre|liter|ml|ek|do|teen|bhi|hata|hatao|kar\s*do|kardo|krdo|kr\s*do)\b",
            "",
            name_part
        ).strip()
        if name_clean and len(name_clean) >= 2:
            parsed_items.append((name_clean, num))

    return parsed_items


def check_and_handle_onboarding(store_id: str, phone: str, message: str) -> Optional[Dict[str, Any]]:
    """
    Handles first-time user conversational registration:
    Step 1: Asks for Full Name (ignores plain greetings like 'Hi')
    Step 2: Asks for Delivery Address
    Step 3: Saves and activates grocery shopping mode
    """
    customer = tools.get_or_create_customer(store_id, phone)
    step = customer.get("onboarding_step", "completed")
    msg_strip = message.strip().lower()
    GREETINGS = {"hi", "hello", "hey", "namaste", "pranam", "start", "/start", "hlo", "helo", "namaskar"}

    # If customer says 'mera naam X hai', update their name anytime
    name_change_match = re.search(r"(?:mera\s*naam|my\s*name\s*is)\s*[:=]?\s*([a-zA-Z\s]+)", message, flags=re.IGNORECASE)
    if name_change_match:
        new_name = name_change_match.group(1).strip().title()
        tools.update_customer_profile(customer["id"], {"name": new_name})
        customer["name"] = new_name

    if step == "awaiting_name":
        # Don't save greetings as a person's name!
        if msg_strip in GREETINGS:
            reply = (
                "Namaste! 🙏 Sharma Kirana mein aapka swagat hai.\n"
                "Kripya apna *Full Name* batayein taaki hum aapka profile setup kar sakein:"
            )
            return {
                "reply": reply,
                "audit_steps": [
                    AuditStep(step_number=1, title="First-Time Onboarding", detail="Received greeting. Prompting for customer name.")
                ],
                "flags": [],
                "suggested_alternatives": [],
                "onboarding_step": "awaiting_name",
                "customer": customer
            }

        clean_name = re.sub(r"^(mera\s*naam|my\s*name\s*is|i\s*am|naam\s*hai|naam)\s*[:=]?\s*", "", message, flags=re.IGNORECASE).strip()
        if not clean_name:
            clean_name = message.strip().title()
        else:
            clean_name = clean_name.title()

        tools.update_customer_profile(customer["id"], {
            "name": clean_name,
            "onboarding_step": "awaiting_address"
        })

        reply = (
            f"Bahut badhiya, {clean_name}! 😊\n"
            f"Delivery ke liye kripya apna *Address / Flat No.* likh dijiye (jaise: Flat 204, Silver Springs, Indore):"
        )
        return {
            "reply": reply,
            "audit_steps": [
                AuditStep(
                    step_number=1,
                    title="First-Time Onboarding",
                    detail=f"Captured customer name: '{clean_name}'. Next: Requesting delivery address."
                )
            ],
            "flags": [],
            "suggested_alternatives": [],
            "onboarding_step": "awaiting_address",
            "customer": {**customer, "name": clean_name, "onboarding_step": "awaiting_address"}
        }

    elif step == "awaiting_address":
        address = message.strip()
        updated_cust = tools.update_customer_profile(customer["id"], {
            "address": address,
            "onboarding_step": "completed"
        })

        cust_name = updated_cust.get("name", "Customer")
        reply = (
            f"Dhanyawad, {cust_name}! 🎉 Aapka profile save ho gaya hai.\n"
            f"📍 Delivery Address: {address}\n\n"
            f"Aap abhi sidhe grocery items mangwa sakte hain! Jaise:\n"
            f"• '2 packet atta, 1 litre oil aur 3 maggi bhej do'\n"
            f"• 'Kya fresh doodh aur butter available hai?'"
        )
        return {
            "reply": reply,
            "audit_steps": [
                AuditStep(
                    step_number=1,
                    title="First-Time Onboarding Completed",
                    detail=f"Saved delivery address for {cust_name}: '{address}'. Ready for grocery orders."
                )
            ],
            "flags": [],
            "suggested_alternatives": [],
            "onboarding_step": "completed",
            "customer": updated_cust
        }

    return None


def run_deterministic_agent(store_id: str, order_id: str, phone: str, message: str) -> Dict[str, Any]:
    """
    Executes the full 7-step autonomous loop deterministically.
    """
    msg_lower = message.strip().lower()
    audit_steps: List[AuditStep] = []
    flags_raised: List[Dict[str, Any]] = []
    suggested_alts: List[Dict[str, Any]] = []
    reply = ""

    # Step 1: Understand Intent
    is_confirm = any(w in msg_lower for w in ["confirm", "haan", "pakka", "place order", "yes", "kar do confirm", "order kar do", "bhej do"])
    is_remove = any(w in msg_lower for w in ["hata", "remove", "delete", "cancel", "mat bhejo", "drop"])
    is_edit_qty = any(w in msg_lower for w in ["ek aur", "kam kar", "badha", "badhao", "badha do", "kardo", "kar do", "change"])
    is_history = any(w in msg_lower for w in ["history", "pichla", "purana", "past order", "previous order", "last order", "purane order", "orders dikhao", "my orders"])

    audit_steps.append(AuditStep(
        step_number=1,
        title="Intent Decomposition",
        detail=f"Parsed intent: {'ORDER_HISTORY' if is_history else 'CONFIRM_ORDER' if is_confirm else 'REMOVE_ITEM' if is_remove else 'EDIT_QTY' if is_edit_qty else 'ORDER_ITEMS'}"
    ))

    # Case 0: Customer Asks for Past Order History
    if is_history:
        customer = tools.get_customer_by_phone(phone, store_id)
        if customer:
            history = tools.get_customer_order_history(customer["id"])
            confirmed_history = [o for o in history if o.get("status") == "confirmed"]
            if not confirmed_history:
                reply = f"Namaste {customer.get('name', '')}! Aapka abhi tak koi confirmed order record nahi hai. Naya order place karne ke liye items batayein!"
            else:
                lines = [f"📦 *Aapke Pichle Orders ({len(confirmed_history)})*:"]
                for idx, o in enumerate(confirmed_history[:5], 1):
                    item_names = ", ".join([f"{i['qty']}x {i['product_name']}" for i in o.get("order_items", [])])
                    lines.append(f"{idx}. Order #{o['id'][:8].upper()} (₹{o['total']:.2f}) - {o.get('confirmed_at') or o.get('created_at')}")
                    if item_names:
                        lines.append(f"   Items: {item_names}")
                lines.append("\nInme se koi order repeat karna ho toh batayein!")
                reply = "\n".join(lines)
            return {
                "reply": reply,
                "audit_steps": [AuditStep(step_number=1, title="Customer Order History", detail=f"Fetched {len(confirmed_history)} confirmed orders from database")],
                "flags": [],
                "suggested_alternatives": []
            }

    # Case A: Customer Confirms Order
    if is_confirm:
        audit_steps.append(AuditStep(
            step_number=2,
            title="Order Verification",
            detail="Checking active draft order items before final confirmation"
        ))
        res = tools.confirm_order(order_id)
        if "error" in res:
            reply = "Aapka cart abhi khaali hai. Pehle kuch items order karein! (e.g. '2 packet atta aur oil bhej do')"
        else:
            audit_steps.append(AuditStep(
                step_number=6,
                title="Atomic Stock Deduction",
                detail=f"Deducted live inventory for {len(res.get('items', []))} line item(s) in Supabase"
            ))
            audit_steps.append(AuditStep(
                step_number=7,
                title="Itemized Bill Generation",
                detail=f"Generated Kirana bill: Total ₹{res['total']}"
            ))
            reply = f"Aapka order confirm ho gaya hai! 🎉\n\n{res['bill']}"

        return {
            "reply": reply,
            "audit_steps": audit_steps,
            "flags": flags_raised,
            "suggested_alternatives": suggested_alts
        }

    # Case B: Remove Item
    if is_remove:
        clean_target = re.sub(r"\b(hata\s*do|hatao|remove|delete|mat\s*bhejo|bhaiya)\b", "", msg_lower).strip()
        audit_steps.append(AuditStep(
            step_number=2,
            title="Product Identification",
            detail=f"Identified item to remove: '{clean_target}'"
        ))
        res = tools.remove_item(order_id, clean_target)
        audit_steps.append(AuditStep(
            step_number=6,
            title="Cart Modification",
            detail=f"Removed '{clean_target}' from draft order"
        ))
        audit_steps.append(AuditStep(
            step_number=4,
            title="Total Calculation",
            detail=f"Updated order total: ₹{res['total']}"
        ))
        reply = f"Theek hai, '{clean_target}' cart se hata diya hai. Abhi total: ₹{res['total']:.2f}. Kuch aur chahiye?"
        return {
            "reply": reply,
            "audit_steps": audit_steps,
            "flags": flags_raised,
            "suggested_alternatives": suggested_alts
        }

    # Case C: Edit Quantity
    if is_edit_qty and ("ek aur" in msg_lower or "1 aur" in msg_lower):
        clean_target = re.sub(r"\b(ek\s*aur|1\s*aur|kar\s*do|bhaiya)\b", "", msg_lower).strip()
        items = tools.get_order_with_items(order_id).get("items", [])
        matched = None
        for it in items:
            if clean_target in it["product_name"].lower() or any(w in it["product_name"].lower() for w in clean_target.split()):
                matched = it
                break

        if matched:
            new_qty = matched["qty"] + 1
            tools.edit_item_qty_by_id(order_id, matched["id"], new_qty)
            audit_steps.append(AuditStep(
                step_number=6,
                title="Quantity Stepper Update",
                detail=f"Updated {matched['product_name']} quantity to {new_qty}"
            ))
            res = tools.recalc_total(order_id)
            reply = f"{matched['product_name']} ka quantity ab {new_qty} kar diya hai. Total: ₹{res['total']:.2f}."
            return {
                "reply": reply,
                "audit_steps": audit_steps,
                "flags": flags_raised,
                "suggested_alternatives": suggested_alts
            }

    # Case D: Add Items / General Order Request
    parsed_items = parse_quantity_and_items(message)
    if not parsed_items:
        parsed_items = [(message.strip(), 1)]

    added_names = []
    unfound_names = []
    out_of_stock_messages = []

    for prod_query, qty in parsed_items:
        audit_steps.append(AuditStep(
            step_number=2,
            title="Entity & Quantity Extraction",
            detail=f"Extracted item: '{prod_query}' | Quantity: {qty}"
        ))

        lookup = tools.lookup_product(store_id, prod_query)
        if not lookup["found"]:
            unfound_names.append(prod_query)
            audit_steps.append(AuditStep(
                step_number=3,
                title="Inventory Lookup (Item Not Found)",
                detail=f"'{prod_query}' stock mein nahi mila."
            ))
            continue

        product = lookup["product"]

        # Check Out of Stock condition
        if int(product.get("stock", 0)) <= 0:
            alts_res = tools.suggest_alternatives(
                store_id=store_id,
                category=product.get("category", "grocery"),
                exclude_product_id=product["id"],
                alternative_names=product.get("alternative_names")
            )
            item_alts = alts_res.get("alternatives", [])
            suggested_alts.extend(item_alts)

            alt_summary = ", ".join([f"{a['name']} (₹{a['price']})" for a in item_alts[:2]])
            out_of_stock_messages.append(
                f"⚠️ *{product['name']}* abhi out of stock hai. Iski jagah available options: {alt_summary or 'In-stock category items'}."
            )
            audit_steps.append(AuditStep(
                step_number=3,
                title="Zero Stock Detected - Alternatives Suggested",
                detail=f"'{product['name']}' has 0 stock. Suggested {len(item_alts)} in-stock alternatives."
            ))
            continue

        audit_steps.append(AuditStep(
            step_number=3,
            title="Database Inventory Match",
            detail=f"Matched: {product['name']} | Price: ₹{product['price']} | Stock Available: {product['stock']} {product['unit']}"
        ))

        # Step 5: Check & Flag Anomalies
        anomaly_res = tools.check_and_flag_anomaly(store_id, order_id, product, qty)
        if anomaly_res["flags_raised"]:
            flags_raised.extend(anomaly_res["flags_raised"])
            audit_steps.append(AuditStep(
                step_number=5,
                title="Rule-Based Anomaly Flagged",
                detail=f"Raised {len(anomaly_res['flags_raised'])} warning flag(s): " + ", ".join(f['reason'] for f in anomaly_res['flags_raised']),
                status="warning"
            ))
        else:
            audit_steps.append(AuditStep(
                step_number=5,
                title="Anomaly Inspection",
                detail="Quantity within normal limits and stock threshold"
            ))

        # Step 6: Add Item to Order
        tools.add_item(order_id, product["id"], product["name"], qty, float(product["price"]))
        added_names.append(f"{qty}x {product['name']}")

    # Step 4: Calculate Total
    updated_order = tools.recalc_total(order_id)
    audit_steps.append(AuditStep(
        step_number=4,
        title="Order Total Recalculation",
        detail=f"Draft order: {len(updated_order['items'])} item(s) | Total: ₹{updated_order['total']:.2f}"
    ))

    # Formulate conversational reply
    reply_parts = []
    if added_names:
        reply_parts.append(f"Maine cart mein add kar diya: {', '.join(added_names)}.\nAbhi order total: ₹{updated_order['total']:.2f}.")

    if unfound_names:
        reply_parts.append(f"Maaf kijiyega, '{', '.join(unfound_names)}' abhi hamare store mein available nahi hai.")

    if out_of_stock_messages:
        reply_parts.extend(out_of_stock_messages)

    if flags_raised:
        reply_parts.append(f"⚠️ Note: {flags_raised[0]['reason']}.")

    if not added_names and not out_of_stock_messages and not unfound_names:
        reply_parts.append("Namaste! Aap kya mangwana chahte hain? Jaise: 2 packet atta, 1 oil aur 3 maggi.")
    elif added_names:
        reply_parts.append("Order confirm karne ke liye 'confirm' likhein ya Place Order button dabayein.")

    reply = "\n\n".join(reply_parts)

    return {
        "reply": reply,
        "audit_steps": audit_steps,
        "flags": flags_raised,
        "suggested_alternatives": suggested_alts
    }


def run_gemini_agent(store_id: str, order_id: str, phone: str, message: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """
    Executes the turn via Google Gemini 1.5 Flash using native function calling.
    """
    session_key = (store_id, phone)
    if session_key not in _gemini_sessions:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_INSTRUCTION,
            tools=AGENT_TOOLS,
        )
        _gemini_sessions[session_key] = model.start_chat(enable_automatic_function_calling=True)

    session = _gemini_sessions[session_key]
    context_prefix = (
        f"[SYSTEM CONTEXT: store_id='{store_id}', order_id='{order_id}', customer_phone='{phone}']\n"
    )

    parts = [context_prefix + message]
    if image_bytes:
        parts.append({"mime_type": "image/jpeg", "data": image_bytes})

    response = session.send_message(parts)
    reply_text = response.text or ""

    order_data = tools.get_order_with_items(order_id)
    items = order_data.get("items", [])
    flags = order_data.get("flags", [])

    audit_steps = [
        AuditStep(step_number=1, title="Gemini 1.5 Flash Intent Parsing", detail="Processed multi-lingual context"),
        AuditStep(step_number=2, title="Autonomous Function Calling", detail="Invoked tools over database"),
        AuditStep(step_number=4, title="Inventory & Pricing Check", detail=f"Order has {len(items)} items, Total ₹{order_data.get('order', {}).get('total', 0)}"),
        AuditStep(step_number=5, title="Anomaly Assessment", detail=f"Flags captured: {len(flags)}"),
    ]

    return {
        "reply": reply_text,
        "audit_steps": audit_steps,
        "flags": flags,
        "suggested_alternatives": []
    }


def process_chat_turn(
    store_id: str,
    order_id: str,
    phone: str,
    message: str,
    image_base64: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point:
    1. Checks if customer is in first-time onboarding mode.
    2. Runs Gemini or deterministic NLP agent for grocery ordering.
    """
    # Check onboarding state first
    onboarding_res = check_and_handle_onboarding(store_id, phone, message)
    if onboarding_res:
        return onboarding_res

    image_bytes = None
    if image_base64:
        try:
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            image_bytes = None

    if HAS_GEMINI_KEY and genai:
        try:
            return run_gemini_agent(store_id, order_id, phone, message, image_bytes)
        except Exception as e:
            print(f"[AGENT] Gemini call failed ({e}). Falling back to deterministic NLP engine.")
            return run_deterministic_agent(store_id, order_id, phone, message)
    else:
        return run_deterministic_agent(store_id, order_id, phone, message)
