"""
Tests for the finance app.

We focus on the critical paths the assignment calls out: transaction CRUD and
validation edge cases, the category-deletion rule, budget tracking + overrun
notifications, decimal precision, multi-currency aggregation, and the report.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

import io

from .models import Budget, Category, Currency, Transaction
from . import insights as insights_mod
from . import selectors
from .imports import import_csv
from .notifications import check_budget_overruns

User = get_user_model()


class BaseFinanceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", "pw12345!")
        self.other = User.objects.create_user("bob", "bob@example.com", "pw12345!")
        self.usd = Currency.objects.get(code="USD")
        self.eur = Currency.objects.get(code="EUR")
        self.salary = Category.objects.create(user=self.user, name="Salary", type="income")
        self.food = Category.objects.create(user=self.user, name="Food", type="expense")


class TransactionModelTests(BaseFinanceTest):
    def test_zero_amount_rejected(self):
        txn = Transaction(
            user=self.user, type="expense", category=self.food,
            amount=Decimal("0.00"), currency=self.usd, date=date.today(),
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_negative_amount_allowed_as_refund(self):
        # A refund inside an expense category is a negative expense.
        txn = Transaction(
            user=self.user, type="expense", category=self.food,
            amount=Decimal("-15.50"), currency=self.usd, date=date.today(),
        )
        txn.full_clean()  # should not raise
        txn.save()
        self.assertEqual(Transaction.objects.count(), 1)

    def test_category_type_must_match(self):
        txn = Transaction(
            user=self.user, type="income", category=self.food,  # food is expense
            amount=Decimal("10"), currency=self.usd, date=date.today(),
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_decimal_precision_preserved(self):
        txn = Transaction.objects.create(
            user=self.user, type="expense", category=self.food,
            amount=Decimal("12.34"), currency=self.usd, date=date.today(),
        )
        txn.refresh_from_db()
        self.assertEqual(txn.amount, Decimal("12.34"))


class CategoryDeletionTests(BaseFinanceTest):
    def test_deleting_category_keeps_transactions(self):
        txn = Transaction.objects.create(
            user=self.user, type="expense", category=self.food,
            amount=Decimal("20"), currency=self.usd, date=date.today(),
        )
        self.food.delete()
        txn.refresh_from_db()
        self.assertIsNone(txn.category)  # SET_NULL, transaction survives
        self.assertEqual(Transaction.objects.count(), 1)


class SelectorTests(BaseFinanceTest):
    def setUp(self):
        super().setUp()
        Transaction.objects.create(user=self.user, type="income", category=self.salary,
                                   amount=Decimal("1000"), currency=self.usd, date=date(2026, 6, 1))
        Transaction.objects.create(user=self.user, type="expense", category=self.food,
                                   amount=Decimal("250.50"), currency=self.usd, date=date(2026, 6, 5))
        Transaction.objects.create(user=self.user, type="expense", category=self.food,
                                   amount=Decimal("-50"), currency=self.usd, date=date(2026, 6, 8))  # refund
        # A EUR transaction must NOT be summed with USD.
        Transaction.objects.create(user=self.user, type="income", category=self.salary,
                                   amount=Decimal("500"), currency=self.eur, date=date(2026, 6, 3))

    def test_totals_grouped_by_currency(self):
        totals = {r["code"]: r for r in selectors.totals_by_currency(self.user)}
        self.assertEqual(totals["USD"]["income"], Decimal("1000.00"))
        # 250.50 expense minus 50 refund = 200.50
        self.assertEqual(totals["USD"]["expense"], Decimal("200.50"))
        self.assertEqual(totals["USD"]["net"], Decimal("799.50"))
        self.assertEqual(totals["EUR"]["income"], Decimal("500.00"))
        self.assertEqual(totals["EUR"]["expense"], Decimal("0.00"))

    def test_monthly_series_has_net(self):
        series = selectors.monthly_series(self.user, 2026)
        june = series[5]  # index 5 == month 6
        self.assertEqual(june["month"], 6)
        self.assertEqual(june["net"], june["income"] - june["expense"])


class BudgetTests(BaseFinanceTest):
    def test_budget_progress_and_overrun_email(self):
        budget = Budget.objects.create(
            user=self.user, category=self.food, currency=self.usd,
            month=date(2026, 6, 15), amount=Decimal("100.00"),
        )
        self.assertEqual(budget.month, date(2026, 6, 1))  # normalised to 1st

        Transaction.objects.create(user=self.user, type="expense", category=self.food,
                                   amount=Decimal("120"), currency=self.usd, date=date(2026, 6, 10))

        progress = selectors.budget_progress(self.user, month=date(2026, 6, 1))
        self.assertEqual(progress[0]["spent"], Decimal("120.00"))
        self.assertTrue(progress[0]["over"])

        # Overrun notification emails the user exactly once.
        check_budget_overruns(self.user, date(2026, 6, 10))
        self.assertEqual(len(mail.outbox), 1)
        check_budget_overruns(self.user, date(2026, 6, 10))
        self.assertEqual(len(mail.outbox), 1)  # not sent again


class ViewTests(BaseFinanceTest):
    def test_login_required(self):
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)  # redirect to login

    def test_dashboard_loads_when_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_create_transaction_via_view(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("transaction_create"), {
            "type": "expense", "category": self.food.id, "amount": "42.00",
            "currency": self.usd.id, "date": "2026-06-01", "description": "Lunch",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 1)

    def test_user_cannot_edit_others_transaction(self):
        txn = Transaction.objects.create(
            user=self.other, type="expense", amount=Decimal("5"),
            currency=self.usd, date=date.today(),
        )
        self.client.force_login(self.user)
        resp = self.client.get(reverse("transaction_edit", args=[txn.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_report_csv_export(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("report"), {"year": 2026, "format": "csv"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")


class ApiTests(BaseFinanceTest):
    def test_transaction_api_scoped_to_user(self):
        Transaction.objects.create(user=self.other, type="expense", amount=Decimal("9"),
                                   currency=self.usd, date=date.today())
        self.client.force_login(self.user)
        resp = self.client.get("/api/transactions/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)  # cannot see bob's txn

    def test_api_rejects_zero_amount(self):
        self.client.force_login(self.user)
        resp = self.client.post("/api/transactions/", {
            "type": "expense", "amount": "0", "currency": self.usd.id,
            "date": "2026-06-01",
        })
        self.assertEqual(resp.status_code, 400)


class PartBTests(BaseFinanceTest):
    def test_anomaly_detection_flags_outlier(self):
        # Four normal ~10 expenses then one big 500 -> outlier.
        for _ in range(4):
            Transaction.objects.create(user=self.user, type="expense", category=self.food,
                                       amount=Decimal("10"), currency=self.usd, date=date(2026, 6, 1))
        Transaction.objects.create(user=self.user, type="expense", category=self.food,
                                   amount=Decimal("500"), currency=self.usd, date=date(2026, 6, 2))
        anomalies = insights_mod.detect_anomalies(self.user)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["amount"], Decimal("500"))

    def test_rule_based_insights_when_no_key(self):
        Transaction.objects.create(user=self.user, type="income", category=self.salary,
                                   amount=Decimal("1000"), currency=self.usd, date=date.today())
        with patch("django.conf.settings.ANTHROPIC_API_KEY", ""):
            result = insights_mod.financial_insights(self.user)
        self.assertEqual(result["source"], "rule-based")
        self.assertIn("USD", result["text"])

    def test_csv_import_categorises_and_dedupes(self):
        csv_text = (
            "date,description,amount\n"
            "2026-06-01,Uber ride home,-25.00\n"
            "2026-06-02,Monthly salary payroll,3000.00\n"
            "2026-06-01,Uber ride home,-25.00\n"  # duplicate within file
        )
        stats = import_csv(self.user, io.BytesIO(csv_text.encode()), self.usd)
        self.assertEqual(stats["imported"], 2)
        self.assertEqual(stats["duplicates"], 1)
        # Auto-categorisation created/used Transport (expense) and Salary (income).
        self.assertTrue(Category.objects.filter(user=self.user, name="Transport").exists())
        uber = Transaction.objects.get(description="Uber ride home")
        self.assertEqual(uber.type, "expense")
        self.assertEqual(uber.amount, Decimal("25.00"))

        # Re-importing the same file: all 3 rows are now duplicates (2 against
        # the DB + the 3rd against the others within the file).
        stats2 = import_csv(self.user, io.BytesIO(csv_text.encode()), self.usd)
        self.assertEqual(stats2["imported"], 0)
        self.assertEqual(stats2["duplicates"], 3)

    def test_insights_and_import_pages_load(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("insights")).status_code, 200)
        self.assertEqual(self.client.get(reverse("import_statement")).status_code, 200)
