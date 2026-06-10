from django import forms

from .models import Budget, Category, Transaction


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].empty_label = "Select type"


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["type", "category", "amount", "currency", "date", "description", "receipt"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.TextInput(attrs={"placeholder": "e.g. Coffee at Starbucks"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user)
        self.fields["category"].required = False
        self.fields["category"].empty_label = "Uncategorised"
        self.fields["currency"].empty_label = "Select currency"
        self.fields["receipt"].required = False
        self.fields["receipt"].label = "Receipt (optional)"
        self.fields["type"].widget.choices = [("", "Select type")] + [
            c for c in self.fields["type"].widget.choices if c[0]
        ]

    def clean(self):
        if self.user is not None:
            self.instance.user = self.user
        return super().clean()


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["category", "currency", "month", "amount"]
        widgets = {
            "month": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(
                user=user, type=Category.EXPENSE
            )
        self.fields["category"].empty_label = "Select category"
        self.fields["currency"].empty_label = "Select currency"
        self.fields["month"].label = "Month"
        self.fields["amount"].widget.attrs["placeholder"] = "0.00"

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.user is not None:
            obj.user = self.user
        if commit:
            obj.save()
        return obj
