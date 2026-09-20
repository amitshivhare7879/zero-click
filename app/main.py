import os
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    ChatRequest, ChatResponse, QtyUpdate, RestockRequest, OCRRequest,
    CustomerLoginRequest, CustomerUpdateRequest
)
from . import tools
from .agent import process_chat_turn
from .config import (
    supabase, IS_LOCAL_DB, HAS_GEMINI_KEY,
    WHATSAPP_TOKEN, PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN, TELEGRAM_BOT_TOKEN
)
from .whatsapp import verify_whatsapp_webhook, handle_incoming_whatsapp_payload, send_whatsapp_message
from .telegram_bot import handle_telegram_update, send_telegram_message, start_telegram_polling_loop

app = FastAPI(
    title="Zero-Click Kirana Store Operator API",
    description="Autonomous Agentic Store Operator for Kirana merchants with WhatsApp & Telegram Bot Connectivity",
    version="2.1.0"
)

# Wide-open CORS for hackathon demo speed and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)


@app.on_event("startup")
async def on_startup():
    # Only run infinite polling loop in long-running server environments (not Vercel serverless)
    if TELEGRAM_BOT_TOKEN and not os.environ.get("VERCEL"):
        print("[STARTUP] Launching Telegram Bot background polling task...")
        asyncio.create_task(start_telegram_polling_loop())


# =====================================================================
# Core Health & System Status
# =====================================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "system": "Zero-Click Kirana Store Operator",
        "database": "Local SQLite Engine" if IS_LOCAL_DB else "Cloud Supabase PostgreSQL",
        "agent_mode": "Gemini 1.5 Flash" if HAS_GEMINI_KEY else "Resilient Kirana NLP Engine",
        "whatsapp_connected": bool(WHATSAPP_TOKEN and PHONE_NUMBER_ID),
        "telegram_connected": bool(TELEGRAM_BOT_TOKEN)
    }


@app.get("/bot/status")
def bot_status():
    return {
        "whatsapp": {
            "configured": bool(WHATSAPP_TOKEN and PHONE_NUMBER_ID),
            "phone_number_id": PHONE_NUMBER_ID or "Not configured",
            "verify_token": WHATSAPP_VERIFY_TOKEN or "Not configured",
            "webhook_path": "/webhook/whatsapp"
        },
        "telegram": {
            "configured": bool(TELEGRAM_BOT_TOKEN),
            "bot_token": (TELEGRAM_BOT_TOKEN[:7] + "...") if TELEGRAM_BOT_TOKEN else "Not configured",
            "webhook_path": "/webhook/telegram",
            "polling_active": bool(TELEGRAM_BOT_TOKEN)
        },
        "database": "Local SQLite Engine (Synced)" if IS_LOCAL_DB else "Cloud Supabase PostgreSQL",
        "agent_mode": "Gemini 1.5 Flash" if HAS_GEMINI_KEY else "Resilient Kirana NLP Engine"
    }


# =====================================================================
# Store & Product Inventory Endpoints (Zero Hardcoded Data)
# =====================================================================

@app.get("/stores")
def list_stores():
    return supabase.table("stores").select("*").execute().data


@app.get("/stores/{store_id}/products")
def list_products(store_id: str):
    return (
        supabase.table("products")
        .select("*")
        .eq("store_id", store_id)
        .order("name")
        .execute()
        .data
    )


