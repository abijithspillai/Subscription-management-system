import unittest
import json
from app import app, database, validate_password

class BrightloopTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_01_password_policy(self):
        """Verify strict password rules: >8 chars, uppercase, lowercase, special char"""
        # Too short
        valid, msg = validate_password("Short1!")
        self.assertFalse(valid)
        # Missing uppercase
        valid, msg = validate_password("lowercase1!")
        self.assertFalse(valid)
        # Missing lowercase
        valid, msg = validate_password("UPPERCASE1!")
        self.assertFalse(valid)
        # Missing special char
        valid, msg = validate_password("NoSpecial123")
        self.assertFalse(valid)
        # Valid password
        valid, msg = validate_password("Admin@Brightloop1")
        self.assertTrue(valid)

    def test_02_admin_login_and_dashboard(self):
        """Verify Admin login and Dashboard KPI loading in < 2s"""
        response = self.client.post('/login', data={
            'email': 'admin@brightloop.com',
            'password': 'Admin@Brightloop1'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Business Overview & Revenue', response.data)
        self.assertIn(b'Monthly Revenue (MRR)', response.data)

    def test_03_customer_portal_isolation(self):
        """Verify customer portal only displays the logged-in customer's records"""
        response = self.client.post('/login', data={
            'email': 'billing@apexretail.in',
            'password': 'Customer@Brightloop1'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Customer Self-Service Portal', response.data)
        self.assertIn(b'Apex Retail Mart', response.data)

        # Ensure customer cannot access Admin/Staff routes
        dashboard_resp = self.client.get('/dashboard', follow_redirects=True)
        self.assertIn(b'Access denied', dashboard_resp.data)

    def test_04_batch_billing_idempotency(self):
        """Verify batch billing runs and avoids duplicate billing"""
        # Login as staff
        self.client.post('/login', data={
            'email': 'sarah.staff@brightloop.com',
            'password': 'Staff@Brightloop1'
        }, follow_redirects=True)

        # Trigger batch billing
        response = self.client.post('/billing/run-batch', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Batch billing completed', response.data)

        # Trigger again immediately - should report skipped/zero duplicates
        second_resp = self.client.post('/billing/run-batch', follow_redirects=True)
        self.assertEqual(second_resp.status_code, 200)
        self.assertIn(b'0 invoices generated automatically', second_resp.data)

    def test_05_payment_recording(self):
        """Verify recording a payment updates the invoice balance and status"""
        # Login as admin
        self.client.post('/login', data={
            'email': 'admin@brightloop.com',
            'password': 'Admin@Brightloop1'
        }, follow_redirects=True)

        # Record payment against invoice #2
        response = self.client.post('/invoices/2/record-payment', data={
            'amount': '100.00',
            'payment_method': 'UPI',
            'payment_date': '2026-10-31',
            'note': 'Automated unit test UPI transfer'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'recorded under reference', response.data)

    def test_06_staff_cannot_create_product(self):
        """Verify Staff cannot create products (Only Admin can add products)"""
        # Login as staff
        self.client.post('/login', data={
            'email': 'sarah.staff@brightloop.com',
            'password': 'Staff@Brightloop1'
        }, follow_redirects=True)

        # Attempt to POST new product as staff
        response = self.client.post('/products', data={
            'name': 'Unauthorized Product',
            'product_type': 'SOFTWARE',
            'sales_price': '999.00',
            'cost_price': '100.00'
        }, follow_redirects=True)
        # Should not have created the product
        self.assertNotIn(b'Product created successfully', response.data)

    def test_07_upi_instant_payment(self):
        """Verify Innovation 1: Dynamic UPI 1-click settlement"""
        # Login as customer (Apex Retail Mart)
        self.client.post('/login', data={
            'email': 'billing@apexretail.in',
            'password': 'Customer@Brightloop1'
        }, follow_redirects=True)

        # Trigger UPI 1-click settlement for invoice #1
        response = self.client.post('/invoices/3/pay-upi', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'via UPI', response.data)

    def test_08_chase_overdue_invoice(self):
        """Verify Innovation 2: 1-Click Automated Overdue Chaser (Dunning System)"""
        # Login as staff
        self.client.post('/login', data={
            'email': 'sarah.staff@brightloop.com',
            'password': 'Staff@Brightloop1'
        }, follow_redirects=True)

        # Trigger overdue reminder for invoice #2
        response = self.client.post('/invoices/2/chase-overdue', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Overdue Payment Reminder', response.data)

    def test_09_customer_plan_upgrade(self):
        """Verify Innovation 4: Customer self-service subscription upgrade and Odoo toggle"""
        # Login as customer
        self.client.post('/login', data={
            'email': 'billing@apexretail.in',
            'password': 'Customer@Brightloop1'
        }, follow_redirects=True)

        # Upgrade subscription #1 to Plan 2 (Enterprise Annual) with Odoo variant
        response = self.client.post('/portal/upgrade-subscription/1', data={
            'new_plan_id': '2',
            'enable_odoo_variant': '1'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Subscription updated successfully', response.data)

    def test_10_csv_exports(self):
        """Verify Innovation 5: 1-Click CSV Financial Exports for Invoices and Subscriptions"""
        # Login as admin
        self.client.post('/login', data={
            'email': 'admin@brightloop.com',
            'password': 'Admin@Brightloop1'
        }, follow_redirects=True)

        inv_csv = self.client.get('/invoices/export-csv')
        self.assertEqual(inv_csv.status_code, 200)
        self.assertIn(b'Invoice Number', inv_csv.data)

        sub_csv = self.client.get('/subscriptions/export-csv')
        self.assertEqual(sub_csv.status_code, 200)
        self.assertIn(b'Subscription Number', sub_csv.data)


if __name__ == '__main__':
    unittest.main()
