# Personal Finance Tracker

A Django web application to track income, expenses, and budgets, with a
dashboard, reports, multi-currency support, receipt uploads, email alerts on
budget overruns, Google sign-in, and a few AI/analytics extras (LLM insights,
bank-statement import, anomaly detection).

Built with **Django + Django REST Framework + Django Templates + PostgreSQL**.

---

## Features

### Part A (mandatory)
- **Authentication** — register, login, logout, editable profile (custom `User` model).
- **Transactions** — add / edit / delete income & expense items (date, amount, description).
  - Negative amounts allowed as **refunds**; zero rejected.
  - **Decimal** money (never float) — cent-accurate.
  - Deleting a category **keeps** its transactions (they become *Uncategorised*).
- **Categories** — per-user income/expense categories (unique by name + type).
- **Dashboard** — totals by currency, expense pie chart, monthly income-vs-expense bar chart, budget progress, recent activity (Chart.js).
- **Reports** — monthly income vs expense for any year, per-currency year totals, **CSV export**.
- **Budgeting** — monthly budget goals per expense category with progress tracking.
- **Multi-currency** — each transaction has a currency; aggregates are grouped per currency (no FX conversion).
- **Receipts** — upload/store a file per transaction (`MEDIA_ROOT`).
- **Email notifications** — one-time alert when a budget is exceeded.
- **Google OAuth** — sign in with Google via `django-allauth` (needs credentials).
- **REST API** — DRF endpoints for currencies, categories, transactions, budgets, and a summary.

### Part B (extra credit)
- **LLM insights** — plain-language financial advice via Claude Haiku (falls back to rule-based advice with no API key).
- **Bank-statement import** — upload a CSV, auto-categorise by keywords, skip duplicates.
- **Anomaly detection** — flags expenses far above the norm for their category (leave-one-out statistics).

---

## Tech stack
| Layer | Choice |
|------|--------|
| Framework | Django 5.1 |
| API | Django REST Framework |
| UI | Django Templates + Chart.js (CDN) |
| DB | PostgreSQL (SQLite fallback for local dev) |
| Auth | Django auth + django-allauth (Google) |
| Static (prod) | WhiteNoise |
| Server (prod) | Gunicorn |

---

## Installation (local)

```bash
# 1. Clone and enter the project
cd FischerJordan

# 2. Create and activate a virtualenv
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env        # then edit values (see below)

# 5. Migrate (seeds default currencies) and create an admin user
python manage.py migrate
python manage.py createsuperuser

# 6. Run
python manage.py runserver
# open http://127.0.0.1:8000/
```

### Database
- With a PostgreSQL server: set `DB_*` (or `DATABASE_URL`) in `.env` and `USE_SQLITE=False`.
- No Postgres handy? Set `USE_SQLITE=True` to develop on SQLite — schema and code are identical.

---

## Environment variables
See [.env.example](.env.example). Key ones:

| Variable | Purpose |
|---------|---------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` locally, `False` in production |
| `ALLOWED_HOSTS` | comma-separated hosts |
| `DATABASE_URL` *or* `DB_*` | PostgreSQL connection |
| `USE_SQLITE` | use SQLite locally instead of Postgres |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth (optional) |
| `EMAIL_BACKEND`, `EMAIL_HOST_*`, `DEFAULT_FROM_EMAIL` | email / SendGrid (optional) |
| `ANTHROPIC_API_KEY` | LLM insights via Claude Haiku (optional) |

Anything optional degrades gracefully when unset (e.g. no Google button, console emails, rule-based insights).

---

## Running tests
```bash
python manage.py test
```
Covers authentication, transaction CRUD + validation edge cases, category-deletion behaviour, budget tracking + overrun emails, multi-currency aggregation, the report/CSV export, API scoping, and all Part B features.

---

## API quick reference
All endpoints require an authenticated session and are scoped to the current user.

| Method | Path | Description |
|-------|------|-------------|
| GET | `/api/summary/` | Dashboard summary (totals, breakdown, monthly series) |
| CRUD | `/api/transactions/` | Transactions |
| CRUD | `/api/categories/` | Categories |
| CRUD | `/api/budgets/` | Budgets |
| GET | `/api/currencies/` | Supported currencies |

---

## Documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) — apps, models, request flow, key decisions.
