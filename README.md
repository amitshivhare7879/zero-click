# Zero-Click Store Operator — scaffold

## Setup (5 min)
1. `pip install -r requirements.txt`
2. Create a Supabase project → run `schema.sql` in the SQL editor.
3. After the seed insert runs, grab the two store UUIDs and manually insert
   ~10 products per store (see commented example at bottom of `schema.sql`).
4. Copy `.env.example` → `.env`, fill in `SUPABASE_URL`, `SUPABASE_KEY`
   (service role key, not anon, so inserts/updates aren't blocked by RLS),
   and `GEMINI_API_KEY`.
5. `uvicorn app.main:app --reload`

## Demo flow
```
POST /chat
{
  "store_id": "<sharma-store-id>",
  "customer_phone": "9999999999",
  "message": "Bhaiya 2 packets Ashirvaad atta, 1 Fortune oil aur 3 Maggi bhej do"
}
```
Agent should: look up each product, add to draft order, flag anomalies if any,
and wait for confirmation.

```
POST /chat  (same store_id + phone → same session/draft order)
{ "message": "atta ek aur kar do" }        -- edits qty
{ "message": "maggi hata do" }             -- removes item
{ "message": "haan confirm karo" }         -- triggers confirm_order → returns bill
```

`GET /stores/{store_id}/orders` and `/anomalies` are the owner-facing views —
point a simple Next.js table at these for the "multiple stores" dashboard.

## Frontend — chat + live cart

`frontend/components/OrderChat.jsx` is a drop-in Next.js component:

```jsx
import OrderChat from "@/components/OrderChat";
<OrderChat storeId="<store-uuid>" customerPhone="9999999999" />
```

Needs `lucide-react` (`npm install lucide-react`) and Tailwind already configured
(standard in a `create-next-app --tailwind` project). Set `NEXT_PUBLIC_API_BASE`
in `.env.local` if the API isn't on `localhost:8000`.

Behavior: chat messages go through the agent (`/chat`) for natural-language
add/edit. The cart panel's qty steppers and trash icon call the new direct
endpoints (`PATCH`/`DELETE` `/orders/{id}/items/{item_id}`) — no LLM round-trip
for a simple +/- or delete, which is both faster and closer to how a real
ordering app behaves. Both panes stay in sync because every action refetches
`GET /orders/{order_id}`. "Place Order" hits `/orders/{id}/confirm` directly.

## What's stubbed vs. what to build next
- ✅ Core 7-step loop, draft-order chat editing, bill generation, rule-based
  anomaly flags, multi-store schema — all wired end-to-end.
- 🔲 OCR/vision path: `main.py` has a comment marking exactly where to add
  the multimodal content block when `image_base64` is present. Don't build
  a separate OCR model — pass the image straight to Gemini.
- 🔲 Frontend: this only exposes the API. Build the chat UI + owner
  dashboard in Next.js against `/chat`, `/stores/{id}/orders`,
  `/stores/{id}/anomalies`.
- 🔲 RLS policies: wide open right now via service key for demo speed —
  fine for a hackathon, say so if judges ask.
