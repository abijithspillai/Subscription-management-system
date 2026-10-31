-- Brightloop Subscription Management System Schema
-- Odoo Cross Makeathon 9.0

PRAGMA foreign_keys = ON;

-- 1. Users & RBAC
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT CHECK(role IN ('ADMIN', 'STAFF', 'CUSTOMER')) NOT NULL DEFAULT 'CUSTOMER',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Products
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    product_type TEXT CHECK(product_type IN ('SOFTWARE', 'SERVICE', 'ADDON')) NOT NULL DEFAULT 'SOFTWARE',
    sales_price DECIMAL(10, 2) NOT NULL,
    cost_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Product Variants (e.g. Brand: Odoo adds 560)
CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    variant_name TEXT NOT NULL,
    price_surcharge DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- 4. Plans
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cost DECIMAL(10, 2) NOT NULL,
    billing_cycle TEXT CHECK(billing_cycle IN ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY')) NOT NULL,
    min_quantity INTEGER NOT NULL DEFAULT 1,
    start_date DATE,
    end_date DATE,
    closure_rule TEXT CHECK(closure_rule IN ('AUTO_CLOSE', 'CAN_RENEW_PAUSE')) NOT NULL DEFAULT 'CAN_RENEW_PAUSE',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5. Quotation Templates
CREATE TABLE IF NOT EXISTS quotation_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    plan_id INTEGER,
    valid_days INTEGER NOT NULL DEFAULT 30,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS quotation_template_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    variant_id INTEGER,
    quantity INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (template_id) REFERENCES quotation_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE SET NULL
);

-- 6. Tax Rules (Admin controlled)
CREATE TABLE IF NOT EXISTS tax_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    rate_percentage DECIMAL(5, 2) NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 7. Discount Rules (Admin controlled)
CREATE TABLE IF NOT EXISTS discount_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    discount_type TEXT CHECK(discount_type IN ('PERCENTAGE', 'FIXED')) NOT NULL,
    value DECIMAL(10, 2) NOT NULL,
    min_purchase DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    min_quantity INTEGER NOT NULL DEFAULT 0,
    start_date DATE,
    end_date DATE,
    usage_limit INTEGER NOT NULL DEFAULT 100,
    times_used INTEGER NOT NULL DEFAULT 0,
    target_product_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (target_product_id) REFERENCES products(id) ON DELETE SET NULL
);

-- 8. Subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    expiry_date DATE,
    next_billing_date DATE NOT NULL,
    payment_terms TEXT NOT NULL DEFAULT 'Immediate Payment',
    status TEXT CHECK(status IN ('DRAFT', 'QUOTATION', 'CONFIRMED', 'ACTIVE', 'PAUSED', 'CLOSED')) NOT NULL DEFAULT 'DRAFT',
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT
);

-- 9. Subscription Lines (Products in a subscription)
CREATE TABLE IF NOT EXISTS subscription_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    variant_id INTEGER,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    tax_rate DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE SET NULL
);

-- 10. Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    subscription_id INTEGER,
    customer_id INTEGER NOT NULL,
    billing_period_start DATE,
    billing_period_end DATE,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    tax_total DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    discount_total DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    amount_paid DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    status TEXT CHECK(status IN ('DRAFT', 'CONFIRMED', 'PAID', 'CANCELLED')) NOT NULL DEFAULT 'DRAFT',
    discount_id INTEGER,
    reminder_count INTEGER NOT NULL DEFAULT 0,
    last_reminder_date DATETIME,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL,
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (discount_id) REFERENCES discount_rules(id) ON DELETE SET NULL
);

-- Unique index to prevent duplicate billing for the same subscription and billing cycle
CREATE UNIQUE INDEX IF NOT EXISTS idx_sub_billing_cycle 
ON invoices(subscription_id, billing_period_start, billing_period_end)
WHERE subscription_id IS NOT NULL AND status != 'CANCELLED';

-- 11. Invoice Line Items
CREATE TABLE IF NOT EXISTS invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    tax_rate DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

-- 12. Payments
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_number TEXT UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_method TEXT CHECK(payment_method IN ('BANK_TRANSFER', 'CREDIT_CARD', 'UPI', 'CASH', 'CHEQUE')) NOT NULL,
    note TEXT,
    recorded_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
);
