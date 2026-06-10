"""DRF API URLs (mounted at /api/)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register("currencies", api_views.CurrencyViewSet, basename="currency")
router.register("categories", api_views.CategoryViewSet, basename="category")
router.register("transactions", api_views.TransactionViewSet, basename="transaction")
router.register("budgets", api_views.BudgetViewSet, basename="budget")

urlpatterns = [
    path("summary/", api_views.summary, name="api_summary"),
    path("", include(router.urls)),
]
