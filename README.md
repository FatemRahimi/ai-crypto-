# AI-Crypto

Personal adaptive AI-quant futures trading intelligence. This repository is the Phase 1 foundation: a modular monolith, a desktop application shell, and the boundaries the later system has to respect.

Phase 1 does not trade, does not connect to an exchange, and does not display live market data.

## What you can run locally

- Web application: http://127.0.0.1:3000
- API: http://127.0.0.1:8000
- API docs (local and test only): http://127.0.0.1:8000/docs

The home page answers the command-center questions from the real Phase 1 state. Sample panels are marked **Demo**. They are not prices, signals, or account figures.

## Windows setup

Use PowerShell from the repository root, `E:\ai-crypto`.

### 1. Environment files

```powershell
Copy-Item .env.example .env
Copy-Item frontend\.env.example frontend\.env.local
```

`.env` is gitignored. The sample values are for this machine only. Do not put exchange API secrets in either file. The frontend file contains only the public API address.

`APP_SECRET_KEY` is loaded and rejected in production when it is still a placeholder. Phase 1 does not sign sessions with it. Sessions are not implemented.

### 2. PostgreSQL

The API needs its own database and role. It must not use the PostgreSQL superuser.

```text
database: aicrypto
role:     aicrypto
```

Docker Compose can start that isolated server when Docker is installed and port 5432 is free:

```powershell
docker compose up -d
```

On this machine, Docker is not installed. PostgreSQL 16 is already running on port 5432, and PostgreSQL 18 is on port 5433. Both require `scram-sha-256`. No `pgpass` file and no `PGPASSWORD` were available, so the `aicrypto` role was not created and no existing database was modified. The API still starts. `GET /health/live` stays healthy. `GET /health/ready` stays 503 until this database accepts the password in `.env`.

To create the isolated database yourself, open **SQL Shell (psql)** from the PostgreSQL 16 install and connect as the superuser you created at install time. Then run:

```sql
CREATE ROLE aicrypto LOGIN PASSWORD 'choose-a-local-password';
CREATE DATABASE aicrypto OWNER aicrypto;
```

Put that same password only in the gitignored `.env` (`DATABASE_URL` and `POSTGRES_PASSWORD`). Do not put the superuser password in `.env`. If a role named `aicrypto` already exists, do not change its password; pick a different role name and point `DATABASE_URL` at it.

Then:

```powershell
cd backend
.\.venv\Scripts\python -m alembic upgrade head
```

### 3. Backend

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m app
```

`python -m app` reads `API_HOST` and `API_PORT` from `.env`. The default port is 8000.

If port 8000 is already in use, leave that process alone. In `.env` set `API_PORT=8001`, and in `frontend/.env.local` set:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
```

Restart both processes after changing those values. `python -m app` does not read the frontend file, and the frontend does not read `API_PORT`.

`alembic upgrade head` applies the version table and the BTC market-data tables. If PostgreSQL rejects the connection, that command fails and the API can still be used. Readiness stays degraded and market routes report the store as unavailable.

A small public BTC/USDT ingest, with no API key:

```powershell
.\.venv\Scripts\python -m app.domains.market_data --interval 1m --limit 5
```

That stores up to five closed one-minute candles. Add `--dataset trades` or `--dataset book` for one small recent-trade or book-ticker request. A start and end must be timezone-aware, and a range above 1000 candles is refused unless `--max-candles` is raised, never above 5000.

### 4. Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

If `npm install` fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, Node is not seeing the Windows certificate store. Retry in the same terminal:

```powershell
$env:NODE_OPTIONS="--use-system-ca"
npm install
```

That uses the operating-system trust store. It does not disable certificate checks.

Open http://127.0.0.1:3000.


### 5. Tests and checks

Backend:

```powershell
cd backend
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy app tests
.\.venv\Scripts\python -m pip_audit --progress-spinner off
```

If `pip-audit` or the public market-data client fails with a certificate error, point `SSL_CERT_FILE` at a PEM export of the Windows root store and run the command again. Do not disable certificate verification. The market-data client uses that bundle when the variable is set.

Frontend:

```powershell
cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
npm audit
```

`npm audit fix --force` is intentionally not a setup step. It proposes major downgrades and upgrades. See `docs/SECURITY.md`.

## Repository map

```text
backend/     FastAPI modular monolith
frontend/    Next.js application shell
docs/        Constitution, architecture, roadmap, and security rules
```

Read `docs/PROJECT_CONSTITUTION.md` before adding a strategy, model, or exchange call.
