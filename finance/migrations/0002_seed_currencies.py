"""Seed the Currency lookup table with a handful of common currencies."""

from django.db import migrations

CURRENCIES = [
    ("USD", "US Dollar", "$"),
    ("EUR", "Euro", "€"),
    ("GBP", "British Pound", "£"),
    ("INR", "Indian Rupee", "₹"),
    ("JPY", "Japanese Yen", "¥"),
    ("CAD", "Canadian Dollar", "$"),
    ("AUD", "Australian Dollar", "$"),
]


def seed(apps, schema_editor):
    Currency = apps.get_model("finance", "Currency")
    for code, name, symbol in CURRENCIES:
        Currency.objects.get_or_create(code=code, defaults={"name": name, "symbol": symbol})


def unseed(apps, schema_editor):
    Currency = apps.get_model("finance", "Currency")
    Currency.objects.filter(code__in=[c[0] for c in CURRENCIES]).delete()


class Migration(migrations.Migration):

    dependencies = [("finance", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
