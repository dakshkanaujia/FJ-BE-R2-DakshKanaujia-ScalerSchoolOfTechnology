"""Admin registrations for finance models (handy for inspection/debugging)."""

from django.contrib import admin

from .models import Budget, Category, Currency, Transaction


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "user")
    list_filter = ("type",)
    search_fields = ("name",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "type", "amount", "currency", "category", "user")
    list_filter = ("type", "currency", "date")
    search_fields = ("description",)
    date_hierarchy = "date"


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("category", "month", "amount", "currency", "user", "overrun_notified")
    list_filter = ("month", "currency")
