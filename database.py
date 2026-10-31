import sqlite3
import os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'brightloop.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()

    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN reminder_count INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN last_reminder_date DATETIME")
    except sqlite3.OperationalError:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    conn.commit()

    seed_data(conn)
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()
    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        return

    print("Seeding initial Brightloop data...")

    # 1. Users (Admin, Staff, Customers)
    # Password policy: >8 chars, uppercase, lowercase, special char
    admin_pw = generate_password_hash("Admin@Brightloop1")
    staff_pw = generate_password_hash("Staff@Brightloop1")
    cust_pw1 = generate_password_hash("Customer@Brightloop1")
    cust_pw2 = generate_password_hash("Enterprise@Brightloop1")

    users = [
        ("Admin Director", "admin@brightloop.com", admin_pw, "ADMIN"),
        ("Sarah Jenkins (Sales)", "sarah.staff@brightloop.com", staff_pw, "STAFF"),
        ("Apex Retail Mart", "billing@apexretail.in", cust_pw1, "CUSTOMER"),
        ("Global Logistics Corp", "billing@globallogistics.com", cust_pw2, "CUSTOMER")
    ]
    cursor.executemany(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        users
    )

    # 2. Products
    products = [
        ("Brightloop Business ERP", "SOFTWARE", 199.00, 45.00, "Core business management system", 1),
        ("Automated Payroll Module", "ADDON", 79.00, 15.00, "Monthly recurring payroll module", 1),
        ("Dedicated Cloud Server", "SERVICE", 350.00, 120.00, "Managed dedicated cloud infrastructure", 1),
        ("Helpdesk & Ticketing Pro", "SOFTWARE", 99.00, 20.00, "Multi-channel ticketing software", 1)
    ]
    cursor.executemany(
        "INSERT INTO products (name, product_type, sales_price, cost_price, notes, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        products
    )

    # 3. Product Variants (e.g. Odoo brand adds 560 as per specification)
    variants = [
        (1, "Standard Edition", 0.00),
        (1, "Odoo Brand Integration", 560.00),  # Explicit requirement from problem prompt!
        (3, "Dual-Core 8GB RAM", 0.00),
        (3, "Octa-Core 32GB High-Performance", 180.00)
    ]
    cursor.executemany(
        "INSERT INTO product_variants (product_id, variant_name, price_surcharge) VALUES (?, ?, ?)",
        variants
    )

    # 4. Plans
    today = date.today()
    plans = [
        ("Growth Plan (Monthly)", 149.00, "MONTHLY", 1, today, today + timedelta(days=365), "CAN_RENEW_PAUSE", 1),
        ("Enterprise Plan (Yearly)", 1800.00, "YEARLY", 5, today, today + timedelta(days=730), "CAN_RENEW_PAUSE", 1),
        ("Starter Plan (Weekly)", 49.00, "WEEKLY", 1, today, today + timedelta(days=90), "AUTO_CLOSE", 1),
        ("Daily Pass", 19.00, "DAILY", 2, today, today + timedelta(days=60), "AUTO_CLOSE", 1)
    ]
    cursor.executemany(
        "INSERT INTO plans (name, cost, billing_cycle, min_quantity, start_date, end_date, closure_rule, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        plans
    )

    # 5. Tax Rules
    taxes = [
        ("Standard VAT / GST (18%)", 18.00, 1),
        ("Reduced Tech Services (5%)", 5.00, 0),
        ("Zero Tax Exemption (0%)", 0.00, 0)
    ]
    cursor.executemany(
        "INSERT INTO tax_rules (name, rate_percentage, is_default) VALUES (?, ?, ?)",
        taxes
    )

    # 6. Discount Rules
    discounts = [
        ("BULKSEATS20", "PERCENTAGE", 20.00, 300.00, 3, today, today + timedelta(days=60), 50, 2, None, 1),
        ("WELCOME50", "FIXED", 50.00, 100.00, 1, today, today + timedelta(days=30), 100, 5, None, 1),
        ("ODOOSPECIAL", "FIXED", 150.00, 500.00, 1, today, today + timedelta(days=90), 25, 1, 1, 1)
    ]
    cursor.executemany(
        "INSERT INTO discount_rules (code, discount_type, value, min_purchase, min_quantity, start_date, end_date, usage_limit, times_used, target_product_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        discounts
    )

    # 7. Quotation Templates
    cursor.execute(
        "INSERT INTO quotation_templates (name, plan_id, valid_days, notes) VALUES (?, ?, ?, ?)",
        ("Enterprise Ready Template", 2, 30, "Pre-configured package with Odoo Integration and Cloud Server")
    )
    tmpl_id = cursor.lastrowid
    cursor.execute("INSERT INTO quotation_template_lines (template_id, product_id, variant_id, quantity) VALUES (?, 1, 2, 5)", (tmpl_id,))
    cursor.execute("INSERT INTO quotation_template_lines (template_id, product_id, variant_id, quantity) VALUES (?, 3, 4, 1)", (tmpl_id,))

    # 8. Sample Subscriptions
    # Sub 1: Active
    cursor.execute("""
        INSERT INTO subscriptions 
        (sub_number, customer_id, plan_id, start_date, expiry_date, next_billing_date, payment_terms, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SUB-2026-0001", 3, 1, today - timedelta(days=45), today + timedelta(days=320),
        today, "Net 15 Days", "ACTIVE", "Active monthly subscription for Corner Retail"
    ))
    sub1_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rate)
        VALUES (?, 1, 1, 2, 199.00, 18.00)
    """, (sub1_id,))
    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rate)
        VALUES (?, 2, NULL, 1, 79.00, 18.00)
    """, (sub1_id,))

    # Sub 2: Active (Enterprise with Odoo variant)
    cursor.execute("""
        INSERT INTO subscriptions 
        (sub_number, customer_id, plan_id, start_date, expiry_date, next_billing_date, payment_terms, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SUB-2026-0002", 4, 2, today - timedelta(days=60), today + timedelta(days=670),
        today + timedelta(days=305), "Immediate Payment", "ACTIVE", "Large annual corporate contract"
    ))
    sub2_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rate)
        VALUES (?, 1, 2, 10, 759.00, 18.00)
    """, (sub2_id,))

    # Sub 3: Quotation stage
    cursor.execute("""
        INSERT INTO subscriptions 
        (sub_number, customer_id, plan_id, start_date, expiry_date, next_billing_date, payment_terms, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SUB-2026-0003", 3, 1, today, today + timedelta(days=365),
        today + timedelta(days=30), "Net 30 Days", "QUOTATION", "Under customer review"
    ))
    sub3_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rate)
        VALUES (?, 4, NULL, 3, 99.00, 18.00)
    """, (sub3_id,))

    # 9. Invoices
    # Paid Invoice
    cursor.execute("""
        INSERT INTO invoices 
        (invoice_number, subscription_id, customer_id, billing_period_start, billing_period_end, invoice_date, due_date, subtotal, tax_total, discount_total, total_amount, amount_paid, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "INV-2026-0001", sub1_id, 3, today - timedelta(days=45), today - timedelta(days=15),
        today - timedelta(days=45), today - timedelta(days=30), 477.00, 85.86, 0.00, 562.86, 562.86, "PAID", "Initial monthly cycle paid"
    ))
    inv1_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO invoice_lines (invoice_id, description, quantity, unit_price, tax_rate, total_amount)
        VALUES (?, 'Brightloop Business ERP (Standard Edition)', 2, 199.00, 18.00, 398.00)
    """, (inv1_id,))
    cursor.execute("""
        INSERT INTO invoice_lines (invoice_id, description, quantity, unit_price, tax_rate, total_amount)
        VALUES (?, 'Automated Payroll Module', 1, 79.00, 18.00, 79.00)
    """, (inv1_id,))

    # Payment for Inv 1
    cursor.execute("""
        INSERT INTO payments (payment_number, invoice_id, amount, payment_date, payment_method, note, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "PAY-2026-0001", inv1_id, 562.86, today - timedelta(days=35), "BANK_TRANSFER", "Bank ref #BT99281X", 1
    ))

    # Overdue Invoice (Needs chasing)
    cursor.execute("""
        INSERT INTO invoices 
        (invoice_number, subscription_id, customer_id, billing_period_start, billing_period_end, invoice_date, due_date, subtotal, tax_total, discount_total, total_amount, amount_paid, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "INV-2026-0002", sub2_id, 4, today - timedelta(days=60), today + timedelta(days=305),
        today - timedelta(days=60), today - timedelta(days=45), 7590.00, 1366.20, 150.00, 8806.20, 4000.00, "CONFIRMED", "First milestone paid, remaining overdue"
    ))
    inv2_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO invoice_lines (invoice_id, description, quantity, unit_price, tax_rate, total_amount)
        VALUES (?, 'Brightloop Business ERP (Odoo Brand Integration)', 10, 759.00, 18.00, 7590.00)
    """, (inv2_id,))
    cursor.execute("""
        INSERT INTO payments (payment_number, invoice_id, amount, payment_date, payment_method, note, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "PAY-2026-0002", inv2_id, 4000.00, today - timedelta(days=40), "CREDIT_CARD", "Partial downpayment", 2
    ))

    # 10. Seed Initial Activity Logs for Audit Trail
    audit_events = [
        (1, "PRODUCT_CREATED", "PRODUCT", 1, "Admin Director registered core product 'Brightloop Business ERP' (₹199/mo)"),
        (1, "VARIANT_ADDED", "VARIANT", 2, "Added product variant 'Odoo Brand Integration' (+₹560 surcharge)"),
        (1, "PLAN_CREATED", "PLAN", 1, "Registered plan 'Growth Plan (Monthly)' with CAN_RENEW_PAUSE closure rule"),
        (2, "QUOTE_CREATED", "SUBSCRIPTION", 3, "Sarah Jenkins (Sales) drafted proposal SUB-2026-0003 for Apex Retail Mart"),
        (1, "BATCH_BILLING_RUN", "INVOICE", 1, "Automated billing day generated monthly GST tax bills without duplicates"),
        (3, "UPI_PAYMENT_SUCCESS", "PAYMENT", 1, "Apex Retail Mart settled invoice INV-2026-0001 (₹562.86) via Dynamic UPI QR")
    ]
    cursor.executemany(
        "INSERT INTO activity_logs (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
        audit_events
    )

    conn.commit()
    print("Database seeding completed successfully.")

if __name__ == '__main__':
    init_db()
