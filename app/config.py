import os
import sqlite3
import uuid
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "").strip()
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip().strip('"')
TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("telegram_access_token") or "").strip()

# =====================================================================
# Local Resilient SQLite Database Engine (Postgres/Supabase Mock Adapter)
# Single source of truth when offline or during judging demo
# On Vercel serverless functions, only /tmp is writable
if os.environ.get("VERCEL"):
    LOCAL_DB_PATH = "/tmp/kirana_local.db"
else:
    LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), "kirana_local.db")


class MockQueryBuilder:
    def __init__(self, table_name: str, conn: sqlite3.Connection):
        self.table_name = table_name
        self.conn = conn
        self._select_cols = "*"
        self._filters: List[str] = []
        self._params: List[Any] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._action = "SELECT"
        self._insert_data: Optional[Dict[str, Any]] = None
        self._update_data: Optional[Dict[str, Any]] = None

    def select(self, columns: str = "*"):
        self._select_cols = columns
        self._action = "SELECT"
        return self

    def eq(self, column: str, value: Any):
        self._filters.append(f"{column} = ?")
        self._params.append(str(value) if isinstance(value, uuid.UUID) else value)
        return self

    def neq(self, column: str, value: Any):
        self._filters.append(f"{column} != ?")
        self._params.append(str(value) if isinstance(value, uuid.UUID) else value)
        return self

    def gt(self, column: str, value: Any):
        self._filters.append(f"{column} > ?")
        self._params.append(value)
        return self

    def gte(self, column: str, value: Any):
        self._filters.append(f"{column} >= ?")
        self._params.append(value)
        return self

    def lt(self, column: str, value: Any):
        self._filters.append(f"{column} < ?")
        self._params.append(value)
        return self

    def lte(self, column: str, value: Any):
        self._filters.append(f"{column} <= ?")
        self._params.append(value)
        return self

    def ilike(self, column: str, pattern: str):
        # In SQLite, LIKE is case-insensitive for ASCII characters
        self._filters.append(f"{column} LIKE ?")
        self._params.append(pattern)
        return self

    def order(self, column: str, desc: bool = False):
        direction = "DESC" if desc else "ASC"
        self._order_by = f"{column} {direction}"
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def insert(self, data: Dict[str, Any]):
        self._action = "INSERT"
        self._insert_data = dict(data)
        return self

    def update(self, data: Dict[str, Any]):
        self._action = "UPDATE"
        self._update_data = dict(data)
        return self

    def delete(self):
        self._action = "DELETE"
        return self

    def execute(self):
        cursor = self.conn.cursor()
        result_data = []

        if self._action == "SELECT":
            sql = f"SELECT * FROM {self.table_name}"
            if self._filters:
                sql += " WHERE " + " AND ".join(self._filters)
            if self._order_by:
                sql += f" ORDER BY {self._order_by}"
            if self._limit is not None:
                sql += f" LIMIT {int(self._limit)}"

            cursor.execute(sql, self._params)
            rows = cursor.fetchall()
            cols = [description[0] for description in cursor.description] if cursor.description else []
            for row in rows:
                item = dict(zip(cols, row))
                # If selecting specific embedded relations like "*, order_items(*)"
                if "order_items(*)" in self._select_cols and self.table_name == "orders":
                    sub_cur = self.conn.cursor()
                    sub_cur.execute("SELECT * FROM order_items WHERE order_id = ?", (item["id"],))
                    sub_rows = sub_cur.fetchall()
                    sub_cols = [d[0] for d in sub_cur.description]
                    item["order_items"] = [dict(zip(sub_cols, r)) for r in sub_rows]
                result_data.append(item)

        elif self._action == "INSERT":
            row = dict(self._insert_data or {})
            if "id" not in row or not row["id"]:
                row["id"] = str(uuid.uuid4())
            keys = list(row.keys())
            placeholders = ", ".join(["?"] * len(keys))
            sql = f"INSERT OR REPLACE INTO {self.table_name} ({', '.join(keys)}) VALUES ({placeholders})"
            cursor.execute(sql, [row[k] for k in keys])
            self.conn.commit()
            result_data = [row]

        elif self._action == "UPDATE":
            row = dict(self._update_data or {})
            set_clauses = [f"{k} = ?" for k in row.keys()]
            sql = f"UPDATE {self.table_name} SET {', '.join(set_clauses)}"
            params = list(row.values())
            if self._filters:
                sql += " WHERE " + " AND ".join(self._filters)
                params.extend(self._params)
            cursor.execute(sql, params)
            self.conn.commit()
            # Fetch updated rows
            select_sql = f"SELECT * FROM {self.table_name}"
            if self._filters:
                select_sql += " WHERE " + " AND ".join(self._filters)
            cursor.execute(select_sql, self._params)
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            result_data = [dict(zip(cols, r)) for r in rows]

        elif self._action == "DELETE":
            sql = f"DELETE FROM {self.table_name}"
            if self._filters:
                sql += " WHERE " + " AND ".join(self._filters)
            cursor.execute(sql, self._params)
            self.conn.commit()
            result_data = [{"deleted": True}]

        class MockResult:
            def __init__(self, data):
                self.data = data

        return MockResult(result_data)


