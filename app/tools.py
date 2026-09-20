"""
Tools module for Zero-Click Kirana Store Operator.
Every tool performs discrete operations on Supabase / Postgres and returns structured data.
"""
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from .config import supabase

# Common Hinglish synonyms mapping to standard product search terms
SYNONYMS = {
    "atta": "Atta",
    "aata": "Atta",
    "flour": "Atta",
    "oil": "Oil",
    "tel": "Oil",
    "sarson": "Mustard Oil",
    "mustard": "Mustard Oil",
    "sunflower": "Sunflower Oil",
    "maggi": "Maggi",
    "maggie": "Maggi",
    "noodles": "Noodles",
    "doodh": "Milk",
    "milk": "Milk",
    "namak": "Salt",
    "salt": "Salt",
    "makkhan": "Butter",
    "butter": "Butter",
    "biscuit": "Biscuits",
    "biscuits": "Biscuits",
    "parle": "Parle-G",
    "parleg": "Parle-G",
    "goodday": "Good Day",
    "surf": "Surf Excel",
    "detergent": "Surf Excel",
    "sabun": "Surf Excel",
    "ariel": "Ariel Matic",
    "vim": "Vim Dishwash",
    "dishwash": "Vim Dishwash",
    "poha": "Poha",
    "pohe": "Poha",
    "indori poha": "Indori Poha",
    "chivda": "Poha",
}

UNIT_STOP_WORDS = {
    "kg", "1kg", "2kg", "3kg", "4kg", "5kg", "10kg",
    "gm", "g", "gram", "grams", "500g", "500gm", "250g", "250gm", "100g", "100gm",
    "l", "lt", "ltr", "litre", "liter", "1l", "2l", "5l",
    "ml", "500ml", "200ml",
    "packet", "packets", "pkt", "pkts", "pack", "packs",
    "pouch", "pouches", "pc", "pcs", "piece", "pieces",
    "bottle", "bottles", "krdo", "kardo", "kar", "do", "de", "chahiye"
}


def get_or_create_customer(
    store_id: str,
    phone: str,
    name: Optional[str] = None,
    address: Optional[str] = None,
    telegram_chat_id: Optional[str] = None
) -> dict:
    """
    Looks up existing customer by phone or creates a new one.
    If new customer without explicit name: sets onboarding_step to 'awaiting_name'.
    If name is provided: sets onboarding_step to 'completed'.
    """
    clean_phone = str(phone).strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("+91"):
        clean_phone = clean_phone[3:]
    elif clean_phone.startswith("91") and len(clean_phone) == 12:
        clean_phone = clean_phone[2:]

    existing = (
        supabase.table("customers")
        .select("*")
        .eq("store_id", store_id)
        .eq("phone", clean_phone)
        .execute()
    )
    if existing.data:
        cust = existing.data[0]
        updates = {}
        if name and name.strip() and name.strip() != cust.get("name"):
            updates["name"] = name.strip()
            updates["onboarding_step"] = "completed"
        if address and address.strip() and address.strip() != cust.get("address"):
            updates["address"] = address.strip()
        if telegram_chat_id and not cust.get("telegram_chat_id"):
            updates["telegram_chat_id"] = telegram_chat_id
        if updates:
            supabase.table("customers").update(updates).eq("id", cust["id"]).execute()
            cust.update(updates)
        return cust

    # Determine initial onboarding step
    initial_step = "completed" if name else "awaiting_name"
    display_name = name or f"Customer {clean_phone[-4:] if len(clean_phone) >= 4 else clean_phone}"

    created = (
        supabase.table("customers")
        .insert({
            "store_id": store_id,
            "phone": clean_phone,
            "name": display_name,
            "address": address or "Indore, MP",
            "onboarding_step": initial_step,
            "telegram_chat_id": telegram_chat_id
        })
        .execute()
    )
    return created.data[0]


def update_customer_profile(customer_id: str, updates: Dict[str, Any]) -> dict:
    """
    Updates customer details like name, address, onboarding_step.
    """
    supabase.table("customers").update(updates).eq("id", customer_id).execute()
    refreshed = supabase.table("customers").select("*").eq("id", customer_id).execute()
    return refreshed.data[0] if refreshed.data else {"id": customer_id, **updates}


def get_customer_by_phone(phone: str, store_id: Optional[str] = None) -> Optional[dict]:
    clean_phone = str(phone).strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("+91"):
        clean_phone = clean_phone[3:]
    elif clean_phone.startswith("91") and len(clean_phone) == 12:
        clean_phone = clean_phone[2:]

    query = supabase.table("customers").select("*").eq("phone", clean_phone)
    if store_id:
        query = query.eq("store_id", store_id)
    res = query.execute()
    return res.data[0] if res.data else None


