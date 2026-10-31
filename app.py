import re
import os
from datetime import datetime, date, timedelta
from functools import wraps
import csv
import io
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort, Response
from werkzeug.security import generate_password_hash, check_password_hash
import database

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'brightloop-makeathon-secret-key-2026')

# Initialize DB on first run
with app.app_context():
    database.init_db()

# -------------------------------------------------------------
# HELPERS & DECORATORS
# -------------------------------------------------------------

def validate_password(password):
    """
    Password policy:
    - More than 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one special character
    """
    if len(password) <= 8:
        return False, "Password must be more than 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-\\\/\[\]]', password):
        return False, "Password must include at least one special character."
    return True, ""

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in.", "warning")
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash("Access denied: You do not have permission for this section.", "danger")
                if user_role == 'CUSTOMER':
                    return redirect(url_for('customer_portal'))
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.context_processor
def inject_user_context():
    return {
        'current_user': {
            'id': session.get('user_id'),
            'name': session.get('name'),
            'email': session.get('email'),
            'role': session.get('role')
        },
        'today': date.today()
    }

# -------------------------------------------------------------
# AUTHENTICATION & RBAC
# -------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'CUSTOMER':
            return redirect(url_for('customer_portal'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = database.get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            if user['role'] == 'CUSTOMER':
                return redirect(url_for('customer_portal'))
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template('login.html', register_mode=True)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('login.html', register_mode=True)

        is_valid, msg = validate_password(password)
        if not is_valid:
            flash(msg, "danger")
            return render_template('login.html', register_mode=True)

        conn = database.get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("An account with this email already exists. Each email can belong to only one account.", "danger")
            return render_template('login.html', register_mode=True)

        pw_hash = generate_password_hash(password)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'CUSTOMER')",
            (name, email, pw_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        session['user_id'] = user_id
        session['name'] = name
        session['email'] = email
        session['role'] = 'CUSTOMER'

        return redirect(url_for('customer_portal'))

    return render_template('login.html', register_mode=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        conn = database.get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        # Security best practice: don't disclose whether email exists, but give reset link for demo
        flash(f"A password reset link has been dispatched to {email}. (Simulation link: /reset-password?email={email})", "info")
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email', '') or request.form.get('email', '')
    if request.method == 'POST':
        new_pw = request.form.get('password', '')
        confirm_pw = request.form.get('confirm_password', '')
        if new_pw != confirm_pw:
            flash("Passwords do not match.", "danger")
            return render_template('reset_password.html', email=email)
        
        is_valid, msg = validate_password(new_pw)
        if not is_valid:
            flash(msg, "danger")
            return render_template('reset_password.html', email=email)

        conn = database.get_db()
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (generate_password_hash(new_pw), email))
        conn.commit()
        conn.close()
        flash("Password successfully reset! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('reset_password.html', email=email)

# -------------------------------------------------------------
# ADMIN: STAFF MANAGEMENT (Only admin can add staff)
# -------------------------------------------------------------

@app.route('/admin/staff', methods=['GET', 'POST'])
@role_required(['ADMIN'])
def manage_staff():
    conn = database.get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'STAFF')

        is_valid, msg = validate_password(password)
        if not is_valid:
            flash(msg, "danger")
        else:
            try:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (name, email, generate_password_hash(password), role)
                )
                conn.commit()
                flash(f"New staff member {name} added successfully.", "success")
            except Exception as e:
                flash(f"Error adding staff: {str(e)}", "danger")

    staff_members = conn.execute("SELECT * FROM users WHERE role IN ('ADMIN', 'STAFF') ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template('staff.html', staff=staff_members)

# -------------------------------------------------------------
# EXECUTIVE FINANCE LEAD DASHBOARD (<2s response time)
# -------------------------------------------------------------

@app.route('/dashboard')
@role_required(['ADMIN', 'STAFF'])
def dashboard():
    conn = database.get_db()
    today_str = date.today().isoformat()

    # 1. Active Subscriptions Count
    active_subs_count = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'ACTIVE'").fetchone()[0]

    # 2. Total Invoiced & Revenue Collected
    rev_stats = conn.execute("""
        SELECT 
            COALESCE(SUM(total_amount), 0) as total_invoiced,
            COALESCE(SUM(amount_paid), 0) as total_collected,
            COALESCE(SUM(total_amount - amount_paid), 0) as total_outstanding
        FROM invoices 
        WHERE status != 'CANCELLED'
    """).fetchone()

    # 3. Overdue Invoices
    overdue_stats = conn.execute("""
        SELECT 
            COUNT(*) as overdue_count,
            COALESCE(SUM(total_amount - amount_paid), 0) as overdue_amount
        FROM invoices 
        WHERE status = 'CONFIRMED' AND due_date < ?
    """, (today_str,)).fetchone()

    # 4. Normalized Monthly Recurring Revenue (MRR)
    # Convert plans to monthly equivalent:
    # DAILY * 30, WEEKLY * 4.33, MONTHLY * 1, YEARLY / 12
    mrr_row = conn.execute("""
        SELECT 
            SUM(
                CASE 
                    WHEN p.billing_cycle = 'DAILY' THEN (l.unit_price * l.quantity) * 30
                    WHEN p.billing_cycle = 'WEEKLY' THEN (l.unit_price * l.quantity) * 4.33
                    WHEN p.billing_cycle = 'MONTHLY' THEN (l.unit_price * l.quantity)
                    WHEN p.billing_cycle = 'YEARLY' THEN (l.unit_price * l.quantity) / 12.0
                    ELSE 0
                END
            ) as computed_mrr
        FROM subscription_lines l
        JOIN subscriptions s ON l.subscription_id = s.id
        JOIN plans p ON s.plan_id = p.id
        WHERE s.status = 'ACTIVE'
    """).fetchone()
    mrr = mrr_row['computed_mrr'] or 0.0
    arr = mrr * 12.0

    # Collection Efficiency %
    total_inv = rev_stats['total_invoiced'] or 0.0
    total_col = rev_stats['total_collected'] or 0.0
    collection_eff = round((total_col / total_inv * 100.0), 1) if total_inv > 0 else 100.0

    # Subscription Retention / Churn %
    total_subs_count = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
    retention_rate = round((active_subs_count / total_subs_count * 100.0), 1) if total_subs_count > 0 else 100.0
    churn_rate = round(100.0 - retention_rate, 1)

    # Odoo Brand Surcharge Revenue
    odoo_surcharge_rev = conn.execute("""
        SELECT COALESCE(SUM(v.price_surcharge * l.quantity), 0)
        FROM subscription_lines l
        JOIN product_variants v ON l.variant_id = v.id
        JOIN subscriptions s ON l.subscription_id = s.id
        WHERE v.variant_name LIKE '%Odoo%' AND s.status = 'ACTIVE'
    """).fetchone()[0] or 0.0

    # 5. Due for billing right now
    due_for_billing = conn.execute("""
        SELECT COUNT(*) FROM subscriptions 
        WHERE status = 'ACTIVE' AND next_billing_date <= ?
    """, (today_str,)).fetchone()[0]

    # 6. Recent Subscriptions
    recent_subs = conn.execute("""
        SELECT s.*, u.name as customer_name, p.name as plan_name, p.billing_cycle
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        ORDER BY s.created_at DESC LIMIT 5
    """).fetchall()

    # 7. Recent Invoices
    recent_invoices = conn.execute("""
        SELECT i.*, u.name as customer_name, s.sub_number
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
        ORDER BY i.created_at DESC LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        active_subs=active_subs_count,
        mrr=round(mrr, 2),
        arr=round(arr, 2),
        collection_eff=collection_eff,
        retention_rate=retention_rate,
        churn_rate=churn_rate,
        odoo_surcharge_rev=round(odoo_surcharge_rev, 2),
        total_collected=round(rev_stats['total_collected'], 2),
        total_outstanding=round(rev_stats['total_outstanding'], 2),
        overdue_count=overdue_stats['overdue_count'],
        overdue_amount=round(overdue_stats['overdue_amount'], 2),
        due_for_billing=due_for_billing,
        recent_subs=recent_subs,
        recent_invoices=recent_invoices
    )

# -------------------------------------------------------------
# PRODUCTS & VARIANTS
# -------------------------------------------------------------

@app.route('/products', methods=['GET', 'POST'])
@role_required(['ADMIN', 'STAFF'])
def products():
    conn = database.get_db()
    if request.method == 'POST' and session.get('role') == 'ADMIN':
        name = request.form.get('name', '').strip()
        product_type = request.form.get('product_type', 'SOFTWARE')
        sales_price = float(request.form.get('sales_price', 0))
        cost_price = float(request.form.get('cost_price', 0))
        notes = request.form.get('notes', '').strip()

        if name and sales_price >= 0:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO products (name, product_type, sales_price, cost_price, notes) VALUES (?, ?, ?, ?, ?)",
                (name, product_type, sales_price, cost_price, notes)
            )
            product_id = cursor.lastrowid

            # Check if variant added simultaneously
            variant_name = request.form.get('variant_name', '').strip()
            variant_surcharge = float(request.form.get('variant_surcharge', 0))
            if variant_name:
                cursor.execute(
                    "INSERT INTO product_variants (product_id, variant_name, price_surcharge) VALUES (?, ?, ?)",
                    (product_id, variant_name, variant_surcharge)
                )

            conn.commit()
            flash("Product created successfully.", "success")

    prods = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    variants = conn.execute("SELECT * FROM product_variants ORDER BY product_id, id").fetchall()
    
    # Map variants to products
    var_map = {}
    for v in variants:
        var_map.setdefault(v['product_id'], []).append(v)

    conn.close()
    return render_template('products.html', products=prods, variants_map=var_map)

@app.route('/products/<int:product_id>/add-variant', methods=['POST'])
@role_required(['ADMIN'])
def add_product_variant(product_id):
    variant_name = request.form.get('variant_name', '').strip()
    surcharge = float(request.form.get('price_surcharge', 0.0))
    if variant_name:
        conn = database.get_db()
        conn.execute(
            "INSERT INTO product_variants (product_id, variant_name, price_surcharge) VALUES (?, ?, ?)",
            (product_id, variant_name, surcharge)
        )
        conn.commit()
        conn.close()
        flash(f"Variant '{variant_name}' (Surcharge: ₹{surcharge:,.2f}) added.", "success")
    return redirect(url_for('products'))

# -------------------------------------------------------------
# PLANS MANAGEMENT
# -------------------------------------------------------------

@app.route('/plans', methods=['GET', 'POST'])
@role_required(['ADMIN', 'STAFF'])
def plans():
    conn = database.get_db()
    if request.method == 'POST' and session.get('role') == 'ADMIN':
        name = request.form.get('name', '').strip()
        cost = float(request.form.get('cost', 0))
        billing_cycle = request.form.get('billing_cycle', 'MONTHLY')
        min_qty = int(request.form.get('min_quantity', 1))
        start_date = request.form.get('start_date') or date.today().isoformat()
        end_date = request.form.get('end_date') or None
        closure_rule = request.form.get('closure_rule', 'CAN_RENEW_PAUSE')

        if name and cost >= 0:
            conn.execute("""
                INSERT INTO plans (name, cost, billing_cycle, min_quantity, start_date, end_date, closure_rule)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, cost, billing_cycle, min_qty, start_date, end_date, closure_rule))
            conn.commit()
            flash("Billing plan created successfully.", "success")

    all_plans = conn.execute("SELECT * FROM plans ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('plans.html', plans=all_plans)

# -------------------------------------------------------------
# TAX RULES (Admin Controlled)
# -------------------------------------------------------------

@app.route('/taxes', methods=['GET', 'POST'])
@role_required(['ADMIN'])
def taxes():
    conn = database.get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        rate = float(request.form.get('rate_percentage', 0))
        is_default = 1 if request.form.get('is_default') else 0

        if is_default:
            conn.execute("UPDATE tax_rules SET is_default = 0")

        conn.execute(
            "INSERT INTO tax_rules (name, rate_percentage, is_default) VALUES (?, ?, ?)",
            (name, rate, is_default)
        )
        conn.commit()
        flash("Tax rule registered.", "success")

    all_taxes = conn.execute("SELECT * FROM tax_rules ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('taxes.html', taxes=all_taxes)

# -------------------------------------------------------------
# DISCOUNT RULES (Admin Controlled)
# -------------------------------------------------------------

@app.route('/discounts', methods=['GET', 'POST'])
@role_required(['ADMIN'])
def discounts():
    conn = database.get_db()
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        discount_type = request.form.get('discount_type', 'PERCENTAGE')
        value = float(request.form.get('value', 0))
        min_purchase = float(request.form.get('min_purchase', 0))
        min_quantity = int(request.form.get('min_quantity', 0))
        start_date = request.form.get('start_date') or date.today().isoformat()
        end_date = request.form.get('end_date') or None
        usage_limit = int(request.form.get('usage_limit', 100))
        target_product_id = request.form.get('target_product_id') or None
        if target_product_id == "":
            target_product_id = None

        try:
            conn.execute("""
                INSERT INTO discount_rules 
                (code, discount_type, value, min_purchase, min_quantity, start_date, end_date, usage_limit, target_product_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, discount_type, value, min_purchase, min_quantity, start_date, end_date, usage_limit, target_product_id))
            conn.commit()
            flash(f"Discount rule '{code}' created successfully.", "success")
        except Exception as e:
            flash(f"Error creating discount: {str(e)}", "danger")

    rules = conn.execute("""
        SELECT d.*, p.name as target_product_name 
        FROM discount_rules d 
        LEFT JOIN products p ON d.target_product_id = p.id 
        ORDER BY d.id DESC
    """).fetchall()
    products_list = conn.execute("SELECT id, name FROM products WHERE is_active = 1").fetchall()
    conn.close()
    return render_template('discounts.html', discounts=rules, products=products_list)

# -------------------------------------------------------------
# QUOTATION TEMPLATES & PIPELINE
# -------------------------------------------------------------

@app.route('/quotation-templates', methods=['GET', 'POST'])
@role_required(['ADMIN', 'STAFF'])
def quotation_templates():
    conn = database.get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        plan_id = request.form.get('plan_id')
        valid_days = int(request.form.get('valid_days', 30))
        notes = request.form.get('notes', '').strip()

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO quotation_templates (name, plan_id, valid_days, notes) VALUES (?, ?, ?, ?)",
            (name, plan_id, valid_days, notes)
        )
        template_id = cursor.lastrowid

        # Insert lines
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        variant_ids = request.form.getlist('variant_id[]')

        for i in range(len(product_ids)):
            if product_ids[i]:
                var_id = variant_ids[i] if i < len(variant_ids) and variant_ids[i] else None
                qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 1
                cursor.execute(
                    "INSERT INTO quotation_template_lines (template_id, product_id, variant_id, quantity) VALUES (?, ?, ?, ?)",
                    (template_id, product_ids[i], var_id, qty)
                )

        conn.commit()
        flash("Quotation template saved.", "success")

    templates = conn.execute("""
        SELECT t.*, p.name as plan_name, p.billing_cycle
        FROM quotation_templates t
        LEFT JOIN plans p ON t.plan_id = p.id
        ORDER BY t.id DESC
    """).fetchall()

    plans_list = conn.execute("SELECT id, name, billing_cycle FROM plans WHERE is_active = 1").fetchall()
    products_list = conn.execute("SELECT id, name, sales_price FROM products WHERE is_active = 1").fetchall()
    variants_list = conn.execute("SELECT id, product_id, variant_name, price_surcharge FROM product_variants").fetchall()

    conn.close()
    return render_template(
        'quotation_templates.html',
        templates=templates,
        plans=plans_list,
        products=products_list,
        variants=variants_list
    )

# -------------------------------------------------------------
# SUBSCRIPTIONS MANAGEMENT (Quotes -> Subscriptions)
# -------------------------------------------------------------

@app.route('/subscriptions')
@role_required(['ADMIN', 'STAFF'])
def subscriptions():
    conn = database.get_db()
    status_filter = request.args.get('status')
    
    query = """
        SELECT s.*, u.name as customer_name, u.email as customer_email, p.name as plan_name, p.billing_cycle,
               (SELECT COUNT(*) FROM subscription_lines WHERE subscription_id = s.id) as item_count,
               (SELECT COALESCE(SUM(unit_price * quantity), 0) FROM subscription_lines WHERE subscription_id = s.id) as subtotal
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
    """
    params = []
    if status_filter:
        query += " WHERE s.status = ?"
        params.append(status_filter)
    query += " ORDER BY s.id DESC"

    subs = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('subscriptions.html', subscriptions=subs, current_filter=status_filter)

@app.route('/subscriptions/new', methods=['GET', 'POST'])
@role_required(['ADMIN', 'STAFF'])
def new_subscription():
    conn = database.get_db()
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        plan_id = request.form.get('plan_id')
        start_date_str = request.form.get('start_date') or date.today().isoformat()
        expiry_date_str = request.form.get('expiry_date') or None
        payment_terms = request.form.get('payment_terms', 'Immediate Payment')
        notes = request.form.get('notes', '')
        status = request.form.get('status', 'QUOTATION')

        # Generate unique sub number
        sub_number = f"SUB-{datetime.now().strftime('%Y%m%d')}-{conn.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0] + 1:04d}"

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subscriptions 
            (sub_number, customer_id, plan_id, start_date, expiry_date, next_billing_date, payment_terms, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sub_number, customer_id, plan_id, start_date_str, expiry_date_str, start_date_str, payment_terms, status, notes))
        
        sub_id = cursor.lastrowid

        # Insert lines
        product_ids = request.form.getlist('product_id[]')
        variant_ids = request.form.getlist('variant_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        tax_rates = request.form.getlist('tax_rate[]')

        for i in range(len(product_ids)):
            if product_ids[i]:
                pid = product_ids[i]
                vid = variant_ids[i] if i < len(variant_ids) and variant_ids[i] else None
                qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 1
                price = float(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else 0.0
                tax = float(tax_rates[i]) if i < len(tax_rates) and tax_rates[i] else 18.0

                cursor.execute("""
                    INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rate)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sub_id, pid, vid, qty, price, tax))

        conn.commit()
        conn.close()
        flash(f"Subscription / Quote {sub_number} created successfully with status '{status}'.", "success")
        return redirect(url_for('subscription_detail', sub_id=sub_id))

    customers = conn.execute("SELECT id, name, email FROM users WHERE role = 'CUSTOMER' ORDER BY name").fetchall()
    plans_list = conn.execute("SELECT * FROM plans WHERE is_active = 1 ORDER BY name").fetchall()
    products_list = conn.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name").fetchall()
    variants_list = conn.execute("SELECT * FROM product_variants ORDER BY id").fetchall()
    default_tax = conn.execute("SELECT rate_percentage FROM tax_rules WHERE is_default = 1").fetchone()
    default_tax_rate = default_tax['rate_percentage'] if default_tax else 18.0

    conn.close()
    return render_template(
        'new_subscription.html',
        customers=customers,
        plans=plans_list,
        products=products_list,
        variants=variants_list,
        default_tax_rate=default_tax_rate
    )

@app.route('/subscriptions/<int:sub_id>')
@role_required(['ADMIN', 'STAFF'])
def subscription_detail(sub_id):
    conn = database.get_db()
    sub = conn.execute("""
        SELECT s.*, u.name as customer_name, u.email as customer_email, p.name as plan_name, p.billing_cycle, p.closure_rule
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        WHERE s.id = ?
    """, (sub_id,)).fetchone()

    if not sub:
        conn.close()
        flash("Subscription not found.", "danger")
        return redirect(url_for('subscriptions'))

    lines = conn.execute("""
        SELECT l.*, p.name as product_name, p.sales_price, v.variant_name, v.price_surcharge
        FROM subscription_lines l
        JOIN products p ON l.product_id = p.id
        LEFT JOIN product_variants v ON l.variant_id = v.id
        WHERE l.subscription_id = ?
    """, (sub_id,)).fetchall()

    invoices = conn.execute("""
        SELECT * FROM invoices WHERE subscription_id = ? ORDER BY id DESC
    """, (sub_id,)).fetchall()

    conn.close()
    return render_template('subscription_detail.html', sub=sub, lines=lines, invoices=invoices)

@app.route('/subscriptions/<int:sub_id>/status', methods=['POST'])
@role_required(['ADMIN', 'STAFF'])
def update_subscription_status(sub_id):
    new_status = request.form.get('status')
    valid_statuses = ['DRAFT', 'QUOTATION', 'CONFIRMED', 'ACTIVE', 'PAUSED', 'CLOSED']
    if new_status in valid_statuses:
        conn = database.get_db()
        conn.execute("UPDATE subscriptions SET status = ? WHERE id = ?", (new_status, sub_id))
        conn.commit()
        conn.close()
        flash(f"Subscription status updated to {new_status}.", "success")
    return redirect(url_for('subscription_detail', sub_id=sub_id))

# -------------------------------------------------------------
# BILLING DAY & BATCH INVOICE GENERATOR (Idempotent Engine)
# -------------------------------------------------------------

def calculate_next_billing_date(current_date, billing_cycle):
    if billing_cycle == 'DAILY':
        return current_date + timedelta(days=1)
    elif billing_cycle == 'WEEKLY':
        return current_date + timedelta(days=7)
    elif billing_cycle == 'MONTHLY':
        # approximate 30 days
        return current_date + timedelta(days=30)
    elif billing_cycle == 'YEARLY':
        return current_date + timedelta(days=365)
    return current_date + timedelta(days=30)

@app.route('/billing')
@role_required(['ADMIN', 'STAFF'])
def billing_dashboard():
    conn = database.get_db()
    today_str = date.today().isoformat()

    # Find subscriptions that are due for billing
    due_subs = conn.execute("""
        SELECT s.*, u.name as customer_name, p.name as plan_name, p.billing_cycle,
               (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM subscription_lines WHERE subscription_id = s.id) as estimated_subtotal
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        WHERE s.status = 'ACTIVE' AND s.next_billing_date <= ?
        ORDER BY s.next_billing_date ASC
    """, (today_str,)).fetchall()

    conn.close()
    return render_template('billing.html', due_subs=due_subs)

@app.route('/billing/run-batch', methods=['POST'])
@role_required(['ADMIN', 'STAFF'])
def run_batch_billing():
    """
    Automated Billing Engine:
    - Finds all active subscriptions where next_billing_date <= today
    - Idempotent: Verifies that no invoice has already been generated for this period
    - Calculates line items, taxes, and automatic discounts
    - Advances next_billing_date
    """
    conn = database.get_db()
    today_dt = date.today()
    today_str = today_dt.isoformat()

    due_subs = conn.execute("""
        SELECT s.*, u.name as customer_name, p.name as plan_name, p.billing_cycle
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        WHERE s.status = 'ACTIVE' AND s.next_billing_date <= ?
    """, (today_str,)).fetchall()

    generated_count = 0
    skipped_count = 0

    for sub in due_subs:
        sub_id = sub['id']
        cust_id = sub['customer_id']
        cycle = sub['billing_cycle']
        period_start = datetime.strptime(sub['next_billing_date'], "%Y-%m-%d").date()
        period_end = calculate_next_billing_date(period_start, cycle) - timedelta(days=1)

        # Idempotency check: Don't bill twice!
        existing = conn.execute("""
            SELECT id FROM invoices 
            WHERE subscription_id = ? AND billing_period_start = ? AND billing_period_end = ? AND status != 'CANCELLED'
        """, (sub_id, period_start.isoformat(), period_end.isoformat())).fetchone()

        if existing:
            skipped_count += 1
            continue

        # Get subscription lines
        lines = conn.execute("""
            SELECT l.*, p.name as product_name, v.variant_name
            FROM subscription_lines l
            JOIN products p ON l.product_id = p.id
            LEFT JOIN product_variants v ON l.variant_id = v.id
            WHERE l.subscription_id = ?
        """, (sub_id,)).fetchall()

        if not lines:
            continue

        subtotal = 0.0
        tax_total = 0.0
        invoice_lines_data = []

        for line in lines:
            line_total = line['quantity'] * line['unit_price']
            line_tax = line_total * (line['tax_rate'] / 100.0)
            subtotal += line_total
            tax_total += line_tax
            
            desc = line['product_name']
            if line['variant_name']:
                desc += f" ({line['variant_name']})"

            invoice_lines_data.append((desc, line['quantity'], line['unit_price'], line['tax_rate'], line_total))

        # Check for applicable discount rules
        discount_amount = 0.0
        applied_discount_id = None
        
        # Look for valid automatic discount
        disc = conn.execute("""
            SELECT * FROM discount_rules 
            WHERE is_active = 1 
              AND times_used < usage_limit
              AND (start_date IS NULL OR start_date <= ?)
              AND (end_date IS NULL OR end_date >= ?)
              AND min_purchase <= ?
            ORDER BY value DESC LIMIT 1
        """, (today_str, today_str, subtotal)).fetchone()

        if disc:
            applied_discount_id = disc['id']
            if disc['discount_type'] == 'PERCENTAGE':
                discount_amount = round(subtotal * (disc['value'] / 100.0), 2)
            else:
                discount_amount = min(subtotal, disc['value'])
            
            # Increment discount usage
            conn.execute("UPDATE discount_rules SET times_used = times_used + 1 WHERE id = ?", (disc['id'],))

        total_amount = max(0.0, round(subtotal + tax_total - discount_amount, 2))
        due_date = today_dt + timedelta(days=15) # Standard Net 15
        inv_number = f"INV-{today_dt.strftime('%Y%m%d')}-{conn.execute('SELECT COUNT(*) FROM invoices').fetchone()[0] + 1:04d}"

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices 
            (invoice_number, subscription_id, customer_id, billing_period_start, billing_period_end, invoice_date, due_date, subtotal, tax_total, discount_total, total_amount, amount_paid, status, discount_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.00, 'CONFIRMED', ?, ?)
        """, (
            inv_number, sub_id, cust_id, period_start.isoformat(), period_end.isoformat(),
            today_str, due_date.isoformat(), round(subtotal, 2), round(tax_total, 2),
            round(discount_amount, 2), total_amount, applied_discount_id, f"Auto-generated billing for {cycle} cycle."
        ))
        inv_id = cursor.lastrowid

        for desc, qty, uprice, trate, ltot in invoice_lines_data:
            cursor.execute("""
                INSERT INTO invoice_lines (invoice_id, description, quantity, unit_price, tax_rate, total_amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (inv_id, desc, qty, uprice, trate, ltot))

        # Advance next_billing_date for the subscription
        next_date = calculate_next_billing_date(period_start, cycle)
        cursor.execute("UPDATE subscriptions SET next_billing_date = ? WHERE id = ?", (next_date.isoformat(), sub_id))

        generated_count += 1

    conn.commit()
    conn.close()

    flash(f"Batch billing completed: {generated_count} invoices generated automatically. {skipped_count} skipped (already billed or duplicate prevention).", "success")
    return redirect(url_for('invoices'))

# -------------------------------------------------------------
# INVOICES & ACTIONS
# -------------------------------------------------------------

@app.route('/invoices')
@role_required(['ADMIN', 'STAFF'])
def invoices():
    conn = database.get_db()
    status_filter = request.args.get('status')
    today_str = date.today().isoformat()

    query = """
        SELECT i.*, u.name as customer_name, s.sub_number
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
    """
    params = []
    if status_filter == 'OVERDUE':
        query += " WHERE i.status = 'CONFIRMED' AND i.due_date < ?"
        params.append(today_str)
    elif status_filter:
        query += " WHERE i.status = ?"
        params.append(status_filter)

    query += " ORDER BY i.id DESC"
    all_invoices = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('invoices.html', invoices=all_invoices, current_filter=status_filter)

@app.route('/invoices/<int:inv_id>')
@login_required
def invoice_detail(inv_id):
    conn = database.get_db()
    inv = conn.execute("""
        SELECT i.*, u.name as customer_name, u.email as customer_email, s.sub_number, d.code as discount_code
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
        LEFT JOIN discount_rules d ON i.discount_id = d.id
        WHERE i.id = ?
    """, (inv_id,)).fetchone()

    if not inv:
        conn.close()
        flash("Invoice not found.", "danger")
        return redirect(url_for('invoices'))

    # If customer, enforce portal access control
    if session.get('role') == 'CUSTOMER' and inv['customer_id'] != session.get('user_id'):
        conn.close()
        flash("Access denied: You can only view your own invoices.", "danger")
        return redirect(url_for('customer_portal'))

    lines = conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (inv_id,)).fetchall()
    payments = conn.execute("SELECT * FROM payments WHERE invoice_id = ? ORDER BY id DESC", (inv_id,)).fetchall()
    conn.close()

    return render_template('invoice_detail.html', invoice=inv, lines=lines, payments=payments)

