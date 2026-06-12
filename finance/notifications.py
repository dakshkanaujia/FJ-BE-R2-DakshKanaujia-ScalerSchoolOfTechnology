from django.conf import settings
from django.core.mail import send_mail

from .models import Budget
from .selectors import budget_spent


def check_budget_overruns(user, for_date):
    if not user.email:
        return

    month = for_date.replace(day=1)
    budgets = Budget.objects.filter(user=user, month=month).select_related(
        "category", "currency"
    )
    for budget in budgets:
        spent = budget_spent(budget)
        if spent > budget.amount and not budget.overrun_notified:
            _send_overrun_email(user, budget, spent)
            budget.overrun_notified = True
            budget.save(update_fields=["overrun_notified"])
        elif spent <= budget.amount and budget.overrun_notified:
            # Reset so a refund that brings spend back under budget allows future alerts.
            budget.overrun_notified = False
            budget.save(update_fields=["overrun_notified"])


def _send_overrun_email(user, budget, spent):
    over_by = spent - budget.amount
    subject = f"Budget exceeded: {budget.category.name} ({budget.month:%B %Y})"
    body = (
        f"Hi {user.username},\n\n"
        f"You have exceeded your budget for '{budget.category.name}'.\n\n"
        f"  Budget:  {budget.amount} {budget.currency.code}\n"
        f"  Spent:   {spent} {budget.currency.code}\n"
        f"  Over by: {over_by} {budget.currency.code}\n\n"
        f"— Personal Finance Tracker"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
