-- =====================================================================
-- Zero-Click Store Operator — Relational Schema & Seed Data
-- Hackathon: SlowBros Labs x PyData Indore — Track 1
-- Single source of truth in Supabase PostgreSQL
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables in reverse dependency order if resetting
DROP TABLE IF EXISTS anomaly_flags CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS stores CASCADE;

-- 1. Stores Table (Multi-Store Support)
CREATE TABLE stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_name VARCHAR(255) NOT NULL DEFAULT 'Ramesh Sharma',
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Products / Inventory Table
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) DEFAULT 'grocery',
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    unit VARCHAR(50) DEFAULT 'pack',
    alternative_names TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Customers Table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    phone VARCHAR(50) NOT NULL,
    name VARCHAR(255) DEFAULT 'Regular Customer',
    address TEXT DEFAULT 'Indore, MP',
    onboarding_step VARCHAR(50) DEFAULT 'completed', -- completed | awaiting_name | awaiting_address
    telegram_chat_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_store_customer UNIQUE (store_id, phone)
);

-- 4. Orders Table
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft', -- draft | confirmed | cancelled
    total NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confirmed_at TIMESTAMP WITH TIME ZONE
);

-- 5. Order Items Table (Relational Line Items - 1 Row Per Product)
CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,
    qty INTEGER NOT NULL CHECK (qty > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(10, 2) NOT NULL CHECK (line_total >= 0)
);