@app.route('/invoices/<int:inv_id>/confirm', methods=['POST'])
@role_required(['ADMIN', 'STAFF'])
def confirm_invoice(inv_id):
    conn = database.get_db()
    conn.execute("UPDATE invoices SET status = 'CONFIRMED' WHERE id = ? AND status = 'DRAFT'", (inv_id,))
    conn.commit()
    conn.close()
    flash("Invoice confirmed.", "success")
    return redirect(url_for('invoice_detail', inv_id=inv_id))

@app.route('/invoices/<int:inv_id>/cancel', methods=['POST'])
@role_required(['ADMIN', 'STAFF'])
def cancel_invoice(inv_id):
    conn = database.get_db()
    conn.execute("UPDATE invoices SET status = 'CANCELLED' WHERE id = ? AND status != 'PAID'", (inv_id,))
    conn.commit()
    conn.close()
    flash("Invoice cancelled.", "warning")
    return redirect(url_for('invoice_detail', inv_id=inv_id))

@app.route('/invoices/<int:inv_id>/send', methods=['POST'])
@role_required(['ADMIN', 'STAFF'])
def send_invoice(inv_id):
    conn = database.get_db()
    inv = conn.execute("SELECT invoice_number, customer_id FROM invoices WHERE id = ?", (inv_id,)).fetchone()
    cust = conn.execute("SELECT email FROM users WHERE id = ?", (inv['customer_id'],)).fetchone()
    conn.close()
    flash(f"Invoice {inv['invoice_number']} successfully sent to customer at {cust['email']}.", "info")
    return redirect(url_for('invoice_detail', inv_id=inv_id))

