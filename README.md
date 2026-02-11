A **multi-agent system** for knowledge retrieval, automated ticketing, progress reporting, and more Built with [FastAPI](https://fastapi.tiangolo.com/), [LangChain](https://www.langchain.com/), [LangGraph](https://langchain-ai.github.io/langgraph/), and [PostgreSQL + pgvector](https://github.com/pgvector/pgvector).

---

## What It Does

It connects to your organization's existing tools (Confluence, SharePoint, Jira) and provides a unified AI interface for:

- **Knowledge Retrieval (RAG)** - Ask natural-language questions about your Confluence wiki or SharePoint documents. The system retrieves relevant content using vector similarity search and generates accurate, grounded answers.
- **Jira Ticket Management** - Query, classify, create, and update Jira tickets through conversational AI. The Jira agent understands ticket context, comments, and status history.
- **Progress Reporting** - Automatically generates progress summaries from Jira ticket changelogs, tracking status transitions and team velocity over time.
- **Follow-Up Chasing** - Analyzes Jira comment threads to detect unanswered questions and generates polite follow-up reminders for tagged team members.
- **Multi-Agent Coordination** - A supervisor agent routes incoming queries to the appropriate specialist (Confluence, SharePoint, or Jira) and synthesizes responses.

## Why It's Useful

- **Eliminates context-switching**: Instead of searching across Confluence, SharePoint, and Jira separately, ask one question and get a consolidated answer.
- **OpenAI-compatible API**: Works with any tool that supports the OpenAI chat completions API (Open WebUI, ChatGPT clients, IDE extensions).
- **Self-hosted and private**: Runs entirely on your infrastructure. No data leaves your network.
- **Pluggable architecture**: Each integration is a self-contained module. Enable only what you need, or add new integrations.
- **Automated quality assurance**: Includes a RAG evaluation framework using [RAGAS](https://docs.ragas.io/) to measure answer quality with metrics like faithfulness, relevancy, and context precision.

---

## Architecture

```
                          +-------------------+
                          |   Client / UI     |
                          | (Open WebUI, API) |
                          +--------+----------+
                                   |
                          OpenAI-compatible API
                                   |
                     +-------------v--------------+
                     |    FastAPI Application      |
                     |                             |
                     |  +-----+ +-----+ +-------+ |
                     |  |OpenAI| |Lang-| |Sched- | |
                     |  |Proxy | |Chain| |uler   | |
                     |  +--+--+ +--+--+ +---+---+ |
                     +----|---------|---------+----+
                          |         |         |
             +------------+    +----+----+    +----------+
             |                 |         |               |
    +--------v------+  +------v---+ +---v--------+ +----v-------+
    |  Supervisor    |  |Confluence| | SharePoint | |   Jira     |
    |  Agent         |  |RAG Agent | | RAG Agent  | |   Agent    |
    | (LangGraph)    |  |(LangChain| |(LangChain) | |(LangGraph) |
    +----------------+  +----+-----+ +-----+------+ +----+-------+
                              |             |             |
                     +--------v-------------v------+ +----v-------+
                     | PostgreSQL + pgvector        | | Jira API   |
                     | (Vector embeddings store)    | | (REST)     |
                     +------------------------------+ +------------+
```

### Key Components

| Component | Path | Description |
|---|---|---|
| **Main App** | `src/main.py` | FastAPI entry point, router registration, middleware |
| **OpenAI Proxy** | `src/openai_proxy.py` | OpenAI-compatible `/chat/completions` endpoint |
| **Confluence Agent** | `src/web/langchain_confluence/` | RAG pipeline for Confluence wiki pages |
| **SharePoint Agent** | `src/web/langchain_sharepoint/` | RAG pipeline for SharePoint documents (.docx) |
| **Jira Agent** | `src/web/langchain_jira/` | Ticket queries, classification, progress reports |
| **Supervisor Agent** | `src/web/langchain_document_supervisor/` | Routes queries to the right sub-agent |
| **Scheduler** | `src/web/scheduler/` | APScheduler for periodic document ingestion |
| **Persistence** | `src/web/persistence/`, `src/db/` | Database session management, ORM models |
| **Config** | `conf/config.yml.sample` | YAML configuration template |

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **PostgreSQL** with the [pgvector](https://github.com/pgvector/pgvector) extension
- **An OpenAI-compatible LLM endpoint** (e.g., [vLLM](https://docs.vllm.ai/), [Ollama](https://ollama.com/), or OpenAI API)
- **An embeddings service** (e.g., vLLM serving `BAAI/bge-m3`, or OpenAI embeddings)

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/your-username/knowledge-agents.git
cd knowledge-agents

# Using uv (recommended)
pip install uv
uv sync

# Or using pip
pip install -r requirement.txt
```

### 2. Configure the Application

```bash
# Copy the config template
cp conf/config.yml.sample conf/config.yml

# Copy the environment variables template
cp .env.example .env
```

Edit `conf/config.yml` with your settings:
- **Database**: PostgreSQL host, port, credentials
- **Embeddings**: URL and model for your embeddings service
- **Confluence**: URL, email, API token (PAT)
- **Jira**: URL, API token (PAT), project components
- **SharePoint** (optional): URL, Azure AD credentials

Edit `.env` with your LLM API credentials:
```bash
OPENAI_API_BASE=http://localhost:8001/v1
OPENAI_API_KEY=your-api-key
```

### 3. Set Up the Database

Ensure PostgreSQL is running with pgvector:

```sql
CREATE DATABASE knowledge_agents;
\c knowledge_agents
CREATE EXTENSION IF NOT EXISTS vector;
```

Tables are auto-created on first startup via SQLAlchemy.

### 4. Create the Logs Directory

```bash
mkdir -p logs
```

### 5. Run the Application

```bash
# From the project root
python src/main.py

# Or with a custom config path
python src/main.py path/to/config.yml
```

The server starts at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive API documentation (Swagger UI).

### 6. Ingest Documents

Trigger Confluence document ingestion:
```bash
curl -X POST http://localhost:8000/api/v1/confluence/ingest
```

Or enable the scheduler in `config.yml` to auto-ingest on a cron schedule.

### 7. Query the System

```bash
# Ask a question via the RAG endpoint
curl -X POST http://localhost:8000/api/v1/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the steps to onboard a new participant?"}'

# Or use the OpenAI-compatible proxy
curl -X POST http://localhost:8000/openai/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "confluence_agent",
    "messages": [{"role": "user", "content": "What are the steps to onboard a new participant?"}],
    "stream": true
  }'
```

---

## Project Structure

```
knowledge-agents/
├── conf/                          # Configuration files
│   ├── config.yml.sample          # Template - copy to config.yml
│   └── logger.ini                 # Logging configuration
├── src/                           # Application source code
│   ├── main.py                    # FastAPI entry point
│   ├── openai_proxy.py            # OpenAI-compatible proxy
│   ├── sample.py                  # Standalone Jira query script
│   ├── common/                    # Shared utilities (HTTP client, Result type)
│   ├── db/                        # Database models and session management
│   └── web/                       # FastAPI modules
│       ├── dependencies.py        # Bootstrap, hooks, logger registration
│       ├── langchain/             # Generic LangChain agent framework
│       ├── langchain_confluence/  # Confluence RAG integration
│       ├── langchain_sharepoint/  # SharePoint RAG integration
│       ├── langchain_jira/        # Jira agent integration
│       ├── langchain_document_supervisor/  # Multi-agent supervisor
│       ├── openai/                # OpenAI settings management
│       ├── persistence/           # Database dependency injection
│       └── scheduler/             # APScheduler for periodic jobs
├── tests/                         # Test suite
│   ├── conftest.py                # Pytest fixtures and HTML report hooks
│   ├── test_rag.py                # RAG evaluation tests (RAGAS metrics)
│   └── create_test_set.py         # Auto-generate test queries from documents
├── examples/                      # Sample data and configuration
│   ├── sample_test_set.json       # Example test set format
│   ├── sample_agent_config.json   # Example agent config
│   └── README.md                  # Examples documentation
├── docs/                          # Additional documentation
│   └── SHAREPOINT.md              # SharePoint setup guide
├── assets/                        # Static assets (CSS for test reports)
├── .env.example                   # Environment variables template
├── .gitignore
├── pyproject.toml                 # Python project metadata and dependencies
├── requirement.txt                # Pip requirements (alternative to uv)
└── README.md                      # This file
```

---

## Testing

### RAG Evaluation

The test suite evaluates RAG quality using [RAGAS](https://docs.ragas.io/) metrics:

- **Answer Relevancy** - Is the answer relevant to the question?
- **Faithfulness** - Is the answer grounded in the retrieved documents?
- **Context Precision** - Are the retrieved documents relevant?
- **Context Recall** - Are all relevant documents retrieved?
- **Context Entity Recall** - Are key entities from ground truth present?

```bash
# Run tests with HTML report
pytest tests/test_rag.py --html=report.html -v

# Run with a specific test set
# Place your test set at tests/data/test_set.json (see examples/sample_test_set.json for format)
```

### Generating Test Data

```bash
# Auto-generate test queries from your ingested documents
# Requires OPENAI_API_KEY, OPENAI_API_BASE, and database credentials in .env
python tests/create_test_set.py
```

---

## Configuration Reference

See `conf/config.yml.sample` for the complete configuration template with inline comments. Key sections:

| Section | Purpose |
|---|---|
| `fastapi` | Server port, CORS origins |
| `db` | PostgreSQL connection (host, port, credentials) |
| `embeddings` | Embeddings service URL and model |
| `confluence` | Confluence URL, PAT, space keys, ingestion schedule |
| `jira` | Jira URL, PAT, project components, VLM model |
| `sharepoint` | SharePoint URL, Azure AD credentials, document paths |
| `scheduler` | Enable/disable periodic ingestion |

---

## Typical Use Cases

1. **Internal Knowledge Base Q&A** - Connect Confluence and let teams ask questions about processes, architecture, and runbooks.
2. **Automated Ticket Triage** - Use the Jira agent to classify incoming tickets by component, priority, and type.
3. **Sprint Progress Summaries** - Generate daily/weekly progress reports from Jira ticket status changes.
4. **Follow-Up Automation** - Detect stale conversations in Jira comments and auto-generate reminder messages.
5. **Document Search Across Silos** - Unify search across Confluence, SharePoint, and Jira in a single conversational interface.

---

## Contributing

Contributions are welcome! To get started:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests if applicable.
4. Submit a pull request.

Please ensure:
- No credentials or company-specific data in commits.
- New integrations follow the existing module pattern (`src/web/langchain_*/`).
- Configuration uses `config.yml` or environment variables, never hardcoded values.

---

## License

This project is provided as-is for educational and demonstration purposes.