class LocalPostgresCompatibleDB:
    def __init__(self, db_path: str = LOCAL_DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.init_schema()

    def table(self, table_name: str) -> MockQueryBuilder:
        return MockQueryBuilder(table_name, self.conn)

    def _ensure_column(self, cursor, table: str, col: str, col_type: str):
        cursor.execute(f"PRAGMA table_info({table})")
        existing = [row[1] for row in cursor.fetchall()]
        if col not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

    def init_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'grocery',
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                unit TEXT DEFAULT 'pack',
                alternative_names TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                phone TEXT NOT NULL,
                name TEXT DEFAULT 'Regular Customer',
                address TEXT DEFAULT 'Indore, MP',
                onboarding_step TEXT DEFAULT 'completed',
                telegram_chat_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                customer_id TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                total REAL NOT NULL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                product_id TEXT,
                product_name TEXT NOT NULL,
                qty INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_flags (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                severity TEXT DEFAULT 'low',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

        # Ensure schema migrations for new columns
        self._ensure_column(cursor, "customers", "address", "TEXT DEFAULT 'Indore, MP'")
        self._ensure_column(cursor, "customers", "onboarding_step", "TEXT DEFAULT 'completed'")
        self._ensure_column(cursor, "customers", "telegram_chat_id", "TEXT")
        self._ensure_column(cursor, "products", "alternative_names", "TEXT")
        self.conn.commit()

        # Seed initial data if empty or missing new products/users
        cursor.execute("SELECT COUNT(*) FROM stores")
        if cursor.fetchone()[0] == 0:
            self._seed_stores()
        
        cursor.execute("SELECT COUNT(*) FROM customers")
        if cursor.fetchone()[0] == 0:
            self._seed_customers()

        # Ensure product catalog is populated with in-stock and alternatives
        cursor.execute("SELECT COUNT(*) FROM products WHERE name LIKE '%Dhara%' OR name LIKE '%Mother Dairy%'")
        if cursor.fetchone()[0] == 0:
            self._seed_products()

    def _seed_stores(self):
        cursor = self.conn.cursor()
        stores = [
            ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Sharma Kirana — Depot Indore', 'Ramesh Sharma', 'Shop 14, Main Market, Depot Area, Indore'),
            ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Sharma Superstore — Vijay Nagar', 'Ramesh Sharma', 'Plot 42, Scheme 54, Vijay Nagar, Indore')
        ]
        cursor.executemany("INSERT OR REPLACE INTO stores (id, name, owner_name, address) VALUES (?, ?, ?, ?)", stores)
        self.conn.commit()

    def _seed_customers(self):
        cursor = self.conn.cursor()
        customers = [
            ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '9876543210', 'Ramesh Patel', 'Flat 402, Shivalik Heights, Depot Area, Indore', 'completed'),
            ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a02', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '9811122233', 'Priya Sharma', 'B-12, Silver Springs, Depot Area, Indore', 'completed'),
            ('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a03', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '9988776655', 'Amit Kumar', '14 Old Palasia, Indore', 'completed')
        ]
        cursor.executemany("INSERT OR REPLACE INTO customers (id, store_id, phone, name, address, onboarding_step) VALUES (?, ?, ?, ?, ?, ?)", customers)
        self.conn.commit()

    def _seed_products(self):
        cursor = self.conn.cursor()
        store_1 = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'
        store_2 = 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22'

        products_s1 = [
            ('11111111-1111-1111-1111-111111111101', store_1, 'Aashirvaad Atta 5kg', 'grocery', 270.00, 15, 'packet', 'Pillsbury Chakki Atta 5kg'),
            ('11111111-1111-1111-1111-111111111102', store_1, 'Pillsbury Chakki Atta 5kg', 'grocery', 265.00, 12, 'packet', 'Aashirvaad Atta 5kg'),
            ('11111111-1111-1111-1111-111111111103', store_1, 'Fortune Sunlite Sunflower Oil 1L', 'grocery', 140.00, 20, 'pouch', 'Saffola Gold Oil 1L'),
            ('11111111-1111-1111-1111-111111111104', store_1, 'Saffola Gold Oil 1L', 'grocery', 185.00, 10, 'pouch', 'Fortune Sunlite Sunflower Oil 1L'),
            ('11111111-1111-1111-1111-111111111105', store_1, 'Fortune Mustard Oil 1L', 'grocery', 155.00, 0, 'bottle', 'Dhara Kachi Ghani Mustard Oil 1L'),
            ('11111111-1111-1111-1111-111111111106', store_1, 'Dhara Kachi Ghani Mustard Oil 1L', 'grocery', 150.00, 14, 'bottle', 'Fortune Mustard Oil 1L'),
            ('11111111-1111-1111-1111-111111111107', store_1, 'Tata Salt 1kg', 'grocery', 28.00, 35, 'packet', 'Aashirvaad Iodized Salt 1kg'),
            ('11111111-1111-1111-1111-111111111108', store_1, 'Aashirvaad Iodized Salt 1kg', 'grocery', 26.00, 25, 'packet', 'Tata Salt 1kg'),
            ('11111111-1111-1111-1111-111111111109', store_1, 'Maggi Noodles 70g', 'snacks', 14.00, 50, 'pc', 'Yippee Noodles 65g'),
            ('11111111-1111-1111-1111-111111111110', store_1, 'Yippee Noodles 65g', 'snacks', 12.00, 30, 'pc', 'Maggi Noodles 70g'),
            ('11111111-1111-1111-1111-111111111111', store_1, 'Parle-G Biscuits 250g', 'snacks', 25.00, 45, 'packet', 'Britannia Good Day Biscuits 200g'),
            ('11111111-1111-1111-1111-111111111112', store_1, 'Britannia Good Day Biscuits 200g', 'snacks', 35.00, 28, 'packet', 'Parle-G Biscuits 250g'),
            ('11111111-1111-1111-1111-111111111113', store_1, 'Amul Taaza Milk 500ml', 'dairy', 30.00, 0, 'pouch', 'Mother Dairy Toned Milk 500ml, Amul Gold Milk 500ml'),
            ('11111111-1111-1111-1111-111111111114', store_1, 'Mother Dairy Toned Milk 500ml', 'dairy', 28.00, 25, 'pouch', 'Amul Taaza Milk 500ml'),
            ('11111111-1111-1111-1111-111111111115', store_1, 'Amul Gold Milk 500ml', 'dairy', 34.00, 18, 'pouch', 'Amul Taaza Milk 500ml'),
            ('11111111-1111-1111-1111-111111111116', store_1, 'Amul Butter 100g', 'dairy', 56.00, 18, 'pc', 'Mother Dairy Butter 100g'),
            ('11111111-1111-1111-1111-111111111117', store_1, 'Surf Excel Easy Wash 1kg', 'household', 145.00, 20, 'packet', 'Ariel Matic Powder 1kg'),
            ('11111111-1111-1111-1111-111111111118', store_1, 'Ariel Matic Powder 1kg', 'household', 210.00, 15, 'packet', 'Surf Excel Easy Wash 1kg'),
            ('11111111-1111-1111-1111-111111111119', store_1, 'Vim Dishwash Gel 500ml', 'household', 105.00, 16, 'bottle', 'Pril Dishwash 500ml'),
        ]
        cursor.executemany("INSERT OR REPLACE INTO products (id, store_id, name, category, price, stock, unit, alternative_names) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", products_s1)

        products_s2 = [
            ('22222222-2222-2222-2222-222222222201', store_2, 'Aashirvaad Atta 5kg', 'grocery', 275.00, 2, 'packet', 'Pillsbury Chakki Atta 5kg'),
            ('22222222-2222-2222-2222-222222222202', store_2, 'Tata Salt 1kg', 'grocery', 28.00, 100, 'packet', 'Aashirvaad Iodized Salt 1kg'),
            ('22222222-2222-2222-2222-222222222203', store_2, 'Fortune Mustard Oil 1L', 'grocery', 155.00, 15, 'bottle', 'Dhara Kachi Ghani Mustard Oil 1L'),
            ('22222222-2222-2222-2222-222222222204', store_2, 'Maggi Noodles 70g', 'snacks', 14.00, 80, 'pc', 'Yippee Noodles 65g'),
            ('22222222-2222-2222-2222-222222222205', store_2, 'Mother Dairy Toned Milk 500ml', 'dairy', 28.00, 25, 'pouch', 'Amul Taaza Milk 500ml'),
            ('22222222-2222-2222-2222-222222222206', store_2, 'Surf Excel Easy Wash 1kg', 'household', 145.00, 20, 'packet', 'Ariel Matic Powder 1kg'),
        ]
        cursor.executemany("INSERT OR REPLACE INTO products (id, store_id, name, category, price, stock, unit, alternative_names) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", products_s2)
        self.conn.commit()


# Initialize Client (Cloud Supabase if tables exist, else Resilient Local Adapter)
IS_LOCAL_DB = True
supabase = None

if SUPABASE_URL and SUPABASE_KEY and SUPABASE_KEY != "your-supabase-service-key":
    try:
        from supabase import create_client, Client
        client_instance: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Test query to verify tables are accessible
        res = client_instance.table("stores").select("id").limit(1).execute()
        supabase = client_instance
        IS_LOCAL_DB = False
        print("[DATABASE] Connected successfully to Cloud Supabase PostgreSQL.")
    except Exception as e:
        print(f"[DATABASE] Notice: Could not connect to Cloud Supabase tables ({e}). Using Resilient Local PostgreSQL Engine.")
        supabase = LocalPostgresCompatibleDB()
        IS_LOCAL_DB = True
else:
    print("[DATABASE] Running on Resilient Local PostgreSQL Database Engine (Offline & Live Demo Safe).")
    supabase = LocalPostgresCompatibleDB()
    IS_LOCAL_DB = True

HAS_GEMINI_KEY = bool(GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key")