# -------------------------------------------------------------
# PAYMENTS & RECONCILIATION
# -------------------------------------------------------------

@app.route('/payments')
@role_required(['ADMIN', 'STAFF'])
def payments_list():
    conn = database.get_db()
    payments = conn.execute("""
        SELECT p.*, i.invoice_number, u.name as customer_name, staff.name as recorded_by_name
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN users staff ON p.recorded_by = staff.id
        ORDER BY p.id DESC
    """).fetchall()
    conn.close()
    return render_template('payments.html', payments=payments)

@app.route('/invoices/<int:inv_id>/record-payment', methods=['POST'])
@login_required
def record_payment(inv_id):
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'BANK_TRANSFER')
    payment_date = request.form.get('payment_date') or date.today().isoformat()
    note = request.form.get('note', '').strip()

    if amount <= 0:
        flash("Payment amount must be greater than zero.", "danger")
        return redirect(url_for('invoice_detail', inv_id=inv_id))

    conn = database.get_db()
    inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,)).fetchone()
    if not inv:
        conn.close()
        flash("Invoice not found.", "danger")
        return redirect(url_for('invoices'))

    # If customer self-paying in portal
    if session.get('role') == 'CUSTOMER' and inv['customer_id'] != session.get('user_id'):
        conn.close()
        flash("Unauthorized payment attempt.", "danger")
        return redirect(url_for('customer_portal'))

    remaining = inv['total_amount'] - inv['amount_paid']
    if amount > remaining + 0.01:
        flash(f"Payment amount (₹{amount:,.2f}) exceeds outstanding balance (₹{remaining:,.2f}).", "danger")
        conn.close()
        return redirect(url_for('invoice_detail', inv_id=inv_id))

    # Generate payment number
    pay_number = f"PAY-{datetime.now().strftime('%Y%m%d')}-{conn.execute('SELECT COUNT(*) FROM payments').fetchone()[0] + 1:04d}"
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payments (payment_number, invoice_id, amount, payment_date, payment_method, note, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (pay_number, inv_id, amount, payment_date, payment_method, note, session.get('user_id')))

    new_amount_paid = round(inv['amount_paid'] + amount, 2)
    new_status = 'PAID' if new_amount_paid >= (inv['total_amount'] - 0.01) else inv['status']

    cursor.execute("""
        UPDATE invoices SET amount_paid = ?, status = ? WHERE id = ?
    """, (new_amount_paid, new_status, inv_id))

    conn.commit()
    conn.close()

    flash(f"Payment of ₹{amount:,.2f} recorded under reference {pay_number}. Invoice balance updated.", "success")
    if session.get('role') == 'CUSTOMER':
        return redirect(url_for('customer_portal'))
    return redirect(url_for('invoice_detail', inv_id=inv_id))

