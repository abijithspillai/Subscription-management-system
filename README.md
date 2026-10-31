# Brightloop Subscription Management System
> **Odoo Cross Makeathon 9.0 — CUSAT Official Hackathon Submission**  
> *The unified digital backbone for plans, recurring billing, smart discounts, and cash flow reconciliation.*

---

## 1. Problem Statement & Real-World Context

Brightloop Software sells recurring software subscriptions, add-on modules, and variant-priced bundles (e.g., standard editions vs. Odoo Brand Integrations). As the business expanded, operational bottlenecks crippled growth:

- **Spreadsheet Paralysis:** Customer subscriptions were tracked across disorganized spreadsheets.
- **Missed Renewals & Revenue Leakage:** Contract expirations and renewal cycles were forgotten.
- **Manual Invoicing Errors:** Invoices were hand-typed every month, leading to missed billing cycles or duplicate charges.
- **Payment Matching Friction:** Accounting teams scrolled through bank statements matching bank transfers manually.
- **Blind Leadership:** The finance lead could not answer basic questions: *How many subscriptions are active? What is our real-time MRR? Which invoices are overdue?*

---

## 2. The Innovative Solution: Brightloop Unified Engine

Brightloop Subscription Management System solves these problems with an integrated, local-first web application designed for high reliability, zero cloud dependency, and sub-2-second query performance.

### Key Functional Pillars:

1. **Product Catalog & Variant Engine:**
   - Products with Sales Price, Cost Price, and Margin tracking.
   - Dynamic variant surcharge modeling (e.g. *Odoo Brand Integration adds $560.00*).

2. **Flexible Billing Plans:**
   - Cadences: `DAILY`, `WEEKLY`, `MONTHLY`, and `YEARLY`.
   - Minimum seat/quantity rules and lifecycle policies (`AUTO_CLOSE` vs `CAN_RENEW_PAUSE`).

3. **Sales Quotation Pipeline:**
   - Reusable Quotation Templates with pre-configured product lines.
   - Lifecycle state machine: `Draft` ➔ `Quotation` ➔ `Confirmed` ➔ `Active` ➔ `Closed`.

4. **Automated "Billing Day" Engine (Idempotent):**
   - 1-click batch generation of invoices for all due subscriptions.
   - Enforces unique index `(subscription_id, billing_period)` to **strictly prevent double-billing**.
   - Automatic tax assessment based on admin-defined tax rules.

5. **Smart Discount Engine:**
   - Admin-only discount rules: percentage or fixed amount discounts.
   - Minimum spend or seat count triggers, start/end dates, and maximum usage counters.
   - Automatically evaluated and applied to upcoming recurring invoices.

6. **Payment Reconciliation & Overdue Tracker:**
   - Multi-method payment recording (`BANK_TRANSFER`, `CREDIT_CARD`, `UPI`, `CASH`, `CHEQUE`).
   - Real-time invoice status transitions (`Draft` ➔ `Confirmed` ➔ `Paid`).
   - Instant filtering for overdue receivables to chase outstanding cash flow.

7. **Role-Based Access Control (RBAC):**
   - **Admin:** Complete system authority, staff management, tax & discount rules.
   - **Internal Staff:** Day-to-day sales, quotes, billing day, and payment logs.
   - **Customer Portal:** Dedicated self-service portal to view only their own contracts and invoices.
   - Strict password policy (`>8 characters, uppercase, lowercase, special character`).

8. **Executive Finance Cockpit:**
   - Real-time metrics: Active Subscriptions, Normalized MRR, ARR, Total Revenue Collected, and Overdue Receivables.
   - Direct indexed SQL aggregation with sub-2-second response guarantee.

---

## 3. Technology Stack

- **Backend:** Python (Flask 3.0+)
- **Database:** SQLite3 (Local, ACID-compliant, zero cloud dependency, foreign keys enforced)
- **Frontend:** Tailwind CSS (Responsive mobile/tablet/desktop) + Vanilla JavaScript
- **Security:** Password hashing (`werkzeug.security`), parametric SQL queries, RBAC session guards
- **Export & Print:** High-fidelity print stylesheet for browser-native PDF invoice generation

