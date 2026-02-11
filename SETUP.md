# Setup Guide

Detailed instructions for setting up Knowledge Agents on your local machine or server.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Python Environment](#python-environment)
3. [PostgreSQL + pgvector](#postgresql--pgvector)
4. [LLM / Embeddings Service](#llm--embeddings-service)
5. [Application Configuration](#application-configuration)
6. [Running the Application](#running-the-application)
7. [Integration Setup](#integration-setup)
8. [Troubleshooting](#troubleshooting)

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.10+ | 3.11+ |
| PostgreSQL | 14+ (with pgvector) | 16+ |
| RAM | 4 GB | 8+ GB |
| GPU (optional) | - | NVIDIA GPU for local LLM inference |

---

## Python Environment

### Option A: Using `uv` (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager.

```bash
# Install uv
pip install uv

# Create virtual environment and install dependencies
uv venv
uv sync
```

### Option B: Using `pip`

```bash
python -m venv .venv

# On Linux/macOS
source .venv/bin/activate

# On Windows
.venv\Scripts\activate

pip install -r requirement.txt
```

---

## PostgreSQL + pgvector

### Install PostgreSQL

Follow the [official guide](https://www.postgresql.org/download/) for your OS.

### Install pgvector Extension

```bash
# Ubuntu/Debian
sudo apt install postgresql-16-pgvector

# macOS (Homebrew)
brew install pgvector

# Or build from source: https://github.com/pgvector/pgvector#installation
```

### Create the Database

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create the database
CREATE DATABASE knowledge_agents;

-- Connect to it
\c knowledge_agents

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;
```

The application auto-creates all required tables on first startup using SQLAlchemy's `create_all()`.

---

## LLM / Embeddings Service

The application requires two AI services:

### 1. Chat/Completion LLM

Any OpenAI-compatible API. Examples:

- **[vLLM](https://docs.vllm.ai/)** (recommended for self-hosted):
  ```bash
  vllm serve Qwen/Qwen3-32B-AWQ --port 8001
  ```
- **[Ollama](https://ollama.com/)**:
  ```bash
  ollama serve
  ```
- **OpenAI API**: Use `https://api.openai.com/v1` as the base URL.

### 2. Embeddings Service

An endpoint serving vector embeddings. The default model is `BAAI/bge-m3`.

- **vLLM** can serve embeddings:
  ```bash
  vllm serve BAAI/bge-m3 --port 8002
  ```
- **OpenAI API**: Use `text-embedding-3-small` or similar.

Set the endpoints in `conf/config.yml`:

```yaml
embeddings:
  base_url: http://localhost:8002/v1
  api_key: dummy  # "dummy" if no auth needed
  model: BAAI/bge-m3
```

---

## Application Configuration

### Step 1: Copy Templates

```bash
cp conf/config.yml.sample conf/config.yml
cp .env.example .env
```

### Step 2: Edit `conf/config.yml`

This is the main configuration file. Key sections to update:

```yaml
# Database connection
db:
  host: localhost
  port: 5432
  db: knowledge_agents
  user: your_db_user
  password: "your_db_password"

# Embeddings service
embeddings:
  base_url: http://localhost:8002/v1
  model: BAAI/bge-m3

# Confluence (if using)
confluence:
  url: https://confluence.yourcompany.com
  email: your_email@yourcompany.com
  api_token: your_confluence_pat

# Jira (if using)
jira:
  url: https://jira.yourcompany.com
  api_token: your_jira_pat
```

### Step 3: Edit `.env`

Environment variables for the LLM and standalone scripts:

```bash
OPENAI_API_BASE=http://localhost:8001/v1
OPENAI_API_KEY=your-api-key

JIRA_BASE_URL=https://jira.yourcompany.com
JIRA_API_TOKEN=your-jira-pat
```

### Step 4: Create Required Directories

```bash
mkdir -p logs data/sharepoint data/func_spec
```

---

## Running the Application

```bash
# Start the server (default config path: conf/config.yml)
python src/main.py

# Or specify a custom config
python src/main.py /path/to/config.yml
```

The server will:
1. Load configuration from YAML
2. Initialize logging
3. Connect to PostgreSQL and auto-create tables
4. Register all API routers
5. Start the scheduler (if enabled)
6. Listen on `http://0.0.0.0:8000`

Visit `http://localhost:8000/docs` for interactive API docs.

---

## Integration Setup

### Confluence

1. Generate a [Personal Access Token](https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html) in your Confluence instance.
2. Add it to `conf/config.yml` under `confluence.api_token`.
3. Set the space key(s) to ingest under `confluence.rag[].space`.
4. Start the app and trigger ingestion via:
   ```bash
   curl -X POST http://localhost:8000/api/v1/confluence/ingest
   ```

### Jira

1. Generate a Personal Access Token in your Jira instance.
2. Add it to `conf/config.yml` under `jira.api_token`.
3. List the project components you want to track under `jira.cron.components`.
4. The Jira agent is available at `POST /api/v1/jira`.

### SharePoint

See [docs/SHAREPOINT.md](docs/SHAREPOINT.md) for the complete setup guide including Azure AD app registration.

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` | Ensure you activated the virtual environment and installed dependencies |
| Database connection refused | Check that PostgreSQL is running and credentials in `config.yml` are correct |
| `pgvector` extension not found | Run `CREATE EXTENSION IF NOT EXISTS vector;` in your database |
| LLM timeout errors | Check that your LLM endpoint is reachable at the configured `OPENAI_API_BASE` |
| Empty RAG responses | Ensure documents have been ingested. Check `logs/system.log` for ingestion errors |
| SSL errors with Jira/Confluence | The code uses `verify=False` for self-signed certs. For production, configure proper SSL |

### Checking Logs

```bash
# Application logs
tail -f logs/system.log

# Component-specific logs
tail -f logs/langchain_jira.log
tail -f logs/proxy.log
```

### Verifying the Setup

```bash
# Check the server is running
curl http://localhost:8000/

# Expected response:
# {"Module": "Knowledge Agents", "Version": "0.0.10"}
```