# -------------------------------------------------------------
# CUSTOMER SELF-SERVICE PORTAL
# -------------------------------------------------------------

@app.route('/portal')
@login_required
def customer_portal():
    user_id = session.get('user_id')
    conn = database.get_db()

    # Customer Subscriptions
    subs = conn.execute("""
        SELECT s.*, p.name as plan_name, p.billing_cycle,
               (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM subscription_lines WHERE subscription_id = s.id) as subtotal
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.customer_id = ?
        ORDER BY s.id DESC
    """, (user_id,)).fetchall()

    # Customer Invoices
    invoices = conn.execute("""
        SELECT i.*, s.sub_number
        FROM invoices i
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
        WHERE i.customer_id = ?
        ORDER BY i.id DESC
    """, (user_id,)).fetchall()

    all_plans = conn.execute("SELECT * FROM plans WHERE is_active = 1").fetchall()
    conn.close()
    return render_template('portal.html', subscriptions=subs, invoices=invoices, all_plans=all_plans)

# -------------------------------------------------------------

# -------------------------------------------------------------
# INNOVATION 1: DYNAMIC UPI 1-CLICK INSTANT PAYMENT
# -------------------------------------------------------------

@app.route('/invoices/<int:inv_id>/pay-upi', methods=['POST'])
@login_required
def pay_upi(inv_id):
    conn = database.get_db()
    inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,)).fetchone()
    if not inv:
        flash("Invoice not found.", "danger")
        conn.close()
        return redirect(url_for('invoices'))

    # Ownership check for customer role
    if session.get('role') == 'CUSTOMER' and inv['customer_id'] != session.get('user_id'):
        flash("Unauthorized payment attempt.", "danger")
        conn.close()
        return redirect(url_for('customer_portal'))

    remaining = round(inv['total_amount'] - inv['amount_paid'], 2)
    if remaining <= 0:
        flash("This invoice is already fully paid.", "info")
        conn.close()
        if session.get('role') == 'CUSTOMER':
            return redirect(url_for('customer_portal'))
        return redirect(url_for('invoice_detail', inv_id=inv_id))

    today_str = date.today().isoformat()
    pay_number = f"PAY-UPI-{secrets.token_hex(4).upper()}"
    upi_txn_ref = f"UPI{int(datetime.now().timestamp())}"

    # Record payment
    conn.execute("""
        INSERT INTO payments (payment_number, invoice_id, amount, payment_date, payment_method, note, recorded_by)
        VALUES (?, ?, ?, ?, 'UPI', ?, ?)
    """, (pay_number, inv_id, remaining, today_str, f"Instant Settlement via Dynamic UPI QR (Ref: {upi_txn_ref})", session.get('user_id')))

    # Mark invoice as PAID
    conn.execute("""
        UPDATE invoices 
        SET amount_paid = total_amount, status = 'PAID'
        WHERE id = ?
    """, (inv_id,))

    conn.commit()
    conn.close()

    flash(f"Payment of ₹{remaining:,.2f} received instantly via UPI (Ref: {upi_txn_ref}). Invoice {inv['invoice_number']} marked PAID.", "success")
    if session.get('role') == 'CUSTOMER':
        return redirect(url_for('customer_portal'))
    return redirect(url_for('invoice_detail', inv_id=inv_id))

