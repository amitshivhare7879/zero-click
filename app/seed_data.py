"""
Standalone Database Seeder for Zero-Click Store Operator.
Seeds 2 Stores, 3 Customers, In-Stock Products, and Out-of-Stock Items with Alternatives
into either Cloud Supabase or the Local Resilient Engine.
"""
import sys
from app.config import supabase, IS_LOCAL_DB

STORES = [
    {
        "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Sharma Kirana — Depot Indore",
        "owner_name": "Ramesh Sharma",
        "address": "Shop 14, Main Market, Depot Area, Indore"
    },
    {
        "id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
        "name": "Sharma Superstore — Vijay Nagar",
        "owner_name": "Ramesh Sharma",
        "address": "Plot 42, Scheme 54, Vijay Nagar, Indore"
    }
]

CUSTOMERS = [
    {
        "id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a01",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "phone": "9876543210",
        "name": "Ramesh Patel",
        "address": "Flat 402, Shivalik Heights, Depot Area, Indore",
        "onboarding_step": "completed"
    },
    {
        "id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a02",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "phone": "9811122233",
        "name": "Priya Sharma",
        "address": "B-12, Silver Springs, Depot Area, Indore",
        "onboarding_step": "completed"
    },
    {
        "id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a03",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "phone": "9988776655",
        "name": "Amit Kumar",
        "address": "14 Old Palasia, Indore",
        "onboarding_step": "completed"
    }
]

