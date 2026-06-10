"""Admin registration for the custom User model."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Reuse Django's UserAdmin, adding our extra profile field."""

    fieldsets = UserAdmin.fieldsets + (
        ("Profile", {"fields": ("full_name",)}),
    )
    list_display = ("username", "email", "full_name", "is_staff")