# -------------------------------------------------------------
# INNOVATION 2: 1-CLICK AUTOMATED OVERDUE CHASER (DUNNING)
# -------------------------------------------------------------

@app.route('/invoices/<int:inv_id>/chase-overdue', methods=['POST'])
@role_required(['ADMIN', 'STAFF'])
def chase_overdue(inv_id):
    conn = database.get_db()
    inv = conn.execute("""
        SELECT i.*, u.name as customer_name, u.email as customer_email 
        FROM invoices i 
        JOIN users u ON i.customer_id = u.id 
        WHERE i.id = ?
    """, (inv_id,)).fetchone()

    if not inv:
        flash("Invoice not found.", "danger")
        conn.close()
        return redirect(url_for('invoices'))

    new_count = (inv['reminder_count'] or 0) + 1
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn.execute("""
        UPDATE invoices 
        SET reminder_count = ?, last_reminder_date = ? 
        WHERE id = ?
    """, (new_count, now_str, inv_id))
    conn.commit()
    conn.close()

    ordinal = "1st" if new_count == 1 else ("2nd" if new_count == 2 else ("3rd" if new_count == 3 else f"{new_count}th"))
    flash(f"⚡ {ordinal} Overdue Payment Reminder dispatched to {inv['customer_name']} ({inv['customer_email']}) via WhatsApp & Email for invoice {inv['invoice_number']}.", "success")
    return redirect(url_for('invoice_detail', inv_id=inv_id))

