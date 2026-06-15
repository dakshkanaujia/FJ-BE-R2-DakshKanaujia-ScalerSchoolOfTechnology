import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .models import Category, Transaction

KEYWORD_RULES = [
    ("uber", "Transport", "expense"),
    ("lyft", "Transport", "expense"),
    ("fuel", "Transport", "expense"),
    ("starbucks", "Food", "expense"),
    ("restaurant", "Food", "expense"),
    ("grocery", "Groceries", "expense"),
    ("supermarket", "Groceries", "expense"),
    ("amazon", "Shopping", "expense"),
    ("netflix", "Subscriptions", "expense"),
    ("spotify", "Subscriptions", "expense"),
    ("rent", "Rent", "expense"),
    ("electric", "Utilities", "expense"),
    ("salary", "Salary", "income"),
    ("payroll", "Salary", "income"),
    ("interest", "Interest", "income"),
]

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]


def _parse_date(value):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _parse_amount(value):
    if value is None or value.strip() == "":
        return None
    cleaned = value.replace(",", "").replace("$", "").replace("£", "").replace("€", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _categorise(user, description, txn_type, cache):
    desc = (description or "").lower()
    for keyword, cat_name, cat_type in KEYWORD_RULES:
        if cat_type == txn_type and keyword in desc:
            key = (cat_name, cat_type)
            if key not in cache:
                cache[key], _ = Category.objects.get_or_create(
                    user=user, name=cat_name, type=cat_type
                )
            return cache[key]
    return None


def import_csv(user, file_obj, currency):
    stats = {"imported": 0, "duplicates": 0, "errors": 0, "error_rows": []}
    cat_cache = {}
    seen_in_file = set()

    raw = file_obj.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        stats["errors"] += 1
        stats["error_rows"].append("Empty or unreadable file.")
        return stats

    fieldmap = {name.lower().strip(): name for name in reader.fieldnames}

    def col(row, *names):
        for n in names:
            if n in fieldmap:
                return row.get(fieldmap[n])
        return None

    for i, row in enumerate(reader, start=2):
        txn_date = _parse_date(col(row, "date", "transaction date", "posted date") or "")
        description = (col(row, "description", "details", "narrative", "memo") or "").strip()

        amount = _parse_amount(col(row, "amount", "value") or "")
        if amount is None:
            debit = _parse_amount(col(row, "debit", "withdrawal") or "")
            credit = _parse_amount(col(row, "credit", "deposit") or "")
            if debit:
                amount, txn_type = abs(debit), Transaction.EXPENSE
            elif credit:
                amount, txn_type = abs(credit), Transaction.INCOME
            else:
                amount = None
        else:
            txn_type = Transaction.INCOME if amount > 0 else Transaction.EXPENSE
            amount = abs(amount)

        if not txn_date or amount is None or amount == 0:
            stats["errors"] += 1
            stats["error_rows"].append(f"Row {i}: missing/invalid date or amount.")
            continue

        # Two-level duplicate detection: within the file, then against the DB.
        dedup_key = (txn_date, amount, txn_type, description)
        if dedup_key in seen_in_file:
            stats["duplicates"] += 1
            continue
        seen_in_file.add(dedup_key)

        exists = Transaction.objects.filter(
            user=user, date=txn_date, amount=amount, type=txn_type,
            currency=currency, description=description,
        ).exists()
        if exists:
            stats["duplicates"] += 1
            continue

        category = _categorise(user, description, txn_type, cat_cache)
        Transaction.objects.create(
            user=user, type=txn_type, category=category, amount=amount,
            currency=currency, date=txn_date, description=description,
        )
        stats["imported"] += 1

    return stats
