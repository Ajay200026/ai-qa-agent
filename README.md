# AI QA Agent for Salesforce

AI-powered QA testing platform that automates Salesforce workflows like a manual QA engineer. Upload test scenarios, connect Salesforce orgs, and run browser-based executions with real-time streaming, screenshots, and pass/fail reports.

**Author:** [Ajay200026](https://github.com/Ajay200026)

## Features

- **LangGraph agent pipeline** — Parses scenarios, plans steps, executes via Playwright, validates results, and generates reports
- **Salesforce automation** — Page-object model for onboarding, customer lifecycle, data entry, and more
- **Real-time execution streaming** — WebSocket updates in the dashboard as tests run
- **Knowledge graph** — Neo4j stores scenario relationships for traceability
- **Firebase authentication** — Email/password sign-in on the frontend; backend verifies Firebase ID tokens
- **Flexible LLM providers** — NVIDIA NIM (default) or OpenAI for scenario parsing and field resolution

## Architecture

```
Frontend (Next.js 15)  →  FastAPI Backend  →  LangGraph Agents  →  Playwright
        ↓                        ↓                    ↓
   Firebase Auth            PostgreSQL              Neo4j
```

### Agent Pipeline

1. **ScenarioParserAgent** — Converts business scenarios into structured execution plans
2. **PlannerAgent** — Generates ordered automation steps
3. **ExecutorAgent** — Executes steps via Playwright page objects
4. **ValidationAgent** — Validates UI state, messages, and acceptance criteria
5. **ReportAgent** — Generates pass/fail reports with screenshots and logs

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Docker & Docker Compose | Latest |
| Node.js (local frontend) | 20+ |
| Python (local backend) | 3.11+ |
| LLM API key | NVIDIA NIM or OpenAI |
| Firebase project | Email/Password auth enabled |

## Quick Start (Docker)

Recommended for first-time setup. Runs PostgreSQL, Neo4j, backend, and frontend together.

```bash
# 1. Clone the repository
git clone https://github.com/Ajay200026/ai-qa-agent.git
cd ai-qa-agent

# 2. Create backend environment file
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
# Generate a Fernet key (required for encrypting Salesforce credentials)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in .env:
JWT_SECRET=your-long-random-secret-at-least-32-characters
FERNET_KEY=<paste-generated-fernet-key>

# LLM — pick one provider:
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-nvidia-api-key

# OR
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key
```

```bash
# 3. Start all services
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Neo4j Browser | http://localhost:7474 (user: `neo4j`, password: `neo4j_secret`) |

> **Note:** For Docker, configure Firebase on the frontend by setting `NEXT_PUBLIC_FIREBASE_*` variables in `frontend/.env.local` before building, or use local development mode below.

## Local Development

### 1. Start infrastructure

```bash
docker compose up postgres neo4j -d
```

### 2. Backend

```bash
cd backend

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browser
playwright install chromium

# Configure environment
cp ../.env.example .env
# Edit .env — set JWT_SECRET, FERNET_KEY, and LLM API key (see Quick Start)

# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend

npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local — set NEXT_PUBLIC_FIREBASE_* values from Firebase Console

npm run dev
```

Open http://localhost:3000 and register a new account (Firebase Email/Password must be enabled in your Firebase project).

## Environment Variables

### Backend (`.env` in project root or `backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | Yes | JWT signing key (min 32 characters) |
| `FERNET_KEY` | Yes | Fernet key for encrypting Salesforce credentials |
| `LLM_PROVIDER` | Yes | `nvidia` or `openai` |
| `NVIDIA_API_KEY` | If using NVIDIA | NVIDIA NIM API key |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `DATABASE_URL` | No | Default: `postgresql+asyncpg://aiqa:aiqa_secret@localhost:5432/aiqa_db` |
| `NEO4J_URI` | No | Default: `bolt://localhost:7687` |
| `NEO4J_USER` / `NEO4J_PASSWORD` | No | Default: `neo4j` / `neo4j_secret` |
| `FIREBASE_PROJECT_ID` | No | Must match your Firebase project |
| `PLAYWRIGHT_HEADLESS` | No | `true` (default) or `false` to show browser |
| `CORS_ORIGINS` | No | Comma-separated frontend URLs |

See [.env.example](.env.example) for the full list.

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | No | Default: `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_WS_URL` | No | Default: `ws://localhost:8000/api/v1` |
| `NEXT_PUBLIC_FIREBASE_*` | Yes | Firebase web app config from Firebase Console |

See [frontend/.env.example](frontend/.env.example).

### Generate secrets

```bash
# Fernet key (credential encryption)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT secret (any long random string, 32+ chars)
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Firebase Setup

1. Create a project at [Firebase Console](https://console.firebase.google.com)
2. Enable **Authentication → Sign-in method → Email/Password**
3. Add a **Web app** and copy the config values into `frontend/.env.local`
4. Set `FIREBASE_PROJECT_ID` in backend `.env` to match your project ID

## Salesforce Authentication

Supports two methods when adding a Salesforce org:

1. **Credentials** — Username/password stored encrypted (Fernet); Playwright logs in via the login page
2. **OAuth/SFDX** — Access token + instance URL; session injected via `frontdoor.jsp`

## API Endpoints

| Module | Endpoints |
|--------|-----------|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Projects | `GET\|POST /projects` |
| Salesforce | `GET\|POST /salesforce/orgs`, `POST /salesforce/orgs/{id}/validate` |
| Scenarios | `GET\|POST /scenarios` (multipart upload) |
| Workflows | `GET\|POST /workflows` |
| Executions | `POST /executions`, `GET /executions`, `WS /executions/{id}/stream` |
| Reports | `GET /reports`, `GET /reports/dashboard` |
| Knowledge | `GET /knowledge/scenarios/{id}/graph` |

Interactive API documentation: http://localhost:8000/docs

## Project Structure

```
ai-qa-agent/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API routers
│   │   ├── agents/          # LangGraph agents
│   │   ├── automation/      # Playwright page-object framework
│   │   ├── core/            # Config, security, database, LLM
│   │   ├── events/          # WebSocket event manager
│   │   ├── knowledge/       # Neo4j integration
│   │   ├── models/          # SQLAlchemy ORM
│   │   ├── repositories/    # Data access layer
│   │   ├── schemas/         # Pydantic models
│   │   └── services/        # Business logic
│   └── alembic/             # Database migrations
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router pages
│       ├── components/      # UI components
│       ├── hooks/           # React hooks (auth, execution stream)
│       └── lib/             # API client, Firebase, types
├── docker-compose.yml
├── .env.example
└── README.md
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend won't start — missing env | Ensure `JWT_SECRET` (32+ chars) and `FERNET_KEY` are set in `.env` |
| `alembic upgrade head` fails | Confirm PostgreSQL is running: `docker compose up postgres -d` |
| Playwright browser missing | Run `playwright install chromium` in the backend venv |
| Frontend login fails | Verify Firebase Email/Password is enabled and `NEXT_PUBLIC_FIREBASE_*` match your project |
| Neo4j connection warning | Non-fatal at startup; graph features retry on use. Check `docker compose up neo4j -d` |
| CORS errors | Add your frontend URL to `CORS_ORIGINS` in backend `.env` |

## Tech Stack

- **Frontend:** Next.js 15, React 19, Tailwind CSS, Firebase Auth, TanStack Query
- **Backend:** FastAPI, SQLAlchemy, Alembic, LangGraph, Playwright
- **Databases:** PostgreSQL, Neo4j
- **LLM:** NVIDIA NIM / OpenAI

## License

MIT
