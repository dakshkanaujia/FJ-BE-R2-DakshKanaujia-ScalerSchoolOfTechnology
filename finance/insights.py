import json
import statistics
from datetime import date
from decimal import Decimal

import anthropic
from django.conf import settings

from .models import Transaction
from . import selectors

THRESHOLD_SIGMAS = 2
MIN_HISTORY = 4


def detect_anomalies(user):
    """Flag expense transactions that are unusually large for their category."""
    anomalies = []
    expenses = (
        Transaction.objects.filter(user=user, type=Transaction.EXPENSE)
        .select_related("category", "currency")
    )

    groups = {}
    for txn in expenses:
        if txn.amount <= 0:
            continue
        key = (txn.category_id, txn.currency_id)
        groups.setdefault(key, []).append(txn)

    for txns in groups.values():
        if len(txns) < MIN_HISTORY:
            continue
        amounts = [float(t.amount) for t in txns]
        for idx, txn in enumerate(txns):
            # Leave-one-out: exclude this txn from its own threshold so outliers
            # don't inflate the mean and hide themselves.
            others = amounts[:idx] + amounts[idx + 1:]
            mean = statistics.mean(others)
            stdev = statistics.pstdev(others)
            threshold = mean * 1.5 if stdev == 0 else mean + THRESHOLD_SIGMAS * stdev
            if float(txn.amount) > threshold:
                anomalies.append(
                    {
                        "transaction": txn,
                        "category": txn.category.name if txn.category else "Uncategorised",
                        "amount": txn.amount,
                        "mean": Decimal(str(round(mean, 2))),
                        "threshold": Decimal(str(round(threshold, 2))),
                        "currency": txn.currency.code,
                        "reason": (
                            f"{txn.amount} {txn.currency.code} is well above the "
                            f"usual ~{round(mean, 2)} for this category."
                        ),
                    }
                )
    anomalies.sort(key=lambda a: a["amount"], reverse=True)
    return anomalies


def _build_summary(user):
    today = date.today()
    year_start = date(today.year, 1, 1)
    totals = selectors.totals_by_currency(user, start=year_start, end=today)
    breakdown = selectors.expense_breakdown(user, start=year_start)
    return {
        "totals_by_currency": [
            {"currency": t["code"], "income": str(t["income"]),
             "expense": str(t["expense"]), "net": str(t["net"])}
            for t in totals
        ],
        "top_expense_categories": [
            {"category": b["category"], "amount": str(b["amount"])}
            for b in breakdown[:5]
        ],
    }


def financial_insights(user):
    """Return {source, text}. source is 'claude' or 'rule-based'."""
    summary = _build_summary(user)
    if not summary["totals_by_currency"]:
        return {"source": "rule-based", "text": "Add some transactions to get personalised insights."}

    if settings.ANTHROPIC_API_KEY:
        text = _claude_insights(summary)
        if text:
            return {"source": "claude", "text": text}

    return {"source": "rule-based", "text": _rule_based_insights(summary)}


def _rule_based_insights(summary):
    lines = []
    for t in summary["totals_by_currency"]:
        net = Decimal(t["net"])
        verdict = "a surplus" if net >= 0 else "a deficit"
        lines.append(
            f"In {t['currency']} you have {verdict} of {t['net']} "
            f"(income {t['income']}, expenses {t['expense']})."
        )
    if summary["top_expense_categories"]:
        top = summary["top_expense_categories"][0]
        lines.append(
            f"Your largest expense category is '{top['category']}' at {top['amount']}. "
            f"Consider setting a budget for it if you haven't already."
        )
    return " ".join(lines)


def _claude_insights(summary):
    prompt = (
        "You are a concise personal-finance assistant. Given this JSON summary "
        "of a user's year-to-date finances, give 3-4 short, practical, friendly "
        "bullet-point tips. Do not invent numbers.\n\n"
        f"{json.dumps(summary)}"
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception:
        return None
