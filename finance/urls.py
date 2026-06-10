"""HTML (template) URLs for the finance app."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("transactions/", views.transaction_list, name="transaction_list"),
    path("transactions/add/", views.transaction_create, name="transaction_create"),
    path("transactions/<int:pk>/edit/", views.transaction_edit, name="transaction_edit"),
    path("transactions/<int:pk>/delete/", views.transaction_delete, name="transaction_delete"),

    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),

    path("budgets/", views.budget_list, name="budget_list"),
    path("budgets/add/", views.budget_create, name="budget_create"),
    path("budgets/<int:pk>/delete/", views.budget_delete, name="budget_delete"),

    path("reports/", views.report, name="report"),

    # Part B
    path("insights/", views.insights, name="insights"),
    path("import/", views.import_statement, name="import_statement"),
]
