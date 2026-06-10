# Architecture Overview

A deliberately conventional Django project: standard `models / serializers /
views / urls` per app, business math isolated in small helper modules, and no
unnecessary abstraction layers.

## Apps

| App | Responsibility |
|-----|----------------|
| `config` | Project settings, root URLconf, WSGI/ASGI. |
| `accounts` | Custom `User` model, registration, login/logout, profile. |
| `finance` | Everything financial: categories, transactions, budgets, currencies, dashboard, reports, notifications, and the Part B extras. |

## Models (`finance/models.py`)

```
User (accounts)
 └─< Category (income | expense)
 └─< Transaction >── Currency
 └─< Budget >── Category, Currency

Transaction >── Category (SET_NULL), Currency (PROTECT)
```

- **Currency** — lookup table seeded via migration `0002`. No FX conversion.
- **Category** — owned by a user; unique per `(user, name, type)`.
- **Transaction** — `DecimalField` amount (cent-precise), signed (negative = refund),
  a date, description, optional receipt file, and a currency. `clean()` enforces
  amount ≠ 0 and category/type/owner consistency.
- **Budget** — a monthly goal per `(user, category, month, currency)`; `month` is
  normalised to the 1st; `overrun_notified` prevents duplicate alert emails.

### Key design decisions
- **Money is `Decimal`, never float** — avoids rounding errors on currency.
- **Category delete = `SET_NULL`** — history is never lost; orphaned transactions
  show as *Uncategorised*.
- **Currency is per-transaction; aggregates group by currency** — honest with no
  exchange-rate machinery, matching the assignment's "no forex" guidance.
- **Custom `User` from day one** — standard Django advice; cheap now, painful later.

## Request flow

**HTML (Django Templating Language)**
```
URL (finance/urls.py) → view (finance/views.py)
  → Form validation (finance/forms.py) → Model.clean()
  → selectors.py (aggregation) → template (templates/finance/*.html)
```

**API (DRF)**
```
URL (finance/api_urls.py, router) → ViewSet (finance/api_views.py)
  → Serializer validation (finance/serializers.py) → Model → DB
  → Serializer → JSON response
```

Both paths share the same validation rules (amount ≠ 0, category type/owner
checks) so behaviour is identical regardless of entry point.

## Supporting modules (`finance/`)
| Module | Role |
|--------|------|
| `selectors.py` | Read-side aggregation: totals-by-currency, expense breakdown, monthly series, budget progress. Pure functions, easy to unit-test. |
| `notifications.py` | Sends a one-time email when a budget is exceeded (Django email framework). |
| `insights.py` | Part B: anomaly detection (leave-one-out stats) and LLM/rule-based insights. |
| `imports.py` | Part B: tolerant CSV parser with keyword auto-categorisation and duplicate detection. |

## Authentication
- Session auth for both the HTML UI and the API.
- `django-allauth` adds Google OAuth; the provider is configured from settings
  (`SOCIALACCOUNT_PROVIDERS`) so no DB `SocialApp` row is required. The Google
  button only appears when `GOOGLE_CLIENT_ID` is set.

## Per-user isolation
Every view and queryset is filtered to `request.user`; API viewsets stamp the
owner on create. Accessing another user's object returns 404.

## Settings
`config/settings.py` is environment-driven (`django-environ`). The same code
runs locally (DEBUG, console email, SQLite/Postgres) and in production
(DEBUG off, security headers, WhiteNoise static, SendGrid, managed Postgres)
by changing only environment variables.
