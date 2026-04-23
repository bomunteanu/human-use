# human-use

MCP server that connects AI agents to the [Rapidata](https://rapidata.ai) human intelligence API. Also ships a web research agent with a React + FastAPI frontend for running surveys, asking clarifying questions, and generating AI reports backed by real human responses.

## What it does

- **MCP server** — exposes Rapidata survey tools to any MCP-compatible AI agent (Claude Desktop, Cursor, etc.)
- **Web research agent** — chat UI where you ask a research question and Claude automatically dispatches Rapidata surveys, polls for results, and compiles a PDF research brief
- **Demographic targeting** — filter respondents by country, language, age group, or gender

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | ≥ 3.11 |
| Node.js | ≥ 18 |
| uv | any recent |
| Docker + Compose | for the all-in-one setup |

---

## Credentials

You need API keys from three services:

| Variable | Where to get it |
|---|---|
| `RAPIDATA_CLIENT_ID` | [app.rapidata.ai](https://app.rapidata.ai) → Settings → API Keys |
| `RAPIDATA_CLIENT_SECRET` | same page |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `JWT_SECRET` | any long random string, e.g. `openssl rand -hex 32` |
| `DATABASE_URL` | Postgres connection string (auto-set in Docker Compose) |

Copy `.env.example` and fill in your values:

```bash
cp .env.example .env
# then edit .env
```

Full `.env` file:

```
RAPIDATA_CLIENT_ID=...
RAPIDATA_CLIENT_SECRET=...
ANTHROPIC_API_KEY=...
JWT_SECRET=...
DATABASE_URL=postgresql+asyncpg://humanuse:humanuse@localhost:5432/humanuse
```

---

## Quickstart — Docker Compose (recommended)

Starts the frontend, backend, and Postgres in one command:

```bash
docker compose up --build
```

- Frontend: http://localhost:80
- Backend API: http://localhost:8000

Register an account on the login page, then start asking research questions.

---

## Local development

### 1. Start Postgres only

```bash
docker compose up -d db
```

### 2. Run the backend

```bash
uv run uvicorn human_use.api:app --reload
```

### 3. Run the frontend

```bash
cd frontend && npm install && npm run dev
```

Frontend runs on http://localhost:5173 by default.

---

## MCP server

To use the survey tools directly inside an AI agent (Claude Desktop, Cursor, etc.):

```bash
uv run human-use
```

### MCP client config

Add this to your MCP client's config file (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "human-use": {
      "command": "uv",
      "args": ["--directory", "/path/to/human-use", "run", "human-use"]
    }
  }
}
```

Use the full path to `uv` if the client can't find it (e.g. `/Users/you/.local/bin/uv`).

### Available tools

| Tool | Description |
|---|---|
| `ask_clarifying_question` | Ask the user a multiple-choice question (web frontend only) |
| `ask_free_text` | Collect free-text responses from real humans |
| `ask_multiple_choice` | Run a multiple-choice survey (max 8 options) |
| `compare` | A/B test two text options |
| `rank` | Rank a list of items by preference |
| `check_progress` | Poll an order for completion status |
| `get_results` | Fetch final results for a completed order |

All dispatch tools (`ask_*`, `compare`, `rank`) accept an optional `targeting` argument to filter respondents by country, language, age group, or gender.

---

## Running tests

```bash
uv run pytest
```

No real API calls are made — Rapidata and Anthropic clients are fully mocked.

---

## Project structure

```
src/human_use/   # Python backend
frontend/src/    # React frontend
tests/           # pytest test suite
alembic/         # DB migrations
docker-compose.yml
```

See `CLAUDE.md` for detailed architecture documentation.