---

## 4. Local Installation & Setup Guide

### Prerequisites
- Python 3.10+ installed (`python --version` or `py --version`)

### Step 1: Navigate to Project Directory
```bash
cd C:\Users\hp\.gemini\antigravity\scratch\brightloop-subscriptions
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run the Application
```bash
python app.py
```
*Note: On startup, `database.py` automatically initializes `brightloop.db` and populates realistic demo seed data covering all 7 problem scenes.*

### Step 4: Open in Browser
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---


---

## 5. Hackathon Innovation Features (Beyond Requirements)

In addition to the mandatory problem statement specifications, this platform includes 5 production-grade business innovations:

1. **⚡ Dynamic UPI QR Code & 1-Click Instant Payment:** Real-time scannable UPI QR code (conforming to NPCI standard) generated on customer invoices with 1-click simulated instant settlement.
2. **📢 1-Click Automated Overdue Chaser (Dunning System):** Built-in reminder escalation engine simulating WhatsApp & Email dunning notices directly addressing lost revenue prevention.
3. **📊 Executive Financial Cockpit (ARR, Churn %, Collection Rate):** Deep SaaS financial metrics including Annual Run-Rate (ARR = MRR × 12), Collection Efficiency %, and Odoo Brand Surcharge Margin.
4. **🔄 Customer Self-Service Plan Upgrades & Add-Ons:** Allows customers to self-upgrade cadence (Monthly ➔ Yearly) and toggle Odoo Brand integration directly from their portal without emailing support.
5. **📥 1-Click CSV Financial Exports:** Export audit-ready datasets of Invoices and Subscriptions for Tally, Zoho Books, or Odoo Accounting.

## 6. Demo Test Credentials (Ready for Evaluators)

| Role | Email | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **👑 Admin Director** | `admin@brightloop.com` | `Admin@Brightloop1` | Full administrative access, staff creation, discount rules, finance cockpit |
| **💼 Internal Staff** | `sarah.staff@brightloop.com` | `Staff@Brightloop1` | Operational execution: quotes, billing run, invoice actions, payments |
| **🏪 Customer** | `billing@apexretail.in` | `Customer@Brightloop1` | Self-service portal: view own subscriptions, print invoices, pay online |

*Tip: The Sign In page features 1-click demo credential autofill buttons for convenience.*

---

## 7. Demonstration & Evaluation Walkthrough

Follow this 5-minute walkthrough during your presentation:

1. **Sign In as Admin:** Inspect the **Executive Finance Cockpit** showing real-time MRR, ARR, active contracts, and overdue receivables.
2. **Review Products & Variants:** Go to **Catalog & Rules ➔ Products & Variants**. Notice the *Brightloop Business ERP* product with the *Odoo Brand Integration* variant (+ ₹560.00 surcharge).
3. **Inspect Quotation to Subscription:** Go to **Subscriptions**. Open `SUB-2026-0003` to show the lifecycle stepper (`Draft` ➔ `Quotation` ➔ `Confirmed` ➔ `Active`).
4. **Execute Billing Day:** Go to **Billing Day**. Notice the subscriptions due for renewal today. Click **"Run Batch Billing Now"**. Verify that invoices are automatically generated and no duplicate charges occur.
5. **Inspect & Print Invoice:** Open any generated invoice. Demonstrate the automated tax calculation, applied discount deduction, and click **"Print Invoice"** to show the professional PDF invoice layout.
6. **Record Payment & Reconciliation:** Record a partial or full payment on an invoice (e.g., via Bank Transfer or UPI). Watch the invoice balance update instantly to `Paid`.
7. **Switch to Customer Portal:** Log out and log in as `billing@apexretail.in`. Demonstrate that the customer sees **only** their own contracts and invoices, with self-service payment options.
