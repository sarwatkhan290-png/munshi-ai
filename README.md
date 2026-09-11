# Munshi AI

Munshi AI is an AI-powered business management app for small shop owners —
a digital replacement for the paper *khata* (credit ledger) notebook.
Shopkeepers can record sales and payments in plain English, Urdu, or Roman
Urdu, photograph a handwritten khata page to auto-digitize it, log
transactions by voice note, and get AI-generated business insights,
reminders, and invoices — all from one dashboard.

## Features

- Natural-language transaction entry (English / Urdu / Roman Urdu), parsed
  by an LLM with an offline regex fallback so the app still works without
  an API key or internet connection
- Customer ledger with running balances and an overdue-payment view
- OCR import: photograph a handwritten khata page and get draft
  transactions to review and confirm (nothing is saved without shopkeeper
  confirmation)
- Voice-note transaction capture via Whisper transcription
- AI business Q&A assistant, sales forecasting, and an internal "Udhaar
  Reliability Score" per customer
- Expense tracking and category reporting
- WhatsApp-ready payment reminders and call scripts (always polite —
  the shopkeeper has final say over any follow-up)
- PDF invoice generation and plain-text digital receipts
- Multi-tenant workspace model: each signup gets its own isolated shop
  (see **Multi-tenancy** below)

## Local setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # then add your OPENAI_API_KEY
python -m streamlit run app.py
```

All AI features (transaction parsing, OCR, voice, Q&A, reminders) degrade
gracefully to offline fallbacks if `OPENAI_API_KEY` is not set — the app
remains fully usable for manual entry either way.

## Running tests

```bash
python -m unittest discover -s tests -v
```

The test suite includes regression tests for tenant isolation (see below)
in addition to transaction-parsing and auth tests.

## Multi-tenancy

Every shop that signs up gets its own `tenant_id`. All reads and writes to
customers, transactions, and expenses are scoped by `tenant_id` at the
service layer — `services/transaction_service.py` and
`services/analytics_service.py` require an explicit `tenant_id` on every
call and raise `MissingTenantError` rather than silently defaulting, so a
missing tenant scope fails loudly during development instead of leaking
data between shops in production. `app.py` sources the current tenant from
`current_tenant_id()`, which reads the logged-in user's session.

## Production notes

This is a strong MVP baseline. Before onboarding real shop owners, still
add:

- Managed PostgreSQL instead of local SQLite, with automated backups
  (SQLite + most free hosts' ephemeral filesystems means data can be lost
  on redeploy)
- Row-level security or equivalent enforcement at the database layer, as a
  second line of defense behind the application-level tenant scoping
- Rate limiting and monitoring on the OpenAI-backed endpoints
- Billing/subscription logic for the existing `plan` field on tenants
- CI/CD and a staging environment

## Security

- Passwords are hashed with PBKDF2-HMAC-SHA256 (200,000 iterations,
  per-user salt) and compared using constant-time comparison.
- Never commit `.env` — it's already gitignored. Rotate any API key that
  has ever been shared, committed, or pasted in plaintext.
