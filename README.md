# Telecom360

**Telecom360: Multi-Operator SIM Lifecycle, Real-Time Number Reservation, Core Network Activation and Operations Intelligence Platform**

Telecom360 is a production-style full-stack telecom SIM lifecycle platform. This repository is scaffolded for phased development with real backend models, API boundaries, role-based access control, PostgreSQL persistence, Redis-backed number locking, WebSocket notifications, and a React operations UI.

## Stack

- Frontend: React, Vite, Tailwind CSS, Recharts, React Flow
- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Auth: JWT with role-based access control
- Realtime: FastAPI WebSocket
- Temporary locking: Redis
- Deployment: Docker Compose

## Project Structure

```text
Telecom360/
  backend/
    app/
      api/v1/          FastAPI routers
      core/            settings, security, RBAC
      db/              SQLAlchemy engine/session/base
      models/          database models
      schemas/         Pydantic schemas
      services/        domain services and workflow logic
      realtime/        websocket connection manager
      main.py          FastAPI application entrypoint
    migrations/        Alembic migration environment
    scripts/           seed and operational scripts
    tests/             backend tests
  frontend/
    src/
      api/             API client
      components/      shared UI and layout
      context/         auth/session state
      hooks/           realtime hooks
      pages/           route pages by role/workflow
      routes/          router configuration
  docker-compose.yml
```

## Start the Project

1. Copy environment values:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker compose up --build
```

3. In a second terminal, create tables and seed starter telecom inventory:

```bash
docker compose exec backend python scripts/seed.py
```

The seed script creates three companies and 1000 SIM records per company.

4. Open the apps:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8001
- API docs: http://localhost:8001/docs

## Local Backend Commands

From `backend/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create tables and seed local data:

```bash
python scripts/seed.py
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create tables and seed local data:

```powershell
python scripts\seed.py
```

## Local Frontend Commands

From `frontend/`:

```bash
npm install
npm run dev
```

## Phase-One Scope

This first phase creates the deployable skeleton: app structure, Docker Compose, environment configuration, RBAC-ready backend, database models, realtime hooks, starter dashboards, and documented project rules. Later phases should fill in migrations, tests, complete API implementations, seed data generation, activation simulations, analytics, complaints, replacements, and audit reporting.
