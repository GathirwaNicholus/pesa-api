# 💰 Pesa API

> **Personal Finance Tracking REST API** — built with FastAPI, PostgreSQL, and a C++ analytics engine.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)
[![C++](https://img.shields.io/badge/C%2B%2B-17-00599C?logo=cplusplus)](https://isocpp.org)

---

## What is Pesa API?

Pesa (Swahili for *money*) is a production-ready REST API for tracking personal income and expenses. It features:

- **JWT authentication** — register, login, protected routes
- **Transaction management** — create, list (with pagination + filters), update, delete
- **Budget tracking** — set spending limits per category, get overage alerts
- **Analytics engine** — total income/expense/net, top 3 categories, 3-month moving average, burn-rate forecast
- **C++ performance layer** — moving average and burn-rate calculations in a compiled shared library (ctypes bridge)
- **Normalised PostgreSQL schema** — foreign keys, ENUM types, composite indexes, analytical views
- **Auto-generated API docs** — Swagger UI at `/api/v1/docs`
- **Glassmorphism frontend** — single-file SPA at `http://localhost:8080`

---

## Directory Structure

```
pesa-api/
├── cpp/
│   ├── finance_engine.h        # C function declarations (extern "C")
│   ├── finance_engine.cpp      # Moving average + burn-rate implementation
│   └── Makefile                # Builds libfinance.so
├── api/
│   ├── main.py                 # FastAPI app, middleware, lifespan
│   ├── config.py               # Pydantic Settings (reads .env)
│   ├── database.py             # Async SQLAlchemy engine + session factory
│   ├── models.py               # ORM models (User, Transaction, Budget)
│   ├── schemas.py              # Pydantic v2 request/response schemas
│   ├── auth.py                 # JWT + BCrypt + get_current_user dependency
│   ├── engine_bridge.py        # ctypes bridge to libfinance.so
│   └── routers/
│       ├── auth.py             # POST /auth/register, /auth/login, GET /auth/me
│       ├── transactions.py     # CRUD /transactions
│       ├── budgets.py          # CRUD /budgets
│       └── analytics.py        # GET /analytics
├── frontend/
│   ├── index.html              # SPA shell
│   ├── style.css               # Glassmorphism dark-purple theme
│   └── app.js                  # Vanilla JS SPA logic
├── sql/
│   ├── 001_init.sql            # Schema, ENUMs, indexes, views
│   └── 002_seed.sql            # Demo data (Wanjiku's finances)
├── docker-compose.yml          # Full stack: Postgres + API + Nginx
├── Dockerfile                  # Multi-stage: C++ build + Python runtime
├── nginx.conf                  # Serves frontend, proxies /api/
├── requirements.txt
├── .env.example
└── README.md
```

---

## Local Setup (Docker — recommended)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)

### 1. Clone & configure

```bash
git clone https://github.com/your-username/pesa-api.git
cd pesa-api
cp .env.example .env
# Edit .env if you want to change passwords / secret key
```

### 2. Run the full stack

```bash
docker compose up --build
```

This single command:
1. Compiles `libfinance.so` from C++ source (Stage 1)
2. Starts PostgreSQL 16
3. Applies `001_init.sql` (schema) and `002_seed.sql` (demo data) automatically
4. Starts the FastAPI server
5. Starts Nginx to serve the frontend

### 3. Open in browser

| URL | What |
|-----|------|
| `http://localhost:8080` | Frontend dashboard |
| `http://localhost:8000/api/v1/docs` | Swagger UI (API explorer) |
| `http://localhost:8000/health` | Health check |
| `http://localhost:5432` | PostgreSQL (connect with any DB client) |

### 4. Demo login

```
Email:    wanjiku@example.com
Password: password123
```

---

## Local Setup (Manual / Development)

### Prerequisites
- Python 3.12+
- PostgreSQL 16+
- GCC / G++ 11+

### 1. Build the C++ library

```bash
cd cpp
make
cd ..
```

This produces `cpp/libfinance.so`.

### 2. Set up the database

```bash
# Create the DB
createdb pesadb

# Apply migrations
psql -d pesadb -f sql/001_init.sql
psql -d pesadb -f sql/002_seed.sql
```

### 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL to your local Postgres
# Example: postgresql+asyncpg://postgres:postgres@localhost:5432/pesadb
```

### 5. Run the API

```bash
uvicorn api.main:app --reload --port 8000
```

`--reload` enables hot-reload on file changes. Open `http://localhost:8000/api/v1/docs`.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | Full asyncpg connection URL |
| `SECRET_KEY` | ✅ | — | JWT signing secret (min 32 chars). Generate: `openssl rand -hex 32` |
| `ALGORITHM` | ❌ | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `1440` | Token TTL (24 hours) |
| `DEBUG` | ❌ | `false` | Enables SQL query logging |
| `ALLOWED_ORIGINS` | ❌ | `["http://localhost:8080"]` | CORS allowed origins (JSON array) |
| `LIB_PATH` | ❌ | `./cpp/libfinance.so` | Path to compiled C++ library |
| `POSTGRES_USER` | ❌ | `pesa` | Docker Compose only |
| `POSTGRES_PASSWORD` | ❌ | `pesa` | Docker Compose only |
| `POSTGRES_DB` | ❌ | `pesadb` | Docker Compose only |

---

## API Endpoint Reference

All protected endpoints require:
```
Authorization: Bearer <your_jwt_token>
```

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/register` | ❌ | Create account. Body: `{email, password, full_name?}` |
| `POST` | `/api/v1/auth/login` | ❌ | Login. Body: `{email, password}`. Returns `{access_token}` |
| `GET`  | `/api/v1/auth/me` | ✅ | Get current user profile |

### Transactions

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/transactions` | ✅ | Create transaction. Body: `{amount, currency?, category, description?, type}` |
| `GET`  | `/api/v1/transactions` | ✅ | List (paginated). Query: `page`, `size`, `category`, `type` |
| `GET`  | `/api/v1/transactions/{id}` | ✅ | Get single transaction |
| `PATCH`| `/api/v1/transactions/{id}` | ✅ | Partial update |
| `DELETE`| `/api/v1/transactions/{id}` | ✅ | Delete |

**Create transaction body:**
```json
{
  "amount": 8500.00,
  "currency": "KES",
  "category": "Food",
  "description": "Naivas groceries",
  "type": "expense"
}
```

### Budgets

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/budgets` | ✅ | Create budget. Body: `{category, limit_amount, period, start_date}` |
| `GET`  | `/api/v1/budgets` | ✅ | List budgets. Query: `active_only` (default: true) |
| `PATCH`| `/api/v1/budgets/{id}` | ✅ | Update budget |
| `DELETE`| `/api/v1/budgets/{id}` | ✅ | Delete budget |

**Create budget body:**
```json
{
  "category": "Food",
  "limit_amount": 10000.00,
  "period": "monthly",
  "start_date": "2025-01-01"
}
```

### Analytics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/analytics` | ✅ | Full analytics summary. Query: `months` (1–12, default 3) |

**Analytics response shape:**
```json
{
  "period_start": "2025-01-01",
  "period_end":   "2025-03-31",
  "total_income":  263000.00,
  "total_expense": 148700.00,
  "net":           114300.00,
  "top_categories": [
    { "category": "Rent",  "total": 66000.00, "percentage": 44.4 },
    { "category": "Food",  "total": 28200.00, "percentage": 19.0 },
    { "category": "Transport", "total": 11200.00, "percentage": 7.5 }
  ],
  "monthly_moving_avg": [
    { "month": "2025-01", "total_expense": 41700.00, "moving_avg": null },
    { "month": "2025-02", "total_expense": 46300.00, "moving_avg": null },
    { "month": "2025-03", "total_expense": 44200.00, "moving_avg": 44066.67 }
  ],
  "burn_rate": {
    "daily_rate": 1473.33,
    "days_left": 18.3,
    "forecast_label": "Budget lasts ~18 more days at current rate"
  },
  "overage_alerts": [
    {
      "budget_id": "...",
      "category": "Eating Out",
      "limit_amount": 4000.00,
      "total_spent": 5500.00,
      "overage": 1500.00,
      "is_over": true
    }
  ]
}
```

### System

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | ❌ | Liveness + DB connectivity check |
| `GET` | `/api/v1/docs` | ❌ | Swagger UI |
| `GET` | `/api/v1/redoc` | ❌ | ReDoc UI |

---

## Compiling the C++ Library

```bash
cd cpp

# Build
make

# Verify symbols are exported correctly
nm -D libfinance.so | grep -E 'calc_moving|calc_burn'
# Should show:
#   T calc_moving_average
#   T calc_burn_rate_forecast

# Run smoke test (optional)
make test
```

The shared library is loaded by `api/engine_bridge.py` via Python's `ctypes`. If the library is missing, the API continues to work — analytics fields that depend on C++ will return `null` (graceful degradation).

---

## Deploying to Railway (Free Tier)

Railway is the easiest way to deploy this publicly. It provides managed Postgres and auto-deploys from GitHub.

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: Pesa API"
git remote add origin https://github.com/your-username/pesa-api.git
git push -u origin main
```

Make sure `.gitignore` excludes `.env` and `cpp/libfinance.so`.

### Step 2 — Create a Railway project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Select **Deploy from GitHub repo** → connect your `pesa-api` repo
3. Railway auto-detects the `Dockerfile` and sets up the build

### Step 3 — Add PostgreSQL

1. In your project dashboard → **+ New** → **Database** → **PostgreSQL**
2. Railway provisions a Postgres instance and exposes `DATABASE_URL`

### Step 4 — Set environment variables

In Railway project settings → **Variables**, add:

```
SECRET_KEY          = <output of: openssl rand -hex 32>
DATABASE_URL        = ${{Postgres.DATABASE_URL}}   ← Railway reference variable
DEBUG               = false
ALLOWED_ORIGINS     = ["https://your-app.railway.app"]
```

> Railway automatically injects `DATABASE_URL` from the Postgres service.
> You just need to rename/reference it.

### Step 5 — Apply database migrations

In Railway, open the Postgres service → **Connect** → use the provided connection string to run:

```bash
psql "<railway_connection_string>" -f sql/001_init.sql
psql "<railway_connection_string>" -f sql/002_seed.sql
```

Or use Railway's built-in query editor to paste the SQL directly.

### Step 6 — Deploy

Railway auto-deploys on every `git push main`. The build runs the multi-stage Dockerfile (C++ compile + Python install).

After deployment, your API is live at `https://your-app.railway.app/api/v1/docs`.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | FastAPI 0.111 | Async-first, auto OpenAPI docs, Pydantic v2 |
| Language | Python 3.12 | Typed, async/await, rich ecosystem |
| Database | PostgreSQL 16 | ACID, ENUM types, window functions, JSONB |
| ORM | SQLAlchemy 2.0 (async) | Composable queries, async sessions, migration support |
| Driver | asyncpg | Fastest async Postgres driver (C extension) |
| Validation | Pydantic v2 | Rust-core, 10-50x faster than v1 |
| Auth | python-jose + passlib | HS256 JWT + BCrypt password hashing |
| Performance | C++17 (ctypes) | Moving average + burn-rate in compiled code |
| Container | Docker multi-stage | Separate build/runtime, minimal final image |
| Reverse proxy | Nginx Alpine | Static file serving + API proxy |

---

## Design Decisions

**Why async SQLAlchemy?**
FastAPI runs on asyncio. Synchronous DB calls block the event loop — no other requests can be served during a DB query. Async allows hundreds of concurrent requests with a single thread.

**Why NUMERIC not FLOAT for money?**
Floating-point arithmetic loses precision: `0.1 + 0.2 = 0.30000000000000004`. NUMERIC stores exact decimals. Never use FLOAT for currency.

**Why JWT (not sessions)?**
Sessions require server-side state (a session store). JWT is stateless — the token itself carries the user ID. Scales horizontally without shared state.

**Why C++ for the finance calculations?**
Demonstrates the Python-as-glue + compiled-code-for-hot-loops pattern used by NumPy, PyTorch, etc. Also a great CV talking point.

**Why two SQL migration files?**
001 is structure (safe for production). 002 is seed data (dev/demo only). Keeping them separate makes the production/dev boundary explicit.

---

## Contributing

PRs welcome! See open issues for ideas:
- [ ] CSV export endpoint
- [ ] Recurring transaction support  
- [ ] WebSocket real-time balance updates
- [ ] Argon2 password hashing upgrade
- [ ] Alembic migration integration

---

## License

MIT — do whatever you want, attribution appreciated.
