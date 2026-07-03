# AI QA Agent — Enterprise Salesforce Knowledge Platform

An application that understands Salesforce codebases like an experienced developer and automates QA workflows. **Phase 1** focuses on application knowledge: scan a Salesforce module, build a dependency graph, and ask AI questions using a **fully local** LLM (LM Studio + Qwen). QA automation (Playwright test execution) remains available alongside the knowledge engine.

**Author:** [Ajay200026](https://github.com/Ajay200026)

## Features

### Knowledge Platform (Phase 1)

- **Module-scoped scanning** — Select one module (e.g. Data Change, Onboarding); only that module and its discovered dependencies are indexed
- **Structured knowledge extraction** — Apex classes, LWC components, objects, fields, flows, validation rules, layouts, permission sets
- **Application knowledge graph** — Neo4j stores relationships: `CALLS`, `USES`, `READS`, `WRITES`, `DEPENDS_ON`, `RENDERS`, and more
- **Vector search** — Chroma indexes entity summaries for semantic retrieval (LM Studio embeddings)
- **Ask AI** — Graph + vector retrieval → local Qwen answers with citations (never sends the full repository to the LLM)
- **Interactive dependency graph** — React Flow visualization with node detail panel (summary, dependencies, business rules, navigation path)
- **Local LLM** — LM Studio OpenAI-compatible endpoint; no cloud API required when `LLM_PROVIDER=lmstudio`

### QA Automation

- **LangGraph agent pipeline** — Parses scenarios, plans steps, executes via Playwright, validates results, and generates reports
- **Salesforce automation** — Page-object model for onboarding, customer lifecycle, data entry, and more
- **Real-time execution streaming** — WebSocket updates in the dashboard as tests run
- **Execution knowledge graph** — Neo4j stores scenario execution traces for traceability
- **Firebase authentication** — Email/password sign-in on the frontend; backend verifies Firebase ID tokens
- **Flexible LLM providers** — LM Studio (local), NVIDIA NIM, or OpenAI for scenario parsing and field resolution

## Architecture

```
Frontend (Next.js 15)
        │
        ▼
FastAPI Backend ─────────────────────────────────────────────┐
        │                                                     │
        ├── Knowledge Engine (Phase 1)                        │
        │     Scanner → Extractors → Postgres (entities)    │
        │                    ├── Neo4j (application graph)  │
        │                    └── Chroma (vector store)      │
        │     Ask AI: graph + vector → LM Studio (Qwen)     │
        │                                                     │
        └── QA Agents (Phase 2+)                              │
              LangGraph → Playwright → Reports                │
                                                              │
PostgreSQL ◄──────────────────────────────────────────────────┘
Neo4j
```

### Knowledge Engine Pipeline

1. **Register repository** — Point to a local Salesforce project path (`force-app`, `sfdx-project.json`)
2. **Select module** — Discover and pick a feature module (e.g. `customerDetails`, `DataChange`)
3. **Scan** — Extract structured knowledge; run dependency closure to pull in referenced Apex, LWC, metadata
4. **Build graph** — Write nodes and relationships to Neo4j; index summaries in Chroma
5. **Ask AI / View graph** — Query indexed knowledge via chat or interactive dependency graph

### QA Agent Pipeline

1. **ScenarioParserAgent** — Converts business scenarios into structured execution plans
2. **PlannerAgent** — Generates ordered automation steps
3. **ExecutorAgent** — Executes steps via Playwright page objects
4. **ValidationAgent** — Validates UI state, messages, and acceptance criteria
5. **ReportAgent** — Generates pass/fail reports with screenshots and logs

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker & Docker Compose | Latest | PostgreSQL + Neo4j |
| Node.js (local frontend) | 20+ | |
| Python (local backend) | 3.11+ | |
| LM Studio | Latest | **Recommended** — load Qwen + embedding model |
| LLM API key | Optional | NVIDIA NIM or OpenAI if not using LM Studio |
| Firebase project | — | Email/Password auth enabled |

### LM Studio Setup (local AI)

1. Install [LM Studio](https://lmstudio.ai)
2. Load a chat model (e.g. **Qwen**)
3. Load an embedding model (e.g. **nomic-embed-text**)
4. Start the local server (default: `http://localhost:1234`)
5. Set in `.env`:

```bash
LLM_PROVIDER=lmstudio
LMSTUDIO_API_BASE=http://localhost:1234/v1
LMSTUDIO_MODEL=qwen                          # match loaded chat model name
LMSTUDIO_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
```

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

# LLM — local (recommended, no cloud API):
LLM_PROVIDER=lmstudio
LMSTUDIO_MODEL=qwen

# OR cloud providers:
# LLM_PROVIDER=nvidia
# NVIDIA_API_KEY=nvapi-your-nvidia-api-key
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-openai-api-key
```

```bash
# 3. Start all services
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Knowledge Platform | http://localhost:3000/knowledge |
| Backend API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Neo4j Browser | http://localhost:7474 (user: `neo4j`, password: `neo4j_secret`) |

> **Note:** LM Studio runs on your host machine, not inside Docker. Start LM Studio before scanning or using Ask AI. For Docker, configure Firebase on the frontend by setting `NEXT_PUBLIC_FIREBASE_*` variables in `frontend/.env.local` before building.

## Using the Knowledge Platform

1. Open **Knowledge** in the sidebar (http://localhost:3000/knowledge)
2. **Register Repository** — enter a name and the absolute path to your local Salesforce project
3. **Select Module** — pick a discovered module (e.g. Data Change, Onboarding)
4. **Scan Module** — extracts knowledge, builds the graph, indexes vectors
5. **View Graph** — interactive dependency visualization at `/knowledge/graph`
6. **Ask AI** — chat about fields, Apex, LWCs, flows, navigation at `/knowledge/ask`

Example questions:

- Where is `Finance_Type__c` used?
- Which Apex class updates Account?
- Explain the Save button execution flow
- Show dependencies for this LWC
- How do I navigate to the Finance section?

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

# Install Playwright browser (QA automation only)
playwright install chromium

# Configure environment
cp ../.env.example .env
# Edit .env — set JWT_SECRET, FERNET_KEY, LLM_PROVIDER (see Quick Start)

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

### 4. LM Studio (local AI)

Start LM Studio with Qwen and an embedding model loaded before scanning or using Ask AI.

Open http://localhost:3000 and register a new account (Firebase Email/Password must be enabled in your Firebase project).

## Environment Variables

### Backend (`.env` in project root or `backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | Yes | JWT signing key (min 32 characters) |
| `FERNET_KEY` | Yes | Fernet key for encrypting Salesforce credentials |
| `LLM_PROVIDER` | Yes | `lmstudio`, `nvidia`, or `openai` |
| `LMSTUDIO_API_BASE` | If using LM Studio | Default: `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | If using LM Studio | Chat model name (e.g. `qwen`) |
| `LMSTUDIO_EMBEDDING_MODEL` | If using LM Studio | Embedding model for vector search |
| `NVIDIA_API_KEY` | If using NVIDIA | NVIDIA NIM API key |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `CHROMA_DIR` | No | Vector store path; default: `./data/chroma` |
| `SF_REPO_PATH` | No | Optional default Salesforce repo path |
| `DATABASE_URL` | No | Default: `postgresql+asyncpg://aiqa:aiqa_secret@localhost:5432/aiqa_db` |
| `NEO4J_URI` | No | Default: `bolt://localhost:7687` |
| `NEO4J_USER` / `NEO4J_PASSWORD` | No | Default: `neo4j` / `neo4j_secret` |
| `FIREBASE_PROJECT_ID` | No | Must match your Firebase project |
| `PLAYWRIGHT_HEADLESS` | No | `true` (default) or `false` to show browser |
| `CORS_ORIGINS` | No | Comma-separated frontend URLs |

See [.env.example](.env.example) for the full list.

### Hosting / production (Playwright)

For any server that runs browser automation:

1. **Recommended:** use the provided Docker backend image (`backend/Dockerfile`), which is based on `mcr.microsoft.com/playwright/python` and already includes Chromium + OS dependencies.
2. Run with Docker Compose: `docker compose up --build`
3. Keep `PLAYWRIGHT_HEADLESS=true` in production.
4. If you deploy without Docker, on the server run once inside the backend venv:
   ```bash
   playwright install chromium
   playwright install-deps chromium   # Linux only — installs system libraries
   ```
5. Do **not** copy a local `PLAYWRIGHT_BROWSERS_PATH` from macOS into production. On Linux/Docker, leave it unset or set `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` when using the official Playwright image.

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

1. **Credentials** — Username/password stored encrypted (Fernet); Playwright logs in via the login page. The same credentials power **REST SOQL** lookups (Login As user resolution, Account Queries).
2. **OAuth (Authorize via Web)** — Same flow as VS Code / SF CLI: pick Production/Sandbox, sign in via browser popup. Uses Salesforce’s built-in `PlatformCLI` Connected App and a local callback on port **1717** — no `.env` setup required.

### Salesforce Orgs page

Use the sidebar **Salesforce Orgs** menu to:

- Authorize orgs (web OAuth or username/password)
- View org details, re-validate, set default, delete
- Default org is pre-selected on **New Execution**

### Custom Connected App (optional)

By default, Web authorize uses the same OAuth client as SF CLI (`PlatformCLI`, callback `http://localhost:1717/OauthRedirect`). To use your own Connected App instead:

1. Salesforce Setup → App Manager → New Connected App
2. Enable OAuth, callback URL: `http://localhost:3000/salesforce-orgs/oauth/callback`
3. Scopes: `api`, `refresh_token`
4. Copy Consumer Key/Secret to backend `.env`:

```bash
SALESFORCE_OAUTH_CLIENT_ID=...
SALESFORCE_OAUTH_CLIENT_SECRET=...
SALESFORCE_OAUTH_REDIRECT_URI=http://localhost:3000/salesforce-orgs/oauth/callback
```

If port **1717** is already in use (e.g. `sf org login web` running), stop that process or switch to a custom Connected App with the frontend callback URL above.

### Login As & Account Queries (REST SOQL)

User and Account lookups use the Salesforce REST API (`/services/data/vXX.X/query`). No browser extension or Salesforce CLI is required — the backend authenticates the same way the CLI would (SOAP login for username/password orgs, or OAuth bearer token).

**Requirements:**

| Requirement | Why |
|-------------|-----|
| Salesforce org connected with **admin** credentials | API must query `User` and `Account` |
| `API Enabled` permission on the integration user | REST query access |
| Password + **security token** (if IP not trusted) | Store as `password` + `token` concatenated in the org password field |
| `instance_url` set on the org | Used for Manage Users navigation after lookup |

**Login As flow:** REST SOQL → User Id → open Manage Users URL in browser → click Login → verify session.

Example SOQL (built automatically from bottler + role):

```sql
SELECT Id, Name, Username, cfs_ob__Bottler__c, cfs_ob__Onboarding_Role__c
FROM User
WHERE IsActive = true
  AND cfs_ob__Bottler__c = '4900'
  AND cfs_ob__Onboarding_Role__c = 'Requestor'
LIMIT 1
```

## API Endpoints

| Module | Endpoints |
|--------|-----------|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Projects | `GET\|POST /projects` |
| **Knowledge Engine** | `POST /knowledge/repos`, `GET /knowledge/repos/{id}/discover`, `POST /knowledge/repos/{id}/modules`, `POST /knowledge/modules/{id}/scan`, `GET /knowledge/modules/{id}/status`, `GET /knowledge/modules/{id}/graph`, `GET /knowledge/entities/{id}`, `POST /knowledge/ask`, `POST /knowledge/ask/stream` |
| Salesforce | `GET\|POST\|PATCH\|DELETE /salesforce/orgs`, `POST /salesforce/orgs/oauth/start`, `POST /salesforce/orgs/oauth/callback`, `POST /salesforce/orgs/{id}/validate` |
| Scenarios | `GET\|POST /scenarios` (multipart upload) |
| Workflows | `GET\|POST /workflows` |
| Executions | `POST /executions`, `GET /executions`, `WS /executions/{id}/stream` |
| Reports | `GET /reports`, `GET /reports/dashboard` |
| Knowledge (QA traces) | `GET /knowledge/scenarios/{id}/graph` |
| System | `GET /config/llm` |

Interactive API documentation: http://localhost:8000/docs

## Project Structure

```
ai-qa-agent/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST API routers
│   │   ├── agents/              # LangGraph QA agents
│   │   ├── automation/          # Playwright page-object framework
│   │   ├── core/                # Config, security, database, LLM
│   │   ├── events/              # WebSocket event manager
│   │   ├── knowledge/           # Neo4j client (QA execution traces)
│   │   ├── knowledge_engine/    # Application knowledge platform
│   │   │   ├── scanner/         # Repo/module discovery, dependency closure
│   │   │   ├── extractors/      # Apex, LWC, metadata, flow parsers
│   │   │   ├── graph_writer.py  # Neo4j application graph
│   │   │   ├── vector_store.py  # Chroma + LM Studio embeddings
│   │   │   ├── ask_service.py   # Graph + vector → LLM answers
│   │   │   └── scan_service.py  # Scan orchestration
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── repositories/        # Data access layer
│   │   ├── schemas/             # Pydantic models
│   │   └── services/            # Business logic
│   └── alembic/                 # Database migrations
├── frontend/
│   └── src/
│       ├── app/
│       │   └── (app)/knowledge/ # Knowledge dashboard, graph, Ask AI
│       ├── components/          # UI components
│       ├── hooks/               # React hooks (auth, execution stream)
│       └── lib/                 # API client, Firebase, types
├── docker-compose.yml
├── .env.example
└── README.md
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend won't start — missing env | Ensure `JWT_SECRET` (32+ chars) and `FERNET_KEY` are set in `.env` |
| `alembic upgrade head` fails | Confirm PostgreSQL is running: `docker compose up postgres -d` |
| LM Studio / Ask AI not working | Start LM Studio, load Qwen + embedding model, verify `http://localhost:1234/v1/models` |
| Vector search empty after scan | Ensure embedding model is loaded in LM Studio; check `LMSTUDIO_EMBEDDING_MODEL` matches |
| No modules discovered | Verify repo path points to a valid SFDX project with `force-app/` |
| Scan finds 0 files | Module name must match folder names in `lwc/`, `classes/`, etc. |
| Graph view empty | Run a scan first; confirm Neo4j is running |
| Playwright browser missing | Run `playwright install chromium` in the backend venv |
| Playwright points at Cursor sandbox path | Restart the backend after pulling latest; the app ignores invalid sandbox paths. Or unset `PLAYWRIGHT_BROWSERS_PATH` in your shell |
| Frontend login fails | Verify Firebase Email/Password is enabled and `NEXT_PUBLIC_FIREBASE_*` match your project |
| Neo4j connection warning | Non-fatal at startup; graph features retry on use. Check `docker compose up neo4j -d` |
| CORS errors | Add your frontend URL to `CORS_ORIGINS` in backend `.env` |

## Tech Stack

- **Frontend:** Next.js 15, React 19, Tailwind CSS, Firebase Auth, TanStack Query, React Flow
- **Backend:** FastAPI, SQLAlchemy, Alembic, LangGraph, Playwright
- **Databases:** PostgreSQL, Neo4j, Chroma (vector store)
- **LLM:** LM Studio (local Qwen) / NVIDIA NIM / OpenAI

## Roadmap

- **Phase 1 (current):** Application Knowledge Engine — module scanning, graph, Ask AI
- **Phase 2:** QA automation integrated with the knowledge engine
- **Future agents:** Architecture, Deployment, Performance, Security, Root Cause Analysis

## License

MIT
