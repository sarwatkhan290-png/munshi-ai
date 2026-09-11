import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
from services.ai_service import parse_transaction
from services.auth_service import (
    prepare_session_for_user,
    reset_session_for_logout,
    hash_password,
    authenticate_user,
    create_tenant_user,
)
from services.transaction_service import (
    add_sale,
    add_payment,
    add_expense,
    get_customer_ledger,
    get_customer,
    MissingTenantError,
)
from services.analytics_service import (
    get_dashboard_summary,
    get_customer_balances,
)


class ProjectStructureTests(unittest.TestCase):
    def test_database_path_is_project_root_relative(self):
        expected_dir = PROJECT_ROOT / "data"
        self.assertEqual(database.DATABASE_PATH.parent, expected_dir)

    def test_database_has_shop_tables(self):
        connection = database.get_connection()
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {table[0] for table in tables}
        self.assertIn("shops", names)
        self.assertIn("shop_users", names)
        self.assertIn("users", names)
        connection.close()


class TransactionParsingTests(unittest.TestCase):
    def test_parse_transaction_handles_common_sale_statement(self):
        result = parse_transaction("Ali ne 25 hazar ka maal liya aur 10 hazar diye")
        self.assertEqual(result["type"], "sale")
        self.assertEqual(result["customer"], "Ali")
        self.assertEqual(result["amount"], 25000.0)
        self.assertEqual(result["paid"], 10000.0)

    def test_parse_transaction_handles_payment_statement(self):
        result = parse_transaction("Ahmed 5000 jama diye")
        self.assertEqual(result["type"], "payment")
        self.assertEqual(result["customer"], "Ahmed")
        self.assertEqual(result["amount"], 5000.0)


class SessionHelperTests(unittest.TestCase):
    def test_prepare_session_for_user_resets_dashboard_state(self):
        session = {"user": {"id": 7}, "tenant": {"id": 3}, "active_page": "Analytics", "nav_target": "📊 Reports", "app_mode": "auth"}

        updated = prepare_session_for_user(session)

        self.assertEqual(updated["active_page"], "🏠 Dashboard")
        self.assertIsNone(updated["nav_target"])
        self.assertEqual(updated["app_mode"], "dashboard")

    def test_reset_session_for_logout_clears_user_and_mode(self):
        session = {"user": {"id": 2}, "tenant": {"id": 9}, "active_page": "💰 Transactions", "nav_target": "Team", "app_mode": "dashboard"}

        updated = reset_session_for_logout(session)

        self.assertIsNone(updated["user"])
        self.assertIsNone(updated["tenant"])
        self.assertEqual(updated["active_page"], "🏠 Dashboard")
        self.assertIsNone(updated["nav_target"])
        self.assertEqual(updated["app_mode"], "auth")