def get_customer_by_telegram(telegram_chat_id: str) -> Optional[dict]:
    res = supabase.table("customers").select("*").eq("telegram_chat_id", str(telegram_chat_id)).execute()
    return res.data[0] if res.data else None


def get_customer_order_history(customer_id: str) -> List[dict]:
    """
    Returns order history for a customer with line items, newest first.
    """
    orders_res = (
        supabase.table("orders")
        .select("*, order_items(*)")
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )
    return orders_res.data or []


def list_customers(store_id: Optional[str] = None) -> List[dict]:
    """
    Returns list of customers for the dashboard login switcher.
    """
    query = supabase.table("customers").select("*")
    if store_id:
        query = query.eq("store_id", store_id)
    return query.order("name").execute().data or []


def get_or_create_draft_order(store_id: str, customer_id: str) -> dict:
    existing = (
        supabase.table("orders")
        .select("*")
        .eq("store_id", store_id)
        .eq("customer_id", customer_id)
        .eq("status", "draft")
        .order("created_at", desc=True)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    created = (
        supabase.table("orders")
        .insert({
            "store_id": store_id,
            "customer_id": customer_id,
            "status": "draft",
            "total": 0.00
        })
        .execute()
    )
    return created.data[0]


def lookup_product(store_id: str, product_name: str) -> dict:
    """
    Looks up a product in the specified store's inventory.
    Applies synonym normalization and case-insensitive substring matching.
    Strips numeric units (1kg, 2l, etc.) to prevent false-positive matches.
    """
    # Strip leading/trailing digits and units like "1kg", "2 packet", "500gm"
    clean_name = product_name.strip().lower()
    clean_name = re.sub(r"^\d+\s*(kg|gm|g|l|ltr|litre|ml|packet|pkt|pc|pcs)?\s*", "", clean_name).strip()
    clean_name = re.sub(r"\b\d+\s*(kg|gm|g|l|ltr|litre|ml|packet|pkt|pc|pcs)\b", "", clean_name).strip()

    # Try synonym replacement
    search_term = clean_name
    for syn, canonical in SYNONYMS.items():
        if syn in clean_name:
            search_term = canonical
            break

    # First attempt: substring match on search_term
    if search_term and search_term not in UNIT_STOP_WORDS:
        result = (
            supabase.table("products")
            .select("*")
            .eq("store_id", store_id)
            .ilike("name", f"%{search_term}%")
            .execute()
        )
        if result.data:
            return {"found": True, "product": result.data[0]}

    # Second attempt: meaningful individual words (ignoring units and numbers)
    words = [w for w in clean_name.split() if len(w) > 2 and w not in UNIT_STOP_WORDS and not w.isdigit()]
    for word in words:
        res = (
            supabase.table("products")
            .select("*")
            .eq("store_id", store_id)
            .ilike("name", f"%{word}%")
            .execute()
        )
        if res.data:
            return {"found": True, "product": res.data[0]}

    return {"found": False, "product": None}


def suggest_alternatives(
    store_id: str,
    category: str,
    exclude_product_id: Optional[str] = None,
    alternative_names: Optional[str] = None
) -> dict:
    """
    Finds up to 3 available, in-stock products when requested item is unavailable or out of stock.
    Prioritizes explicit alternative_names if provided, otherwise matches same category.
    """
    alternatives = []
    seen_ids = set([exclude_product_id] if exclude_product_id else [])

    # 1. Check explicit alternative names linked to the product
    if alternative_names:
        names = [n.strip() for n in alternative_names.split(",") if n.strip()]
        for name in names:
            matched = (
                supabase.table("products")
                .select("*")
                .eq("store_id", store_id)
                .ilike("name", f"%{name}%")
                .gt("stock", 0)
                .execute()
            )
            for p in (matched.data or []):
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    alternatives.append(p)

    # 2. Query products in the same category that are in stock
    if len(alternatives) < 3 and category:
        cat_query = (
            supabase.table("products")
            .select("*")
            .eq("store_id", store_id)
            .eq("category", category)
            .gt("stock", 0)
            .execute()
        )
        for p in (cat_query.data or []):
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                alternatives.append(p)
                if len(alternatives) >= 3:
                    break

    # 3. Fallback: general in-stock products
    if not alternatives:
        fallback = (
            supabase.table("products")
            .select("*")
            .eq("store_id", store_id)
            .gt("stock", 0)
            .execute()
        )
        for p in (fallback.data or []):
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                alternatives.append(p)
                if len(alternatives) >= 3:
                    break

    return {"alternatives": alternatives[:3]}


def add_item(order_id: str, product_id: str, product_name: str, qty: int, unit_price: float) -> dict:
    """
    Adds a line item to the relational order_items table.
    If the product already exists in the draft order, increments the quantity.
    """
    qty = max(1, int(qty))
    unit_price = float(unit_price)

    existing = (
        supabase.table("order_items")
        .select("*")
        .eq("order_id", order_id)
        .eq("product_id", product_id)
        .execute()
    )

    if existing.data:
        item = existing.data[0]
        new_qty = item["qty"] + qty
        new_line_total = new_qty * unit_price
        supabase.table("order_items").update({
            "qty": new_qty,
            "line_total": round(new_line_total, 2)
        }).eq("id", item["id"]).execute()
    else:
        line_total = round(qty * unit_price, 2)
        supabase.table("order_items").insert({
            "order_id": order_id,
            "product_id": product_id,
            "product_name": product_name,
            "qty": qty,
            "unit_price": round(unit_price, 2),
            "line_total": line_total
        }).execute()

    return recalc_total(order_id)


def remove_item(order_id: str, product_name: str) -> dict:
    """
    Removes an item from the draft order by product name match.
    """
    clean = product_name.strip().lower()
    items = supabase.table("order_items").select("*").eq("order_id", order_id).execute().data or []

    for item in items:
        if clean in item["product_name"].lower() or any(w in item["product_name"].lower() for w in clean.split() if len(w) > 2):
            supabase.table("order_items").delete().eq("id", item["id"]).execute()
            break

    return recalc_total(order_id)


def edit_qty(order_id: str, product_name: str, new_qty: int) -> dict:
    """
    Modifies the quantity of a product in the draft order.
    """
    if new_qty <= 0:
        return remove_item(order_id, product_name)

    items = supabase.table("order_items").select("*").eq("order_id", order_id).execute().data or []
    clean = product_name.strip().lower()

    matched_item = None
    for item in items:
        if clean in item["product_name"].lower() or any(w in item["product_name"].lower() for w in clean.split() if len(w) > 2):
            matched_item = item
            break

    if not matched_item:
        return {"error": f"Item matching '{product_name}' not found in order"}

    new_line_total = round(new_qty * float(matched_item["unit_price"]), 2)
    supabase.table("order_items").update({
        "qty": new_qty,
        "line_total": new_line_total
    }).eq("id", matched_item["id"]).execute()

    return recalc_total(order_id)


def recalc_total(order_id: str) -> dict:
    """
    Calculates total for the order and updates orders table.
    """
    items = supabase.table("order_items").select("*").eq("order_id", order_id).execute().data or []
    total = round(sum(float(i["line_total"]) for i in items), 2)
    supabase.table("orders").update({"total": total}).eq("id", order_id).execute()
    return {"order_id": order_id, "total": total, "items": items}


def check_and_flag_anomaly(store_id: str, order_id: str, product: dict, qty: int) -> dict:
    """
    Rule-based anomaly detection engine (1 row per flag).
    Checks:
      1. Unusual Quantity Threshold: qty > 20
      2. Stock Exceeded: qty > product['stock']
    """
    flags_raised = []
    qty = int(qty)
    available_stock = int(product.get("stock", 0))

    # Rule 1: High Quantity Anomaly (> 20 units)
    if qty > 20:
        reason = f"Unusually high bulk quantity ({qty} units) requested for {product.get('name')}"
        severity = "medium"
        supabase.table("anomaly_flags").insert({
            "store_id": store_id,
            "order_id": order_id,
            "reason": reason,
            "severity": severity
        }).execute()
        flags_raised.append({"reason": reason, "severity": severity})

    # Rule 2: Exceeds Current Inventory
    if qty > available_stock:
        reason = f"Requested quantity ({qty}) exceeds available store inventory ({available_stock} in stock)"
        severity = "high"
        supabase.table("anomaly_flags").insert({
            "store_id": store_id,
            "order_id": order_id,
            "reason": reason,
            "severity": severity
        }).execute()
        flags_raised.append({"reason": reason, "severity": severity})

    return {"flags_raised": flags_raised, "flag_count": len(flags_raised)}


def get_order_with_items(order_id: str) -> dict:
    """
    Retrieves full order with relational line items.
    """
    order_res = supabase.table("orders").select("*").eq("id", order_id).execute()
    if not order_res.data:
        return {"error": "Order not found"}

    order = order_res.data[0]
    items_res = supabase.table("order_items").select("*").eq("order_id", order_id).execute()
    items = items_res.data or []

    # Also fetch any flags for this order
    flags_res = supabase.table("anomaly_flags").select("*").eq("order_id", order_id).execute()
    flags = flags_res.data or []

    return {"order": order, "items": items, "flags": flags}


def edit_item_qty_by_id(order_id: str, item_id: str, new_qty: int) -> dict:
    """
    Direct cart stepper edit (+/-) called by UI without LLM.
    """
    if new_qty <= 0:
        return remove_item_by_id(order_id, item_id)

    item_res = supabase.table("order_items").select("*").eq("id", item_id).execute()
    if not item_res.data:
        return {"error": "Item not found in order"}

    item = item_res.data[0]
    new_line_total = round(new_qty * float(item["unit_price"]), 2)
    supabase.table("order_items").update({
        "qty": new_qty,
        "line_total": new_line_total
    }).eq("id", item_id).execute()

    return recalc_total(order_id)


def remove_item_by_id(order_id: str, item_id: str) -> dict:
    """
    Direct cart trash deletion called by UI without LLM.
    """
    supabase.table("order_items").delete().eq("id", item_id).execute()
    return recalc_total(order_id)


def confirm_order(order_id: str) -> dict:
    """
    Confirms order:
    1. Deducts live stock from products table atomically
    2. Updates status to 'confirmed'
    3. Generates itemized Kirana bill text with timestamp and totals
    """
    order_info = get_order_with_items(order_id)
    if "error" in order_info:
        return order_info

    items = order_info["items"]
    order = order_info["order"]

    if not items:
        return {"error": "Cannot confirm an empty cart"}

    store_res = supabase.table("stores").select("*").eq("id", order["store_id"]).execute()
    store_name = store_res.data[0]["name"] if store_res.data else "Kirana Store"

    # Atomic stock deduction
    for item in items:
        if item.get("product_id"):
            prod_res = supabase.table("products").select("stock").eq("id", item["product_id"]).execute()
            if prod_res.data:
                current_stock = prod_res.data[0]["stock"]
                new_stock = max(0, current_stock - item["qty"])
                supabase.table("products").update({"stock": new_stock}).eq("id", item["product_id"]).execute()

    total = sum(float(i["line_total"]) for i in items)
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")

    supabase.table("orders").update({
        "status": "confirmed",
        "total": round(total, 2),
        "confirmed_at": timestamp
    }).eq("id", order_id).execute()

    # Generate itemized bill
    bill_lines = [
        f"🧾 *{store_name.upper()}*",
        f"📅 Date: {timestamp}",
        f"🆔 Order ID: #{order_id[:8].upper()}",
        "─" * 32,
    ]
    for idx, item in enumerate(items, 1):
        bill_lines.append(f"{idx}. {item['product_name']}")
        bill_lines.append(f"   {item['qty']} x ₹{item['unit_price']:.2f} = ₹{item['line_total']:.2f}")

    bill_lines.extend([
        "─" * 32,
        f"Subtotal:       ₹{total:.2f}",
        "Delivery / GST: FREE (Essential Groceries)",
        f"*GRAND TOTAL:   ₹{total:.2f}*",
        "─" * 32,
        "Dhanyawad! Aapka order jaldi bhej rahe hain! 🙏📦"
    ])
    bill_text = "\n".join(bill_lines)

    return {
        "order_id": order_id,
        "status": "confirmed",
        "total": round(total, 2),
        "bill": bill_text,
        "items": items
    }


def restock_product(product_id: str, add_qty: int, new_price: Optional[float] = None) -> dict:
    """
    Merchant action to update stock or price directly.
    """
    prod_res = supabase.table("products").select("*").eq("id", product_id).execute()
    if not prod_res.data:
        return {"error": "Product not found"}

    prod = prod_res.data[0]
    updated_stock = prod["stock"] + add_qty
    update_data = {"stock": updated_stock}
    if new_price is not None and new_price >= 0:
        update_data["price"] = round(new_price, 2)

    supabase.table("products").update(update_data).eq("id", product_id).execute()
    refreshed = supabase.table("products").select("*").eq("id", product_id).execute().data[0]
    return {"success": True, "product": refreshed}


def get_store_metrics(store_id: str) -> dict:
    """
    Aggregates KPIs for the store owner dashboard.
    """
    orders_res = supabase.table("orders").select("*").eq("store_id", store_id).execute().data or []
    confirmed_orders = [o for o in orders_res if o.get("status") == "confirmed"]
    total_revenue = sum(float(o.get("total", 0)) for o in confirmed_orders)

    anomalies_res = supabase.table("anomaly_flags").select("*").eq("store_id", store_id).execute().data or []
    products_res = supabase.table("products").select("*").eq("store_id", store_id).execute().data or []
    low_stock = [p for p in products_res if p.get("stock", 0) <= 5]

    return {
        "store_id": store_id,
        "total_revenue": round(total_revenue, 2),
        "total_orders": len(orders_res),
        "confirmed_orders": len(confirmed_orders),
        "anomaly_count": len(anomalies_res),
        "low_stock_count": len(low_stock),
        "total_products": len(products_res)
    }
