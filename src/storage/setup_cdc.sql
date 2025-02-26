-- Make sure the database has logical replication enabled
-- This requires setting wal_level = logical in postgresql.conf

-- Create tables for CDC tracking
CREATE TABLE IF NOT EXISTS public.users (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS public.products (
    product_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(12, 2) NOT NULL,
    inventory INTEGER NOT NULL DEFAULT 0,
    category VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.orders (
    order_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES public.users(user_id),
    order_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    shipping_address TEXT,
    payment_method VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL REFERENCES public.orders(order_id),
    product_id VARCHAR(50) NOT NULL REFERENCES public.products(product_id),
    quantity INTEGER NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add the trigger to each table
CREATE TRIGGER update_users_modtime
BEFORE UPDATE ON public.users
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_products_modtime
BEFORE UPDATE ON public.products
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_orders_modtime
BEFORE UPDATE ON public.orders
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Set up publication for Debezium CDC
CREATE PUBLICATION dbz_publication FOR TABLE 
    public.users, 
    public.products, 
    public.orders, 
    public.order_items;

-- Grant privileges for Debezium user (if needed)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO postgres;
-- GRANT USAGE ON SCHEMA public TO postgres;
-- GRANT CREATE ON DATABASE mlops TO postgres;

-- Create some test data
INSERT INTO public.users (user_id, username, email) VALUES
    ('user-1', 'johndoe', 'john@example.com'),
    ('user-2', 'janedoe', 'jane@example.com'),
    ('user-3', 'bobsmith', 'bob@example.com');

INSERT INTO public.products (product_id, name, description, price, inventory, category) VALUES
    ('prod-1', 'Laptop', 'High-performance laptop', 1299.99, 10, 'Electronics'),
    ('prod-2', 'Phone', 'Smartphone with great camera', 799.99, 25, 'Electronics'),
    ('prod-3', 'Headphones', 'Noise-cancelling headphones', 199.99, 50, 'Audio');

INSERT INTO public.orders (order_id, user_id, status, total_amount, shipping_address, payment_method) VALUES
    ('order-1', 'user-1', 'COMPLETED', 1299.99, '123 Main St, City', 'CREDIT_CARD'),
    ('order-2', 'user-2', 'PROCESSING', 999.98, '456 Broad St, Town', 'PAYPAL');

INSERT INTO public.order_items (order_id, product_id, quantity, price) VALUES
    ('order-1', 'prod-1', 1, 1299.99),
    ('order-2', 'prod-2', 1, 799.99),
    ('order-2', 'prod-3', 1, 199.99); 