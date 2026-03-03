# Declutter — AI File Organizer

**6-Month Production Build** — Full-stack SaaS for duplicate file detection, AI classification, and cloud storage cleanup.

## Quick Start

```bash
# 1. Clone and configure
cd backend && cp .env.example .env
# Generate Fernet key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste output as ENCRYPTION_KEY in .env

# 2. Start everything
docker-compose up
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Celery Flower | http://localhost:5555 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## Architecture

```
declutter/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # 16 route modules
│   │   │   ├── auth.py       # JWT auth (M1)
│   │   │   ├── connections.py # Storage connections (M1)
│   │   │   ├── scans.py      # Scan jobs + manifest ingestion (M1)
│   │   │   ├── dashboard.py  # Stats API (M1)
│   │   │   ├── duplicates.py # Duplicate management (M1)
│   │   │   ├── cloud.py      # Google Drive + Dropbox OAuth (M2)
│   │   │   ├── similar.py    # pHash visual similarity (M2)
│   │   │   ├── classify.py   # AI file classification (M3)
│   │   │   ├── suggestions.py# Smart cleanup suggestions (M3)
│   │   │   ├── billing.py    # Stripe subscription (M3)
│   │   │   ├── onedrive.py   # OneDrive OAuth (M3)
│   │   │   ├── share.py      # Read-only share links (M4)
│   │   │   ├── api_keys.py   # API key management (M5)
│   │   │   ├── export_routes.py # CSV/Excel/GDPR export (M5)
│   │   │   ├── webhooks.py   # Outbound webhooks (M5)
│   │   │   ├── admin.py      # Admin panel (M5)
│   │   │   └── account.py    # Account management + GDPR (M6)
│   │   ├── services/
│   │   │   ├── scanning/     # Duplicate detection engine (M1)
│   │   │   ├── thumbnails/   # Thumbnail gen + R2/S3 (M2)
│   │   │   ├── oauth/        # Google/Dropbox/OneDrive (M2-3)
│   │   │   ├── ai/           # Classifier + suggestions engine (M3)
│   │   │   ├── embeddings/   # CLIP semantic search (M4)
│   │   │   ├── workers/      # Celery tasks + beat scheduler (M4)
│   │   │   ├── notifications/ # Email via Resend (M4)
│   │   │   ├── billing/      # Stripe service (M3)
│   │   │   └── share/        # Share link generation (M4)
│   │   ├── models/           # SQLAlchemy ORM (all months)
│   │   └── core/             # Config, DB, security
│   └── alembic/versions/
│       ├── 001_initial.py    # M1: core tables
│       ├── 002_month2.py     # M2: pHash, OAuth states
│       ├── 003_month3.py     # M3: AI, suggestions, schedules
│       ├── 004_month4.py     # M4: CLIP embeddings, share links
│       └── 005_month5_6.py   # M5-6: API keys, webhooks, audit, prefs
└── frontend/
    ├── app/
    │   ├── dashboard/        # Main dashboard (M1)
    │   ├── duplicates/       # Duplicate groups (M1)
    │   ├── similar/          # Visual similarity (M2)
    │   ├── settings/         # Cloud + billing settings (M2-3)
    │   ├── suggestions/      # Smart cleanup cards (M3)
    │   ├── files/            # All files browser (M4)
    │   ├── api-keys/         # API key management (M5)
    │   └── account/          # Profile, stats, security, GDPR (M6)
    ├── components/layout/Sidebar.tsx
    ├── lib/api.ts            # Full API client
    ├── lib/store.ts          # Zustand auth store
    └── public/
        ├── manifest.json     # PWA manifest (M6)
        └── sw.js             # Service worker (M6)
```

---

## Feature Breakdown by Month

### Month 1 — Foundation
- FastAPI backend with JWT auth (access + refresh tokens)
- PostgreSQL + Redis + Docker Compose
- File manifest ingestion (no file uploads — metadata only)
- MD5 exact duplicate detection with grouping
- Next.js 14 frontend with dark space theme
- Dashboard with stats, duplicate groups page

### Month 2 — Cloud OAuth + Visual Similarity
- Google Drive OAuth (metadata-only indexing via Drive API v3)
- Dropbox OAuth (recursive folder listing + content_hash)
- Thumbnail generation with R2/S3 or base64 fallback
- pHash visual similarity with Union-Find clustering
- Similar Photos page with threshold slider + comparison modal
- Settings page with cloud connections panel

### Month 3 — AI Classification + Billing
- Heuristic classifier: screenshots, receipts, blur detection
- GPT-4o Mini for Pro users (thumbnail-only, never original file)
- Smart suggestions engine: 7 rule types
- OneDrive OAuth via Microsoft Graph API
- Stripe subscription (monthly + yearly, 14-day trial)
- Billing portal for Pro subscribers

### Month 4 — Embeddings + Workers + Notifications
- CLIP semantic embeddings (pgvector cosine similarity)
- Celery task queue with beat scheduler
- Periodic tasks: weekly re-index, monthly reports
- Email notifications via Resend (scan digest, weekly report, welcome)
- Read-only share links for reports (JWT-signed, 7-day expiry)

### Month 5 — API Keys + Webhooks + Admin + Export
- API key management (SHA256-hashed, scoped access)
- Outbound webhooks with HMAC-SHA256 signing
- Admin panel (usage stats, user management, audit log)
- File index export: CSV, Excel (multi-sheet), GDPR JSON
- Audit log for sensitive operations

### Month 6 — Account + PWA + GDPR
- Account page: usage stats chart, password change, notification prefs
- GDPR right-to-erasure: full account deletion with Stripe cancellation
- Progressive Web App: manifest, service worker, push notifications
- User preferences stored in DB
- Mobile-responsive throughout

---

## API Endpoints (All Routes)

```
# Auth
POST  /api/v1/auth/register
POST  /api/v1/auth/login
GET   /api/v1/auth/me
DELETE /api/v1/auth/logout

