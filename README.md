# AutoPM

AI-native project management: multi-tenant RBAC, stories/tickets, GitHub integration, and autonomous coding agents that open PRs.

**Local development only** — no Docker. PostgreSQL and Redis run on your machine.

## Architecture

| Layer | Stack |
|-------|--------|
| Frontend | Next.js 14, React, TailwindCSS, shadcn-style UI |
| Backend | FastAPI, SQLAlchemy 2 async, Alembic |
| Database | PostgreSQL 15+ |
| Queue | Celery + Redis |
| AI | Anthropic Claude + GitHub MCP |

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (`createdb autopm`)
- Redis (`brew install redis && brew services start redis`)

## Quick start

### 1. Database

```bash
createdb autopm
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit DATABASE_URL and generate ENCRYPTION_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
alembic upgrade head
python seed.py          # optional: create default company + owner user
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Seed (default super user)

```bash
cd backend && source .venv/bin/activate
python seed.py
```

Creates one company and one **owner** user (skipped if they already exist):

| Field | Default |
|-------|---------|
| Company | AutoPM (`autopm`) |
| Email | `admin@autopm.com` |
| Password | `changeme123` |

Override via `SEED_*` env vars in `.env` (see `.env.example`).

### 3. Celery worker (agent runs)

```bash
cd backend && source .venv/bin/activate
celery -A modules.agent.celery_app worker --loglevel=info
```

### 4. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000 — API at http://localhost:8000/docs

## First-time flow

1. **Register** at `/register` — creates company + owner account
2. **Create project** — `/projects/new`
3. **Settings** — connect GitHub repo, configure LLM (Anthropic key per project)
4. **Stories & tickets** — create work items under a project
5. **Enable agent** on a ticket → **Run agent** — watch live logs via SSE

## Environment variables

### `backend/.env`

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user@localhost:5432/autopm` |
| `SECRET_KEY` | JWT signing secret |
| `ENCRYPTION_KEY` | Fernet key for GitHub tokens & LLM keys |
| `ANTHROPIC_API_KEY` | Optional global fallback for agent |
| `REDIS_URL` | Celery broker |
| `GITHUB_MCP_SERVER_URL` | GitHub MCP endpoint for agent tools |

### `frontend/.env.local`

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API overview

- **Auth** — register, login, refresh, `/auth/me`
- **Projects** — CRUD, members, RBAC
- **GitHub** — connect repo, list repos, index codebase
- **LLM** — per-project provider config (encrypted keys)
- **Stories / Tickets** — CRUD, comments, agent enable
- **Agent** — queue run, SSE log stream, cancel

## RBAC

| Global | Project | Can create tickets, run agent |
|--------|---------|-------------------------------|
| owner, admin | (bypass) | ✅ |
| member | manager | stories + config |
| member | developer | tickets + agent |
| member | viewer | read-only |

## Project structure

```
AutoPM/
├── backend/          # FastAPI + Celery
│   ├── core/         # config, db, auth, encryption
│   ├── modules/      # auth, users, projects, github, llm, stories, tickets, agent
│   └── migrations/
└── frontend/         # Next.js App Router
    ├── app/          # pages
    ├── components/
    └── lib/          # api, auth, hooks
```

## Troubleshooting

- **GitHub/LLM save fails** — set valid `ENCRYPTION_KEY` in `.env`
- **Agent stays queued** — start Redis and the Celery worker
- **Agent errors** — set project LLM config or `ANTHROPIC_API_KEY`; connect GitHub with a PAT that has repo access