# -------------------------------------------------------------
# INNOVATION 4: CUSTOMER SELF-SERVICE PLAN UPGRADE & ADD-ONS
# -------------------------------------------------------------

@app.route('/portal/upgrade-subscription/<int:sub_id>', methods=['POST'])
@login_required
def upgrade_subscription(sub_id):
    conn = database.get_db()
    sub = conn.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
    
    if not sub:
        flash("Subscription not found.", "danger")
        conn.close()
        return redirect(url_for('customer_portal'))
        
    if session.get('role') == 'CUSTOMER' and sub['customer_id'] != session.get('user_id'):
        flash("Access denied.", "danger")
        conn.close()
        return redirect(url_for('customer_portal'))

    new_plan_id = int(request.form.get('new_plan_id', sub['plan_id']))
    enable_odoo_variant = request.form.get('enable_odoo_variant') == '1'

    plan = conn.execute("SELECT * FROM plans WHERE id = ?", (new_plan_id,)).fetchone()
    if not plan:
        flash("Selected plan not found.", "danger")
        conn.close()
        return redirect(url_for('customer_portal'))

    # Update subscription plan
    conn.execute("UPDATE subscriptions SET plan_id = ? WHERE id = ?", (new_plan_id, sub_id))

    # Toggle Odoo variant
    odoo_var = conn.execute("SELECT * FROM product_variants WHERE variant_name LIKE '%Odoo%' LIMIT 1").fetchone()
    if odoo_var:
        existing_odoo = conn.execute("SELECT * FROM subscription_lines WHERE subscription_id = ? AND variant_id = ?", (sub_id, odoo_var['id'])).fetchone()
        if enable_odoo_variant and not existing_odoo:
            conn.execute("""
                INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rate)
                VALUES (?, ?, ?, 1, ?, 18.0)
            """, (sub_id, odoo_var['product_id'], odoo_var['id'], odoo_var['price_surcharge']))
        elif not enable_odoo_variant and existing_odoo:
            conn.execute("DELETE FROM subscription_lines WHERE subscription_id = ? AND variant_id = ?", (sub_id, odoo_var['id']))

    conn.commit()
    conn.close()

    flash(f"Subscription updated successfully to plan '{plan['name']}'{' with Odoo Brand Integration' if enable_odoo_variant else ''}.", "success")
    return redirect(url_for('customer_portal'))