# Storage
GET   /api/v1/connections
POST  /api/v1/connections/local
POST  /api/v1/connections/google/authorize
GET   /api/v1/connections/google/callback
POST  /api/v1/connections/dropbox/authorize
GET   /api/v1/connections/dropbox/callback
POST  /api/v1/connections/onedrive/authorize
GET   /api/v1/connections/onedrive/callback
POST  /api/v1/connections/{id}/sync
DELETE /api/v1/connections/{id}

# Scanning
POST  /api/v1/scans
POST  /api/v1/scans/ingest
GET   /api/v1/scans/{id}

# Dashboard
GET   /api/v1/dashboard/summary

# Duplicates
GET   /api/v1/duplicates/files
DELETE /api/v1/duplicates/files/{id}
POST  /api/v1/duplicates/files/{id}/undo

# Similar Photos
GET   /api/v1/similar
GET   /api/v1/similar/stats
DELETE /api/v1/similar/files/{id}

# Classification (M3)
POST  /api/v1/classify/run
GET   /api/v1/classify/stats
GET   /api/v1/classify/files

# Suggestions (M3)
GET   /api/v1/suggestions
GET   /api/v1/suggestions/stats
POST  /api/v1/suggestions/generate
POST  /api/v1/suggestions/{id}/apply
POST  /api/v1/suggestions/{id}/dismiss

# Billing (M3)
POST  /api/v1/billing/checkout
POST  /api/v1/billing/portal
POST  /api/v1/billing/webhook
GET   /api/v1/billing/status

# Share Links (M4)
POST  /api/v1/share
GET   /api/v1/share
DELETE /api/v1/share/{id}
GET   /api/v1/share/view/{slug}

# API Keys (M5)
POST  /api/v1/api-keys
GET   /api/v1/api-keys
DELETE /api/v1/api-keys/{id}

# Export (M5)
GET   /api/v1/export/csv
GET   /api/v1/export/excel
GET   /api/v1/export/gdpr

# Webhooks (M5)
POST  /api/v1/webhooks
GET   /api/v1/webhooks
DELETE /api/v1/webhooks/{id}
POST  /api/v1/webhooks/{id}/test

# Admin (M5)
GET   /api/v1/admin/stats
GET   /api/v1/admin/users
POST  /api/v1/admin/users/{id}/tier
GET   /api/v1/admin/audit

# Account (M6)
GET   /api/v1/account/preferences
PUT   /api/v1/account/preferences
POST  /api/v1/account/password
GET   /api/v1/account/stats
DELETE /api/v1/account
```

---

## Environment Variables

See `backend/.env.example` for the full list. Required:
- `SECRET_KEY` — JWT signing key
- `ENCRYPTION_KEY` — Fernet key for OAuth token encryption
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string

Optional (feature-enabling):
- `GOOGLE_CLIENT_ID/SECRET` — Google Drive OAuth
- `DROPBOX_APP_KEY/SECRET` — Dropbox OAuth
- `ONEDRIVE_CLIENT_ID/SECRET` — OneDrive OAuth
- `STRIPE_SECRET_KEY` + price IDs — Billing
- `RESEND_API_KEY` — Email notifications
- `OPENAI_API_KEY` — GPT-4o Mini classification (Pro)
- `R2_ENDPOINT/ACCESS_KEY/SECRET_KEY` — Cloudflare R2 thumbnail storage
- `ADMIN_SECRET` — Admin panel access token

---

## Privacy Model

**No file bytes are ever uploaded or stored.** Declutter only processes:
- File metadata (name, size, path, dates)
- Cryptographic hashes (MD5 for dedup, pHash for visual similarity)
- Thumbnail previews (generated locally or via cloud thumbnail links)

OAuth tokens are encrypted at rest using Fernet AES-256.
Only file metadata is sent to OpenAI (thumbnails ≤256px), never original files.
