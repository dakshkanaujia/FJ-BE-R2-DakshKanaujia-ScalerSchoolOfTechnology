from datetime import date

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import selectors
from .models import Budget, Category, Currency, Transaction
from .notifications import check_budget_overruns
from .serializers import (
    BudgetSerializer,
    CategorySerializer,
    CurrencySerializer,
    TransactionSerializer,
)


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer


class OwnedModelViewSet(viewsets.ModelViewSet):
    """Base viewset that scopes all querysets and creates to the requesting user."""

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CategoryViewSet(OwnedModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class TransactionViewSet(OwnedModelViewSet):
    queryset = Transaction.objects.select_related("category", "currency").all()
    serializer_class = TransactionSerializer

    def perform_create(self, serializer):
        txn = serializer.save(user=self.request.user)
        check_budget_overruns(self.request.user, txn.date)

    def perform_update(self, serializer):
        txn = serializer.save()
        check_budget_overruns(self.request.user, txn.date)


class BudgetViewSet(OwnedModelViewSet):
    queryset = Budget.objects.select_related("category", "currency").all()
    serializer_class = BudgetSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary(request):
    today = date.today()
    month_start = today.replace(day=1)
    return Response(
        {
            "totals_all_time": selectors.totals_by_currency(request.user),
            "totals_this_month": selectors.totals_by_currency(request.user, start=month_start),
            "expense_breakdown_this_month": selectors.expense_breakdown(
                request.user, start=month_start
            ),
            "monthly_series": selectors.monthly_series(request.user, today.year),
        }
    )