-- 6. Anomaly Flags Table (Rule-Based Flags - 1 Row Per Flag)
CREATE TABLE anomaly_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'low', -- low | medium | high
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexing for high-frequency queries
CREATE INDEX idx_products_store ON products(store_id);
CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_customers_store_phone ON customers(store_id, phone);
CREATE INDEX idx_orders_store ON orders(store_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_anomaly_store ON anomaly_flags(store_id);

-- =====================================================================
-- Seed Data: 2 Multi-Store Locations, 3 Customers, Products & Alternatives
-- =====================================================================

INSERT INTO stores (id, name, owner_name, address) VALUES
('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Sharma Kirana — Depot Indore', 'Ramesh Sharma', 'Shop 14, Main Market, Depot Area, Indore'),
('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Sharma Superstore — Vijay Nagar', 'Ramesh Sharma', 'Plot 42, Scheme 54, Vijay Nagar, Indore');

-- 3 Pre-Registered Customers for Store 1
INSERT INTO customers (id, store_id, phone, name, address, onboarding_step) VALUES
('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '9876543210', 'Ramesh Patel', 'Flat 402, Shivalik Heights, Depot Area, Indore', 'completed'),
('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a02', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '9811122233', 'Priya Sharma', 'B-12, Silver Springs, Depot Area, Indore', 'completed'),
('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a03', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '9988776655', 'Amit Kumar', '14 Old Palasia, Indore', 'completed');

-- Store 1: Depot Indore Products (with in-stock, out-of-stock, and alternatives)
INSERT INTO products (id, store_id, name, category, price, stock, unit, alternative_names) VALUES
('11111111-1111-1111-1111-111111111101', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Aashirvaad Atta 5kg', 'grocery', 270.00, 15, 'packet', 'Pillsbury Chakki Atta 5kg'),
('11111111-1111-1111-1111-111111111102', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Pillsbury Chakki Atta 5kg', 'grocery', 265.00, 12, 'packet', 'Aashirvaad Atta 5kg'),
('11111111-1111-1111-1111-111111111103', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Fortune Sunlite Sunflower Oil 1L', 'grocery', 140.00, 20, 'pouch', 'Saffola Gold Oil 1L'),
('11111111-1111-1111-1111-111111111104', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Saffola Gold Oil 1L', 'grocery', 185.00, 10, 'pouch', 'Fortune Sunlite Sunflower Oil 1L'),
('11111111-1111-1111-1111-111111111105', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Fortune Mustard Oil 1L', 'grocery', 155.00, 0, 'bottle', 'Dhara Kachi Ghani Mustard Oil 1L'), -- Out of stock!
('11111111-1111-1111-1111-111111111106', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Dhara Kachi Ghani Mustard Oil 1L', 'grocery', 150.00, 14, 'bottle', 'Fortune Mustard Oil 1L'), -- Alternative for mustard oil
('11111111-1111-1111-1111-111111111107', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Tata Salt 1kg', 'grocery', 28.00, 35, 'packet', 'Aashirvaad Iodized Salt 1kg'),
('11111111-1111-1111-1111-111111111108', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Aashirvaad Iodized Salt 1kg', 'grocery', 26.00, 25, 'packet', 'Tata Salt 1kg'),
('11111111-1111-1111-1111-111111111109', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Maggi Noodles 70g', 'snacks', 14.00, 50, 'pc', 'Yippee Noodles 65g'),
('11111111-1111-1111-1111-111111111110', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Yippee Noodles 65g', 'snacks', 12.00, 30, 'pc', 'Maggi Noodles 70g'),
('11111111-1111-1111-1111-111111111111', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Parle-G Biscuits 250g', 'snacks', 25.00, 45, 'packet', 'Britannia Good Day Biscuits 200g'),
('11111111-1111-1111-1111-111111111112', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Britannia Good Day Biscuits 200g', 'snacks', 35.00, 28, 'packet', 'Parle-G Biscuits 250g'),
('11111111-1111-1111-1111-111111111113', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Amul Taaza Milk 500ml', 'dairy', 30.00, 0, 'pouch', 'Mother Dairy Toned Milk 500ml, Amul Gold Milk 500ml'), -- Out of stock!
('11111111-1111-1111-1111-111111111114', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Mother Dairy Toned Milk 500ml', 'dairy', 28.00, 25, 'pouch', 'Amul Taaza Milk 500ml'), -- Alternative for milk
('11111111-1111-1111-1111-111111111115', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Amul Gold Milk 500ml', 'dairy', 34.00, 18, 'pouch', 'Amul Taaza Milk 500ml'), -- Premium milk alternative
('11111111-1111-1111-1111-111111111116', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Amul Butter 100g', 'dairy', 56.00, 18, 'pc', 'Mother Dairy Butter 100g'),
('11111111-1111-1111-1111-111111111117', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Surf Excel Easy Wash 1kg', 'household', 145.00, 20, 'packet', 'Ariel Matic Powder 1kg'),
('11111111-1111-1111-1111-111111111118', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Ariel Matic Powder 1kg', 'household', 210.00, 15, 'packet', 'Surf Excel Easy Wash 1kg'),
('11111111-1111-1111-1111-111111111119', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Vim Dishwash Gel 500ml', 'household', 105.00, 16, 'bottle', 'Pril Dishwash 500ml'),
('11111111-1111-1111-1111-111111111120', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Indori Poha 1kg', 'grocery', 55.00, 30, 'packet', 'Indori Poha 500g'),
('11111111-1111-1111-1111-111111111121', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'Indori Poha 500g', 'grocery', 30.00, 25, 'packet', 'Indori Poha 1kg');

-- Store 2: Vijay Nagar Products
INSERT INTO products (id, store_id, name, category, price, stock, unit, alternative_names) VALUES
('22222222-2222-2222-2222-222222222201', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Aashirvaad Atta 5kg', 'grocery', 275.00, 2, 'packet', 'Pillsbury Chakki Atta 5kg'),
('22222222-2222-2222-2222-222222222202', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Tata Salt 1kg', 'grocery', 28.00, 100, 'packet', 'Aashirvaad Iodized Salt 1kg'),
('22222222-2222-2222-2222-222222222203', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Fortune Mustard Oil 1L', 'grocery', 155.00, 15, 'bottle', 'Dhara Kachi Ghani Mustard Oil 1L'),
('22222222-2222-2222-2222-222222222204', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Maggi Noodles 70g', 'snacks', 14.00, 80, 'pc', 'Yippee Noodles 65g'),
('22222222-2222-2222-2222-222222222205', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Mother Dairy Toned Milk 500ml', 'dairy', 28.00, 25, 'pouch', 'Amul Taaza Milk 500ml'),
('22222222-2222-2222-2222-222222222206', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'Surf Excel Easy Wash 1kg', 'household', 145.00, 20, 'packet', 'Ariel Matic Powder 1kg');
