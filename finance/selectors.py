from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import Budget, Category, Transaction

ZERO = Decimal("0.00")


def _quantize(value):
    return (value or ZERO).quantize(Decimal("0.01"))


def totals_by_currency(user, start=None, end=None):
    """Income, expense, and net per currency. Returns [{code, symbol, income, expense, net}]."""
    qs = Transaction.objects.filter(user=user)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    rows = qs.values("currency__code", "currency__symbol", "type").annotate(total=Sum("amount"))

    by_currency = {}
    for row in rows:
        code = row["currency__code"]
        bucket = by_currency.setdefault(
            code,
            {"code": code, "symbol": row["currency__symbol"], "income": ZERO, "expense": ZERO},
        )
        bucket[row["type"]] = row["total"] or ZERO

    result = []
    for bucket in by_currency.values():
        income = _quantize(bucket["income"])
        expense = _quantize(bucket["expense"])
        result.append(
            {
                "code": bucket["code"],
                "symbol": bucket["symbol"],
                "income": income,
                "expense": expense,
                "net": income - expense,
            }
        )
    return sorted(result, key=lambda r: r["code"])


def expense_breakdown(user, start=None, end=None):
    """Expense totals by category for the pie chart. Returns [{category, amount}] desc."""
    qs = Transaction.objects.filter(user=user, type=Transaction.EXPENSE)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    rows = qs.values("category__name").annotate(total=Sum("amount")).order_by("-total")
    return [
        {"category": row["category__name"] or "Uncategorised", "amount": _quantize(row["total"])}
        for row in rows
        if (row["total"] or ZERO) > ZERO
    ]


def monthly_series(user, year):
    """Monthly income/expense/net for a year. Returns 12 rows [{month, income, expense, net}]."""
    qs = (
        Transaction.objects.filter(user=user, date__year=year)
        .values("date__month", "type")
        .annotate(total=Sum("amount"))
    )
    months = {m: {"month": m, "income": ZERO, "expense": ZERO} for m in range(1, 13)}
    for row in qs:
        months[row["date__month"]][row["type"]] = _quantize(row["total"])
    series = []
    for m in range(1, 13):
        row = months[m]
        row["net"] = row["income"] - row["expense"]
        series.append(row)
    return series


def budget_spent(budget):
    """Total expenses against a budget (same category/month/currency). Refunds reduce it."""
    spent = (
        Transaction.objects.filter(
            user=budget.user,
            category=budget.category,
            currency=budget.currency,
            type=Transaction.EXPENSE,
            date__year=budget.month.year,
            date__month=budget.month.month,
        ).aggregate(total=Sum("amount"))["total"]
    )
    return _quantize(spent)


def budget_progress(user, month=None):
    """Progress for every budget in a month. Returns [{budget, spent, remaining, percent, over}]."""
    if month is None:
        today = date.today()
        month = today.replace(day=1)
    else:
        month = month.replace(day=1)

    budgets = Budget.objects.filter(user=user, month=month).select_related("category", "currency")
    progress = []
    for budget in budgets:
        spent = budget_spent(budget)
        remaining = _quantize(budget.amount - spent)
        percent = int((spent / budget.amount) * 100) if budget.amount else 0
        progress.append(
            {
                "budget": budget,
                "spent": spent,
                "remaining": remaining,
                "percent": percent,
                "over": spent > budget.amount,
            }
        )
    return progress
