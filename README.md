# AutoPM

AI-native project management: multi-tenant RBAC, stories/tickets, GitHub integration, and autonomous coding agents that open PRs.

**Local development only** — no Docker. PostgreSQL and Redis run on your machine.

## Architecture

| Layer | Stack |
|-------|--------|
| Web | Next.js 14, React, TailwindCSS, shadcn-style UI |
| API | FastAPI, SQLAlchemy 2 async, Alembic |
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

### 2. API server

```bash
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
source .venv/bin/activate
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
source .venv/bin/activate
celery -A modules.agent.celery_app worker --loglevel=info
```

Or use `./scripts/dev-celery.sh`.

### 4. Web app

```bash
cd web
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

### `.env` (repo root)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user@localhost:5432/autopm` |
| `SECRET_KEY` | JWT signing secret |
| `ENCRYPTION_KEY` | Fernet key for GitHub tokens & LLM keys |
| `ANTHROPIC_API_KEY` | Optional global fallback for agent |
| `REDIS_URL` | Celery broker |
| `GITHUB_MCP_SERVER_URL` | GitHub MCP endpoint for agent tools |

### `web/.env.local`

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
├── core/             # config, db, auth, encryption
├── modules/          # auth, users, projects, github, llm, stories, tickets, agent
├── migrations/       # Alembic
├── main.py           # FastAPI entry
├── scripts/          # dev helpers
└── web/              # Next.js App Router
    ├── app/
    ├── components/
    └── lib/
```

## Troubleshooting

- **GitHub/LLM save fails** — set valid `ENCRYPTION_KEY` in `.env`
- **Agent stays queued** — start Redis and the Celery worker
- **Agent errors** — set project LLM config or `ANTHROPIC_API_KEY`; connect GitHub with a PAT that has repo access