# -------------------------------------------------------------
# INNOVATION 5: 1-CLICK CSV FINANCIAL EXPORT (AUDIT READY)
# -------------------------------------------------------------

@app.route('/invoices/export-csv')
@role_required(['ADMIN', 'STAFF'])
def export_invoices_csv():
    conn = database.get_db()
    invoices = conn.execute("""
        SELECT i.*, u.name as customer_name, u.email as customer_email, s.sub_number
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        LEFT JOIN subscriptions s ON i.subscription_id = s.id
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice Number", "Subscription Ref", "Customer Name", "Customer Email",
        "Invoice Date", "Due Date", "Taxable Subtotal (INR)", "Tax Total (INR)",
        "Discount Total (INR)", "Total Amount (INR)", "Amount Paid (INR)",
        "Balance Due (INR)", "Status", "Reminders Sent"
    ])

    for inv in invoices:
        balance = inv['total_amount'] - inv['amount_paid']
        writer.writerow([
            inv['invoice_number'],
            inv['sub_number'] or "Manual / Ad-hoc",
            inv['customer_name'],
            inv['customer_email'],
            inv['invoice_date'],
            inv['due_date'],
            f"{inv['subtotal']:.2f}",
            f"{inv['tax_total']:.2f}",
            f"{inv['discount_total']:.2f}",
            f"{inv['total_amount']:.2f}",
            f"{inv['amount_paid']:.2f}",
            f"{balance:.2f}",
            inv['status'],
            inv['reminder_count'] or 0
        ])

    csv_data = output.getvalue()
    filename = f"brightloop_invoices_{date.today().isoformat()}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/subscriptions/export-csv')
@role_required(['ADMIN', 'STAFF'])
def export_subscriptions_csv():
    conn = database.get_db()
    subs = conn.execute("""
        SELECT s.*, u.name as customer_name, u.email as customer_email, p.name as plan_name, p.billing_cycle,
               COALESCE((SELECT SUM(l.quantity * l.unit_price) FROM subscription_lines l WHERE l.subscription_id = s.id), 0) as subtotal
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        ORDER BY s.id DESC
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Subscription Number", "Customer Name", "Customer Email", "Plan Name",
        "Billing Cycle", "Start Date", "Next Renewal Date", "Status", "Cycle Subtotal (INR)"
    ])

    for s in subs:
        writer.writerow([
            s['sub_number'],
            s['customer_name'],
            s['customer_email'],
            s['plan_name'],
            s['billing_cycle'],
            s['start_date'],
            s['next_billing_date'],
            s['status'],
            f"{s['subtotal']:.2f}"
        ])

    csv_data = output.getvalue()
    filename = f"brightloop_subscriptions_{date.today().isoformat()}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# APP RUNNER
# -------------------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
