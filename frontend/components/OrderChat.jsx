"use client";

import { useState, useEffect, useRef } from "react";
import { Send, Minus, Plus, Trash2, ShoppingBag, CheckCircle2, AlertTriangle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/**
 * Drop into any Next.js page:
 *   <OrderChat storeId="<store-uuid>" customerPhone="9876543210" customerName="Ramesh Patel" />
 *
 * Left pane: natural-language chat with the agent (onboarding, product search, alternatives, voice/text).
 * Right pane: live cart — qty steppers and delete work instantly via direct
 * REST calls, no LLM round-trip needed for simple edits. Both panes stay in
 * sync because every action refetches /orders/{order_id}.
 */
export default function OrderChat({ storeId, customerPhone = "9876543210", customerName = "Ramesh Patel" }) {
  const [messages, setMessages] = useState([
    { role: "agent", text: `Namaste ${customerName}! 🙏 Sharma Kirana mein aapka swagat hai. Kya order karna hai aaj?` },
  ]);
  const [input, setInput] = useState("");
  const [orderId, setOrderId] = useState(null);
  const [cart, setCart] = useState({ order: null, items: [], flags: [] });
  const [sending, setSending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function refreshCart(id) {
    if (!id) return;
    try {
      const res = await fetch(`${API_BASE}/orders/${id}`);
      if (res.ok) setCart(await res.json());
    } catch (e) {
      console.error("Cart refresh failed:", e);
    }
  }

  async function sendMessage(customText) {
    const text = (customText || input).trim();
    if (!text || sending) return;

    setMessages((m) => [...m, { role: "customer", text }]);
    if (!customText) setInput("");
    setSending(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          store_id: storeId,
          customer_phone: customerPhone,
          message: text,
        }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "agent",
          text: data.reply,
          alternatives: data.suggested_alternatives || []
        }
      ]);
      setOrderId(data.order_id);
      if (data.status === "confirmed") setConfirmed(true);
      await refreshCart(data.order_id);
    } catch (err) {
      setMessages((m) => [...m, { role: "agent", text: "Connection issue — please verify store server is running." }]);
    } finally {
      setSending(false);
    }
  }

  async function changeQty(itemId, newQty) {
    if (!orderId) return;
    if (newQty <= 0) return deleteItem(itemId);
    await fetch(`${API_BASE}/orders/${orderId}/items/${itemId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qty: newQty }),
    });
    refreshCart(orderId);
  }

  async function deleteItem(itemId) {
    if (!orderId) return;
    await fetch(`${API_BASE}/orders/${orderId}/items/${itemId}`, { method: "DELETE" });
    refreshCart(orderId);
  }

  async function placeOrder() {
    if (!orderId || !cart.items?.length) return;
    const res = await fetch(`${API_BASE}/orders/${orderId}/confirm`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      setConfirmed(true);
      setMessages((m) => [...m, { role: "agent", text: data.bill }]);
      refreshCart(orderId);
    }
  }

  const total = cart.items?.reduce((sum, i) => sum + i.line_total, 0) || 0;

  return (
    <div className="flex flex-col md:flex-row h-[650px] w-full max-w-4xl mx-auto rounded-3xl border border-neutral-200 overflow-hidden shadow-xl bg-white">
      {/* Chat pane */}
      <div className="flex flex-col md:w-3/5 border-r border-neutral-200 bg-white">
        <div className="p-4 border-b border-neutral-100 flex items-center justify-between bg-neutral-50/50">
          <div>
            <h3 className="font-bold text-sm text-neutral-900">Zero-Click Kirana Assistant</h3>
            <p className="text-xs text-neutral-500">Customer: {customerName} ({customerPhone})</p>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
            Autonomous Agent
          </span>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "customer" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                  m.role === "customer"
                    ? "bg-neutral-900 text-white rounded-br-sm"
                    : "bg-neutral-100 text-neutral-900 rounded-bl-sm"
                }`}
              >
                <p>{m.text}</p>
                {m.alternatives && m.alternatives.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-neutral-200 text-xs">
                    <p className="font-semibold text-amber-800 mb-1">In-Stock Alternatives:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {m.alternatives.map((alt) => (
                        <button
                          key={alt.id}
                          onClick={() => sendMessage(`1 ${alt.name} add kar do`)}
                          className="bg-white border border-amber-300 text-neutral-800 hover:border-neutral-900 px-2.5 py-1 rounded-lg text-xs transition shadow-xs"
                        >
                          + {alt.name} (₹{alt.price})
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 p-3 border-t border-neutral-200 bg-white">
          <input
            className="flex-1 rounded-full border border-neutral-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
            placeholder="2 packet atta, 1 fortune oil aur 3 maggi bhej do..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            disabled={confirmed}
          />
          <button
            onClick={() => sendMessage()}
            disabled={sending || confirmed}
            className="rounded-full bg-neutral-900 p-2.5 text-white disabled:opacity-40 transition hover:bg-neutral-800"
          >
            <Send size={16} />
          </button>
        </div>
      </div>

      {/* Cart pane */}
      <div className="flex flex-col md:w-2/5 bg-neutral-50">
        <div className="flex items-center justify-between p-4 border-b border-neutral-200 bg-white">
          <div className="flex items-center gap-2">
            <ShoppingBag size={18} className="text-emerald-700" />
            <span className="font-bold text-sm text-neutral-900">Your Basket</span>
          </div>
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-600">
            {cart.items?.length || 0} items
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {!cart.items?.length && (
            <div className="text-center py-12 text-neutral-400 text-sm">
              <p className="text-2xl mb-1">🛒</p>
              <p>Cart is empty — start chatting.</p>
            </div>
          )}

          {cart.flags && cart.flags.length > 0 && (
            <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2">
              <AlertTriangle size={16} className="shrink-0 text-amber-600" />
              <span>{cart.flags[0].reason}</span>
            </div>
          )}

          {cart.items?.map((item) => (
            <div key={item.id} className="flex items-center justify-between bg-white rounded-xl p-3 border border-neutral-200 shadow-xs">
              <div className="min-w-0 flex-1 pr-2">
                <p className="text-sm font-semibold truncate text-neutral-900">{item.product_name}</p>
                <p className="text-xs text-neutral-500">₹{item.unit_price} each • ₹{item.line_total}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={() => changeQty(item.id, item.qty - 1)}
                  className="rounded-lg border border-neutral-300 w-6 h-6 flex items-center justify-center text-neutral-700 disabled:opacity-40 hover:bg-neutral-100"
                  disabled={confirmed}
                >
                  <Minus size={12} />
                </button>
                <span className="text-sm font-bold w-5 text-center text-neutral-900">{item.qty}</span>
                <button
                  onClick={() => changeQty(item.id, item.qty + 1)}
                  className="rounded-lg border border-neutral-300 w-6 h-6 flex items-center justify-center text-neutral-700 disabled:opacity-40 hover:bg-neutral-100"
                  disabled={confirmed}
                >
                  <Plus size={12} />
                </button>
                <button
                  onClick={() => deleteItem(item.id)}
                  className="text-red-500 p-1 disabled:opacity-40 hover:bg-red-50 rounded-lg ml-1"
                  disabled={confirmed}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="p-4 border-t border-neutral-200 bg-white space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Subtotal</span>
            <span className="font-semibold text-neutral-900">₹{total.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-xs text-emerald-700 font-medium">
            <span>Essential Grocery Delivery</span>
            <span>FREE</span>
          </div>
          <div className="flex justify-between text-base font-extrabold text-neutral-900 pt-1 border-t border-neutral-100">
            <span>Total</span>
            <span>₹{total.toFixed(2)}</span>
          </div>

          <button
            onClick={placeOrder}
            disabled={!cart.items?.length || confirmed}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white py-3 text-sm font-bold transition disabled:opacity-40 shadow-md shadow-emerald-600/20"
          >
            {confirmed ? (
              <>
                <CheckCircle2 size={16} /> Order Confirmed & Deducted
              </>
            ) : (
              "Place Order Now"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