class AuthServiceTests(unittest.TestCase):
    """Auth tests run against a throwaway temp database so they never touch
    real data or depend on a pre-existing 'owner@example.com' account."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self._tmpdir.name) / "test_auth.db"
        database.initialize_database()

    def tearDown(self):
        database.DATABASE_PATH = self._original_path
        self._tmpdir.cleanup()

    def test_hash_password_does_not_store_plaintext(self):
        hashed = hash_password("demo123")
        self.assertTrue(hashed)
        self.assertNotEqual(hashed, "demo123")

    def test_authenticate_user_rejects_unknown_email(self):
        result = authenticate_user("nobody@example.com", "whatever")
        self.assertFalse(result["success"])

    def test_authenticate_user_accepts_correct_password_and_rejects_wrong_one(self):
        signup = create_tenant_user(
            name="Demo Owner",
            email="owner@example.com",
            password="demo123",
            tenant_name="Demo Shop",
        )
        self.assertTrue(signup["success"])

        good = authenticate_user("owner@example.com", "demo123")
        self.assertTrue(good["success"])
        self.assertEqual(good["user"]["email"], "owner@example.com")

        bad = authenticate_user("owner@example.com", "wrong-password")
        self.assertFalse(bad["success"])


class TenantIsolationTests(unittest.TestCase):
    """
    Regression tests for the cross-tenant data leak: every service function
    that touches customers/transactions/expenses must be scoped by
    tenant_id, so two shops never see or affect each other's ledgers.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self._tmpdir.name) / "test_tenants.db"
        database.initialize_database()

        shop_a = create_tenant_user(
            name="Owner A", email="a@shopa.com", password="pw12345", tenant_name="Shop A"
        )
        shop_b = create_tenant_user(
            name="Owner B", email="b@shopb.com", password="pw12345", tenant_name="Shop B"
        )
        self.tenant_a = shop_a["user"]["tenant_id"]
        self.tenant_b = shop_b["user"]["tenant_id"]
        self.assertNotEqual(self.tenant_a, self.tenant_b)

    def tearDown(self):
        database.DATABASE_PATH = self._original_path
        self._tmpdir.cleanup()

    def test_add_sale_computes_due_and_persists_amounts(self):
        result = add_sale(self.tenant_a, "Ali", amount=5000, paid=2000, description="Test sale")
        self.assertTrue(result["transaction_id"])
        self.assertEqual(result["amount"], 5000.0)
        self.assertEqual(result["paid"], 2000.0)
        self.assertEqual(result["due"], 3000.0)

    def test_add_payment_reduces_nothing_for_unknown_customer(self):
        result = add_payment(self.tenant_a, "Nobody", 1000)
        self.assertIsNone(result)

    def test_same_customer_name_does_not_collide_across_tenants(self):
        add_sale(self.tenant_a, "Ali", amount=5000, paid=0)
        add_sale(self.tenant_b, "Ali", amount=9000, paid=9000)

        ledger_a = get_customer_ledger(self.tenant_a, "Ali")
        ledger_b = get_customer_ledger(self.tenant_b, "Ali")

        self.assertEqual(len(ledger_a), 1)
        self.assertEqual(len(ledger_b), 1)
        self.assertEqual(ledger_a[0][3], 5000.0)  # amount column
        self.assertEqual(ledger_b[0][3], 9000.0)

    def test_get_customer_does_not_leak_across_tenants(self):
        add_sale(self.tenant_a, "Sana", amount=1000, paid=0)
        self.assertIsNotNone(get_customer(self.tenant_a, "Sana"))
        self.assertIsNone(get_customer(self.tenant_b, "Sana"))

    def test_dashboard_summary_only_reflects_own_tenant(self):
        add_sale(self.tenant_a, "Bilal", amount=10000, paid=4000)
        add_expense(self.tenant_a, "Rent", 2000)

        add_sale(self.tenant_b, "Bilal", amount=99999, paid=0)
        add_expense(self.tenant_b, "Rent", 50000)

        summary_a = get_dashboard_summary(self.tenant_a)
        self.assertEqual(summary_a["sales"], 10000.0)
        self.assertEqual(summary_a["expenses"], 2000.0)

        summary_b = get_dashboard_summary(self.tenant_b)
        self.assertEqual(summary_b["sales"], 99999.0)
        self.assertEqual(summary_b["expenses"], 50000.0)

    def test_customer_balances_scoped_per_tenant(self):
        add_sale(self.tenant_a, "Zara", amount=3000, paid=1000)
        balances_a = get_customer_balances(self.tenant_a)
        balances_b = get_customer_balances(self.tenant_b)

        names_a = {row[1] for row in balances_a}
        names_b = {row[1] for row in balances_b}

        self.assertIn("Zara", names_a)
        self.assertNotIn("Zara", names_b)

    def test_missing_tenant_id_raises_instead_of_defaulting(self):
        with self.assertRaises(MissingTenantError):
            add_sale(None, "Ali", amount=1000, paid=0)


if __name__ == "__main__":
    unittest.main()
