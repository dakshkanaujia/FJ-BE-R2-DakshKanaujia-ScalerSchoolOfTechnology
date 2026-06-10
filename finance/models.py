from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

MONEY_MAX_DIGITS = 12
MONEY_DECIMAL_PLACES = 2


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5, default="")

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "currencies"

    def __str__(self):
        return self.code


class Category(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    TYPE_CHOICES = [(INCOME, "Income"), (EXPENSE, "Expense")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=7, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "type"], name="unique_category_per_user"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class Transaction(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    TYPE_CHOICES = [(INCOME, "Income"), (EXPENSE, "Expense")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    # SET_NULL so deleting a category keeps its transactions as Uncategorised.
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    type = models.CharField(max_length=7, choices=TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="transactions")
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    receipt = models.FileField(upload_to="receipts/%Y/%m/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.get_type_display()} {self.amount} {self.currency} on {self.date}"

    def clean(self):
        if self.amount is not None and self.amount == Decimal("0"):
            raise ValidationError({"amount": "Amount cannot be zero."})
        if self.category:
            if self.category.type != self.type:
                raise ValidationError(
                    {"category": "Category type must match the transaction type."}
                )
            if self.user_id and self.category.user_id != self.user_id:
                raise ValidationError({"category": "Category belongs to another user."})


class Budget(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets"
    )
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="budgets"
    )
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="budgets")
    month = models.DateField()
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    # Prevents repeat emails after the first overrun alert is sent.
    overrun_notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "month", "currency"],
                name="unique_budget_per_category_month_currency",
            )
        ]

    def __str__(self):
        return f"Budget {self.category} {self.month:%Y-%m}: {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        if self.month:
            self.month = self.month.replace(day=1)
        super().save(*args, **kwargs)