STORE_1_PRODUCTS = [
    {
        "id": "11111111-1111-1111-1111-111111111101",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Aashirvaad Atta 5kg",
        "category": "grocery",
        "price": 270.00,
        "stock": 15,
        "unit": "packet",
        "alternative_names": "Pillsbury Chakki Atta 5kg"
    },
    {
        "id": "11111111-1111-1111-1111-111111111102",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Pillsbury Chakki Atta 5kg",
        "category": "grocery",
        "price": 265.00,
        "stock": 12,
        "unit": "packet",
        "alternative_names": "Aashirvaad Atta 5kg"
    },
    {
        "id": "11111111-1111-1111-1111-111111111103",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Fortune Sunlite Sunflower Oil 1L",
        "category": "grocery",
        "price": 140.00,
        "stock": 20,
        "unit": "pouch",
        "alternative_names": "Saffola Gold Oil 1L"
    },
    {
        "id": "11111111-1111-1111-1111-111111111104",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Saffola Gold Oil 1L",
        "category": "grocery",
        "price": 185.00,
        "stock": 10,
        "unit": "pouch",
        "alternative_names": "Fortune Sunlite Sunflower Oil 1L"
    },
    {
        "id": "11111111-1111-1111-1111-111111111105",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Fortune Mustard Oil 1L",
        "category": "grocery",
        "price": 155.00,
        "stock": 0,  # OUT OF STOCK
        "unit": "bottle",
        "alternative_names": "Dhara Kachi Ghani Mustard Oil 1L"
    },
    {
        "id": "11111111-1111-1111-1111-111111111106",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Dhara Kachi Ghani Mustard Oil 1L",
        "category": "grocery",
        "price": 150.00,
        "stock": 14,
        "unit": "bottle",
        "alternative_names": "Fortune Mustard Oil 1L"
    },
    {
        "id": "11111111-1111-1111-1111-111111111107",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Tata Salt 1kg",
        "category": "grocery",
        "price": 28.00,
        "stock": 35,
        "unit": "packet",
        "alternative_names": "Aashirvaad Iodized Salt 1kg"
    },
    {
        "id": "11111111-1111-1111-1111-111111111108",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Aashirvaad Iodized Salt 1kg",
        "category": "grocery",
        "price": 26.00,
        "stock": 25,
        "unit": "packet",
        "alternative_names": "Tata Salt 1kg"
    },
    {
        "id": "11111111-1111-1111-1111-111111111109",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Maggi Noodles 70g",
        "category": "snacks",
        "price": 14.00,
        "stock": 50,
        "unit": "pc",
        "alternative_names": "Yippee Noodles 65g"
    },
    {
        "id": "11111111-1111-1111-1111-111111111110",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Yippee Noodles 65g",
        "category": "snacks",
        "price": 12.00,
        "stock": 30,
        "unit": "pc",
        "alternative_names": "Maggi Noodles 70g"
    },
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Parle-G Biscuits 250g",
        "category": "snacks",
        "price": 25.00,
        "stock": 45,
        "unit": "packet",
        "alternative_names": "Britannia Good Day Biscuits 200g"
    },
    {
        "id": "11111111-1111-1111-1111-111111111112",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Britannia Good Day Biscuits 200g",
        "category": "snacks",
        "price": 35.00,
        "stock": 28,
        "unit": "packet",
        "alternative_names": "Parle-G Biscuits 250g"
    },
    {
        "id": "11111111-1111-1111-1111-111111111113",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Amul Taaza Milk 500ml",
        "category": "dairy",
        "price": 30.00,
        "stock": 0,  # OUT OF STOCK
        "unit": "pouch",
        "alternative_names": "Mother Dairy Toned Milk 500ml, Amul Gold Milk 500ml"
    },
    {
        "id": "11111111-1111-1111-1111-111111111114",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Mother Dairy Toned Milk 500ml",
        "category": "dairy",
        "price": 28.00,
        "stock": 25,
        "unit": "pouch",
        "alternative_names": "Amul Taaza Milk 500ml"
    },
    {
        "id": "11111111-1111-1111-1111-111111111115",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Amul Gold Milk 500ml",
        "category": "dairy",
        "price": 34.00,
        "stock": 18,
        "unit": "pouch",
        "alternative_names": "Amul Taaza Milk 500ml"
    },
    {
        "id": "11111111-1111-1111-1111-111111111116",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Amul Butter 100g",
        "category": "dairy",
        "price": 56.00,
        "stock": 18,
        "unit": "pc",
        "alternative_names": "Mother Dairy Butter 100g"
    },
    {
        "id": "11111111-1111-1111-1111-111111111117",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Surf Excel Easy Wash 1kg",
        "category": "household",
        "price": 145.00,
        "stock": 20,
        "unit": "packet",
        "alternative_names": "Ariel Matic Powder 1kg"
    },
    {
        "id": "11111111-1111-1111-1111-111111111118",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Ariel Matic Powder 1kg",
        "category": "household",
        "price": 210.00,
        "stock": 15,
        "unit": "packet",
        "alternative_names": "Surf Excel Easy Wash 1kg"
    },
    {
        "id": "11111111-1111-1111-1111-111111111119",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Vim Dishwash Gel 500ml",
        "category": "household",
        "price": 105.00,
        "stock": 16,
        "unit": "bottle",
        "alternative_names": "Pril Dishwash 500ml"
    },
    {
        "id": "11111111-1111-1111-1111-111111111120",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Indori Poha 1kg",
        "category": "grocery",
        "price": 55.00,
        "stock": 30,
        "unit": "packet",
        "alternative_names": "Indori Poha 500g"
    },
    {
        "id": "11111111-1111-1111-1111-111111111121",
        "store_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "name": "Indori Poha 500g",
        "category": "grocery",
        "price": 30.00,
        "stock": 25,
        "unit": "packet",
        "alternative_names": "Indori Poha 1kg"
    }
]


def seed_database():
    target = "Local Resilient PostgreSQL" if IS_LOCAL_DB else "Cloud Supabase"
    print(f"[SEED] Seeding database on target: {target}...")

    # 1. Stores
    for store in STORES:
        supabase.table("stores").insert(store).execute()
    print(f"[SEED] Seeded {len(STORES)} stores")

    # 2. Customers
    for cust in CUSTOMERS:
        supabase.table("customers").insert(cust).execute()
    print(f"[SEED] Seeded {len(CUSTOMERS)} pre-registered users (Ramesh Patel, Priya Sharma, Amit Kumar)")

    # 3. Products
    for prod in STORE_1_PRODUCTS:
        supabase.table("products").insert(prod).execute()
    print(f"[SEED] Seeded {len(STORE_1_PRODUCTS)} products with stock & alternative relationships")

    print(f"[SEED] Seeding completed successfully. All data ready in {target}.")


if __name__ == "__main__":
    seed_database()
