import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import insights as insights_mod
from . import selectors
from .forms import BudgetForm, CategoryForm, TransactionForm
from .imports import import_csv
from .models import Budget, Category, Currency, Transaction
from .notifications import check_budget_overruns


@login_required
def dashboard(request):
    today = date.today()
    month_start = today.replace(day=1)

    context = {
        "totals": selectors.totals_by_currency(request.user),
        "month_totals": selectors.totals_by_currency(request.user, start=month_start),
        "expense_breakdown": selectors.expense_breakdown(request.user, start=month_start),
        "monthly_series": selectors.monthly_series(request.user, today.year),
        "budget_progress": selectors.budget_progress(request.user, month=month_start),
        "year": today.year,
        "recent": Transaction.objects.filter(user=request.user).select_related(
            "category", "currency"
        )[:10],
    }
    return render(request, "finance/dashboard.html", context)


# --- Transactions -----------------------------------------------------------

@login_required
def transaction_list(request):
    txns = Transaction.objects.filter(user=request.user).select_related(
        "category", "currency"
    )
    type_filter = request.GET.get("type")
    if type_filter in (Transaction.INCOME, Transaction.EXPENSE):
        txns = txns.filter(type=type_filter)
    return render(
        request,
        "finance/transaction_list.html",
        {"transactions": txns, "type_filter": type_filter},
    )


@login_required
def transaction_create(request):
    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            txn = form.save()
            check_budget_overruns(request.user, txn.date)
            messages.success(request, "Transaction added.")
            return redirect("transaction_list")
    else:
        form = TransactionForm(user=request.user, initial={"date": date.today()})
    return render(
        request, "finance/transaction_form.html", {"form": form, "title": "Add transaction"}
    )


@login_required
def transaction_edit(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES, instance=txn, user=request.user)
        if form.is_valid():
            txn = form.save()
            check_budget_overruns(request.user, txn.date)
            messages.success(request, "Transaction updated.")
            return redirect("transaction_list")
    else:
        form = TransactionForm(instance=txn, user=request.user)
    return render(
        request, "finance/transaction_form.html", {"form": form, "title": "Edit transaction"}
    )


@login_required
def transaction_delete(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        txn.delete()
        messages.success(request, "Transaction deleted.")
        return redirect("transaction_list")
    return render(request, "finance/confirm_delete.html", {"object": txn, "kind": "transaction"})


# --- Categories -------------------------------------------------------------

@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user)
    return render(request, "finance/category_list.html", {"categories": categories})


@login_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            try:
                category.full_clean()
                category.save()
                messages.success(request, "Category created.")
                return redirect("category_list")
            except Exception:
                form.add_error("name", "You already have a category with this name and type.")
    else:
        form = CategoryForm()
    return render(
        request, "finance/category_form.html", {"form": form, "title": "Add category"}
    )


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    txn_count = category.transactions.count()
    if request.method == "POST":
        category.delete()
        messages.success(
            request,
            f"Category deleted. {txn_count} transaction(s) kept as Uncategorised.",
        )
        return redirect("category_list")
    return render(
        request,
        "finance/confirm_delete.html",
        {"object": category, "kind": "category", "txn_count": txn_count},
    )


# --- Budgets ----------------------------------------------------------------

@login_required
def budget_list(request):
    today = date.today()
    progress = selectors.budget_progress(request.user, month=today.replace(day=1))
    return render(
        request,
        "finance/budget_list.html",
        {"progress": progress, "month": today.replace(day=1)},
    )


@login_required
def budget_create(request):
    if request.method == "POST":
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Budget set.")
                return redirect("budget_list")
            except IntegrityError:
                form.add_error(
                    None, "A budget for this category, month and currency already exists."
                )
    else:
        form = BudgetForm(user=request.user, initial={"month": date.today()})
    return render(request, "finance/budget_form.html", {"form": form, "title": "Set budget"})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == "POST":
        budget.delete()
        messages.success(request, "Budget deleted.")
        return redirect("budget_list")
    return render(request, "finance/confirm_delete.html", {"object": budget, "kind": "budget"})


# --- Reports ----------------------------------------------------------------

@login_required
def report(request):
    today = date.today()
    try:
        year = int(request.GET.get("year", today.year))
    except (TypeError, ValueError):
        year = today.year

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    monthly_series = selectors.monthly_series(request.user, year)

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="report_{year}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Month", "Income", "Expense", "Net"])
        for row in monthly_series:
            writer.writerow([row["month"], row["income"], row["expense"], row["net"]])
        return response

    context = {
        "year": year,
        "monthly_series": monthly_series,
        "totals": selectors.totals_by_currency(request.user, start=year_start, end=year_end),
        "years": list(range(today.year, today.year - 6, -1)),
    }
    return render(request, "finance/report.html", context)


# --- Insights & import ------------------------------------------------------

@login_required
def insights(request):
    context = {
        "insights": insights_mod.financial_insights(request.user),
        "anomalies": insights_mod.detect_anomalies(request.user),
    }
    return render(request, "finance/insights.html", context)


@login_required
def import_statement(request):
    stats = None
    if request.method == "POST" and request.FILES.get("file"):
        currency = get_object_or_404(Currency, pk=request.POST.get("currency"))
        stats = import_csv(request.user, request.FILES["file"], currency)
        messages.success(
            request,
            f"Import finished: {stats['imported']} added, "
            f"{stats['duplicates']} duplicates skipped, {stats['errors']} errors.",
        )
    return render(
        request,
        "finance/import_statement.html",
        {"currencies": Currency.objects.all(), "stats": stats},
    )
