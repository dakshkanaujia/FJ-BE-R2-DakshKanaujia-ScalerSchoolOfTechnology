from rest_framework import serializers

from .models import Budget, Category, Currency, Transaction


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "code", "name", "symbol"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "type", "created_at"]
        read_only_fields = ["created_at"]


class TransactionSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "type", "category", "category_name", "amount",
            "currency", "currency_code", "date", "description", "receipt", "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_amount(self, value):
        if value == 0:
            raise serializers.ValidationError("Amount cannot be zero.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        category = attrs.get("category") or getattr(self.instance, "category", None)
        txn_type = attrs.get("type") or getattr(self.instance, "type", None)
        if category:
            if category.type != txn_type:
                raise serializers.ValidationError(
                    {"category": "Category type must match the transaction type."}
                )
            if request and category.user_id != request.user.id:
                raise serializers.ValidationError(
                    {"category": "Category belongs to another user."}
                )
        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = Budget
        fields = [
            "id", "category", "category_name", "currency", "currency_code",
            "month", "amount", "overrun_notified", "created_at",
        ]
        read_only_fields = ["overrun_notified", "created_at"]