@app.get("/stores/{store_id}/orders")
def list_orders(store_id: str):
    """Owner view: all orders for store with nested items, newest first."""
    return (
        supabase.table("orders")
        .select("*, order_items(*)")
        .eq("store_id", store_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


@app.get("/stores/{store_id}/anomalies")
def list_anomalies(store_id: str):
    """Owner view: all anomaly flags raised for this store."""
    return (
        supabase.table("anomaly_flags")
        .select("*")
        .eq("store_id", store_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


@app.get("/stores/{store_id}/metrics")
def get_metrics(store_id: str):
    return tools.get_store_metrics(store_id)


@app.post("/stores/{store_id}/products/{product_id}/restock")
def restock_product(store_id: str, product_id: str, body: RestockRequest):
    result = tools.restock_product(product_id, body.add_qty, body.new_price)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# =====================================================================
# Customer Profile & Login Authentication (Pre-seeded & New Users)
# =====================================================================

@app.get("/customers")
def get_customers(store_id: Optional[str] = None):
    """Returns list of registered customers for quick login selector in UI."""
    return tools.list_customers(store_id)


@app.post("/customers/login")
def customer_login(body: CustomerLoginRequest):
    """Logs in an existing customer or registers a new customer profile."""
    store_id = body.store_id or "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    customer = tools.get_or_create_customer(
        store_id=store_id,
        phone=body.phone,
        name=body.name,
        address=body.address
    )
    order = tools.get_or_create_draft_order(store_id, customer["id"])
    order_with_items = tools.get_order_with_items(order["id"])
    return {
        "customer": customer,
        "active_order": order_with_items
    }


@app.patch("/customers/{customer_id}")
def update_customer_profile(customer_id: str, body: CustomerUpdateRequest):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return tools.update_customer_profile(customer_id, updates)


@app.get("/customers/{customer_id}/orders")
def get_customer_orders(customer_id: str):
    """Customer view: full order history with line items and bills."""
    return tools.get_customer_order_history(customer_id)


@app.get("/customers/phone/{phone}/orders")
def get_customer_orders_by_phone(phone: str, store_id: Optional[str] = None):
    """Lookup order history by customer phone number."""
    cust = tools.get_customer_by_phone(phone, store_id)
    if not cust:
        return []
    return tools.get_customer_order_history(cust["id"])


# =====================================================================
# Order & Cart Modification Endpoints (Direct UI Speed, No LLM Latency)
# =====================================================================

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    """Cart read: frontend fetches this after every modification."""
    result = tools.get_order_with_items(order_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.patch("/orders/{order_id}/items/{item_id}")
def update_item_qty(order_id: str, item_id: str, body: QtyUpdate):
    """Cart stepper (+/-) calls this directly without LLM delay."""
    result = tools.edit_item_qty_by_id(order_id, item_id, body.qty)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.delete("/orders/{order_id}/items/{item_id}")
def delete_item(order_id: str, item_id: str):
    """Cart trash icon calls this directly without LLM delay."""
    return tools.remove_item_by_id(order_id, item_id)


@app.post("/orders/{order_id}/confirm")
def confirm_order_direct(order_id: str):
    """Direct 'Place Order' button in UI."""
    result = tools.confirm_order(order_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# =====================================================================
# Conversational Agent & Vision Endpoints (Customer Chat & OCR)
# =====================================================================

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Customer chat endpoint: orchestrates onboarding and 7-step autonomous agent."""
    store = supabase.table("stores").select("*").eq("id", req.store_id).execute()
    if not store.data:
        raise HTTPException(404, "Store not found")

    customer = tools.get_or_create_customer(req.store_id, req.customer_phone)
    order = tools.get_or_create_draft_order(req.store_id, customer["id"])

    agent_result = process_chat_turn(
        store_id=req.store_id,
        order_id=order["id"],
        phone=req.customer_phone,
        message=req.message,
        image_base64=req.image_base64
    )

    refreshed_order = supabase.table("orders").select("*").eq("id", order["id"]).execute().data[0]

    return ChatResponse(
        reply=agent_result["reply"],
        order_id=refreshed_order["id"],
        status=refreshed_order["status"],
        total=refreshed_order["total"],
        audit_steps=agent_result.get("audit_steps", []),
        flags=agent_result.get("flags", []),
        suggested_alternatives=agent_result.get("suggested_alternatives", []),
        onboarding_step=agent_result.get("onboarding_step"),
        customer=agent_result.get("customer", customer)
    )


@app.post("/ocr-order", response_model=ChatResponse)
def ocr_order(req: OCRRequest):
    """Multimodal handwritten grocery receipt / slip parser endpoint."""
    return chat(ChatRequest(
        store_id=req.store_id,
        customer_phone=req.customer_phone,
        message="Please process this handwritten grocery list image and add the items to my cart.",
        image_base64=req.image_base64
    ))


# =====================================================================
# WhatsApp Cloud API Webhook Integration
# =====================================================================

@app.get("/webhook/whatsapp")
def verify_whatsapp(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    token: Optional[str] = Query(None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """Meta Webhook Subscription Verification."""
    result = verify_whatsapp_webhook(mode, token, challenge)
    if result is not None:
        return Response(content=result, media_type="text/plain")
    raise HTTPException(403, "WhatsApp verification challenge failed")


@app.post("/webhook/whatsapp")
async def receive_whatsapp(request: Request):
    """Incoming messages from WhatsApp customers."""
    payload = await request.json()
    return handle_incoming_whatsapp_payload(payload)


# =====================================================================
# Telegram Bot Webhook & Message Integration
# =====================================================================

@app.post("/webhook/telegram")
async def receive_telegram(request: Request):
    """Incoming updates from Telegram Bot."""
    payload = await request.json()
    return handle_telegram_update(payload)


@app.post("/bot/test-message")
def test_bot_dispatch(
    channel: str = Query("whatsapp", description="'whatsapp' or 'telegram'"),
    to: str = Query(..., description="Phone number for WhatsApp or Chat ID for Telegram"),
    message: str = Query(..., description="Message text to send")
):
    """Interactive testing endpoint for WhatsApp and Telegram bot delivery."""
    if channel == "whatsapp":
        return send_whatsapp_message(to, message)
    elif channel == "telegram":
        return send_telegram_message(to, message)
    raise HTTPException(400, "Channel must be 'whatsapp' or 'telegram'")


# =====================================================================
# Web Dashboard & Customer Ordering UI (Served directly on single port)
# =====================================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Zero-Click Store Operator Dashboard is compiling...</h1>")
