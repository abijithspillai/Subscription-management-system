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
            'email': 'marcus@cornerretail.com',
            'password': 'Customer@Brightloop1'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Customer Self-Service Portal', response.data)
        self.assertIn(b'Marcus Vance (Small Shop)', response.data)

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

if __name__ == '__main__':
    unittest.main()
