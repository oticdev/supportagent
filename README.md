# RelayPay Support Agent

An AI-powered customer support platform for RelayPay. It combines a **chat agent** and a **voice agent** that can answer product questions, check Google Calendar availability, book support calls, and escalate complex issues to the human support team via Slack.

## Features

- **Chat agent** — Conversational support powered by OpenRouter (GPT-4o-mini by default). Searches a vector knowledge base (pgvector) before answering any product question.
- **Voice agent** — Real-time voice support using OpenAI's Realtime API (WebRTC). Speaks and listens with sub-second latency.
- **RAG knowledge base** — Ingest any web page via Firecrawl; embeddings stored in PostgreSQL with pgvector and searched with HNSW cosine similarity.
- **Calendar booking** — Checks live availability via Google Calendar and books 30-minute support calls, sending the invite to the customer.
- **Escalation** — Records escalations in the database and posts a Slack notification to the support team.
- **Admin dashboard** — Password-protected panel to view conversation logs, escalations, and trigger knowledge base ingestion.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, uvicorn, uv |
| AI / LLM | OpenAI Agents SDK, OpenRouter, OpenAI Realtime API |
| Embeddings | OpenAI `text-embedding-3-small` + pgvector (HNSW) |
| Database | PostgreSQL 16 + pgvector |
| Scraping | Firecrawl |
| Notifications | Slack incoming webhooks |
| Calendar | Google Calendar API (OAuth2) |
| Infra | GCP — Cloud Run, Cloud SQL, Artifact Registry, Secret Manager |
| IaC | Terraform (modules for networking, Cloud SQL, backend, frontend) |
| CI/CD | GitHub Actions + Workload Identity Federation (keyless auth) |

---

## Running locally

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for the database)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Node.js 22+](https://nodejs.org/) and npm
- API keys — see [Environment variables](#environment-variables)

### 1. Start the database

```bash
docker compose up -d
```

This starts a PostgreSQL 16 + pgvector container on `localhost:5432`. The schema and HNSW index are created automatically when the backend starts.

### 2. Backend

```bash
cd backend
cp ../.env.example .env   # then fill in your API keys
uv sync
uv run uvicorn main:app --reload --port 8000
```

The API is now available at http://localhost:8000. Visit http://localhost:8000/docs for the interactive API docs.

### 3. Frontend

```bash
cd frontend
cp ../.env.example .env   # set VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

The UI is now available at http://localhost:5173.

### 4. Ingest the knowledge base

Once the backend is running, trigger ingestion from the admin panel or call the API directly:

```bash
curl -X POST http://localhost:8000/api/admin/ingest \
  -u admin:your_admin_password
```

This scrapes the configured URLs via Firecrawl, chunks the content, embeds it, and stores it in pgvector.

---

## Environment variables

Copy `.env.example` to `backend/.env` and `frontend/.env` and fill in the values.

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI — used for Realtime voice API and embeddings |
| `OPENROUTER_API_KEY` | OpenRouter — used for the chat LLM |
| `FIRECRAWL_API_KEY` | Firecrawl — used to scrape pages during ingestion |
| `DATABASE_URL` | PostgreSQL connection URL |
| `LLM_MODEL` | Chat model (default: `openai/gpt-4o-mini`) |
| `EMBED_MODEL` | Embedding model (default: `text-embedding-3-small`) |
| `TTS_VOICE` | Realtime voice (default: `alloy`) |
| `GOOGLE_CLIENT_ID` | Google Calendar OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google Calendar OAuth client secret |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | Long-lived refresh token — run `scripts/get_google_token.py` to obtain |
| `SUPPORT_EMAIL` | Email shown to customers when escalating |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for escalation notifications |
| `ADMIN_USERNAME` | Admin panel username (default: `admin`) |
| `ADMIN_PASSWORD` | Admin panel password |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (e.g. `http://localhost:5173`) |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend API URL, no trailing slash (e.g. `http://localhost:8000`) |

### Google Calendar setup

To enable calendar booking, you need a Google Cloud OAuth2 credential with the Calendar API enabled. Run the helper script to get a long-lived refresh token:

```bash
cd backend
uv run python scripts/get_google_token.py
```

Follow the browser prompt and paste the resulting token into `GOOGLE_OAUTH_REFRESH_TOKEN`.

---

## Project structure

```
.
├── backend/                  # FastAPI application
│   ├── agent/
│   │   ├── orchestrator.py   # OpenAI Agents SDK runner
│   │   ├── tools.py          # search_knowledge_base, calendar, escalate tools
│   │   ├── rag.py            # Embedding + HNSW vector search
│   │   ├── prompts.py        # System prompt
│   │   ├── calendar_service.py
│   │   └── notifier.py       # Slack notifications
│   ├── routers/
│   │   ├── chat.py           # POST /api/chat
│   │   ├── voice.py          # POST /api/voice/session (Realtime API)
│   │   └── admin.py          # Admin dashboard endpoints
│   ├── ingest/
│   │   └── firecrawl_loader.py  # Web scraping + chunking + embedding
│   ├── scripts/
│   │   └── get_google_token.py  # OAuth2 helper
│   ├── db.py                 # asyncpg pool, schema init, DB helpers
│   ├── config.py             # Environment variable loading
│   ├── main.py               # FastAPI app, CORS, rate limiting
│   └── Dockerfile
├── frontend/                 # React + Vite SPA
│   ├── src/
│   │   ├── components/       # Chat UI, Voice agent, Admin dashboard
│   │   └── App.tsx
│   ├── nginx.conf            # SPA routing for production
│   └── Dockerfile
├── terraform/                # GCP infrastructure as code
│   ├── modules/
│   │   ├── networking/       # VPC, Cloud SQL peering, VPC connector
│   │   ├── cloudsql/         # PostgreSQL 16 + pgvector
│   │   ├── backend/          # Cloud Run, Artifact Registry, Secret Manager, WIF
│   │   └── frontend/         # GCS bucket, Cloud Load Balancer, managed SSL
│   └── environments/
│       ├── dev/
│       ├── staging/
│       └── production/
├── .github/workflows/
│   ├── backend-deploy.yml    # CI/CD: build + push + deploy backend on push to main
│   └── frontend-deploy.yml   # CI/CD: build + upload frontend on push to main
└── docker-compose.yml        # Local dev — PostgreSQL + pgvector only
```

---

## Deployment

The app runs on **Google Cloud Platform**. Infrastructure is managed with Terraform and deployments are automated via GitHub Actions.

### Live URLs (dev environment)

| Service | URL |
|---|---|
| Frontend | https://relaypay-dev-frontend-845745374775.us-central1.run.app |
| Backend | https://relaypay-dev-api-2jyaqpkqda-uc.a.run.app |
| Health check | https://relaypay-dev-api-2jyaqpkqda-uc.a.run.app/health |

### Provisioning a new environment

```bash
cd terraform/environments/dev   # or staging / production
cp terraform.tfvars.example terraform.tfvars  # fill in values
terraform init
terraform apply
```

### GitHub Actions secrets required

Add these to **Settings → Secrets → Actions** in your GitHub repo:

| Secret | Description |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | WIF provider resource name (from Terraform output) |
| `GCP_SERVICE_ACCOUNT` | Backend deploy SA email |
| `FRONTEND_GCP_WORKLOAD_IDENTITY_PROVIDER` | Frontend WIF provider resource name |
| `FRONTEND_GCP_SERVICE_ACCOUNT` | Frontend deploy SA email |

### Admin dashboard

Visit `/admin` on the frontend URL and sign in with the credentials set in `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
