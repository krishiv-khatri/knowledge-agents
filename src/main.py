"""
Main Application Entry Point

This is the FastAPI application that orchestrates multiple AI agents for:
  - Knowledge retrieval from Confluence and SharePoint (RAG)
  - Jira ticket management, classification, and progress reporting
  - Multi-agent coordination via a supervisor agent

Architecture Overview:
  - FastAPI serves as the HTTP layer, exposing REST + SSE streaming endpoints.
  - Each integration (Confluence, Jira, SharePoint) is a self-contained module
    under src/web/ with its own routes, dependencies, and services.
  - LangChain + LangGraph provide the AI/LLM orchestration layer.
  - PostgreSQL + pgvector stores document embeddings for vector similarity search.
  - A scheduler (APScheduler) handles periodic ingestion jobs.

Data Flow:
  1. Documents are ingested from Confluence/SharePoint into pgvector.
  2. User queries arrive via REST API or OpenAI-compatible proxy.
  3. The supervisor agent routes queries to the appropriate sub-agent.
  4. Sub-agents use RAG (retrieval-augmented generation) or Jira APIs to respond.
  5. Responses are streamed back to the client in SSE format.
"""

import logging
import platform
import sys
import time
import traceback

from ruamel.yaml import YAML
from pydantic_yaml import parse_yaml_file_as

from typing import Dict, List
from fastapi import Depends, FastAPI, Request, Response
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
import sqlalchemy
import uvicorn

from web.dependencies import bootstrap, init_logger_config, register_logger
from web.doc import default_response
from web.exception_handler import register_app_exception_handler

TITLE = "Knowledge Agent"
VERSION = "0.0.10"

config: Dict = None

app: FastAPI = None

def set_global_config(input_config: Dict):
    global config
    config = input_config

@asynccontextmanager
async def global_startup(app: FastAPI):
    """
    Since
    ------
    0.0.1
    """
    try:
        await bootstrap(config)
    except Exception as e:
        print(str(e))
        traceback.print_exception(e)
    yield


# The entry point of the API
try:
    app = FastAPI(
        title=TITLE,
        version=VERSION,
        lifespan=global_startup,
        responses=default_response,
        redoc_url=None,
    )
except Exception as e:
    logging.error("ERROR during initialization", e)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    Since
    ------
    0.0.1
    """
    try:
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["x-Backend-TTime"] = str(process_time * 1000)
        return response
    except Exception as e:
        # you probably want some kind of logging here
        logging.error("Unable to add process time header", exc_info=True)
        return Response("Internal server error", status_code=500)


sys_tags = ["system"]

@app.get("/", tags=sys_tags)
def get_version():
    """
    Since
    ------
    0.0.1
    """
    return {"Module": "Knowledge Agent", "Version": VERSION}

if __name__ == "__main__":
    """
    Since
    ------
    0.0.1
    """
    config_path = "conf/config.yml"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    yaml = YAML(typ="safe")
    with open(config_path, "r") as f:
        config = yaml.load(f)

    logging_config: Dict[str, any] = config["logger"]
    logging_config_path = logging_config.get("config", "conf/logging.ini")
    logging_base_path = logging_config.get("base_path", "logs")

    init_logger_config(logging_config_path, logging_base_path)

    l = register_logger("system")

    l.info(f"System start")
    l.info(f"Operation System {platform.system()}")
    l.info(f"Using configuration {config}")
    l.info(f"Using sqlalchemy {sqlalchemy.__version__}")

    fastapi_config: Dict[str, any] = config["fastapi"]
    fastapi_listen_port = fastapi_config.get("listen_port", 8000)

    cors = config["fastapi"]["cors"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========================= Core Services ==========================================
    # These modules are always loaded. They set up the database, ORM models,
    # and the background scheduler that drives periodic ingestion jobs.

    from web.openai import models as openai_model       # ORM models for LLM settings
    from web.persistence import route as persistence_route  # Database session management
    from web.scheduler import dependencies               # APScheduler initialization

    # ========================= Agent / Integration Routers ===========================
    # Each router adds REST endpoints for a specific integration.
    # Comment out any integration you don't need.

    # OpenAI settings management API
    from web.openai import route as openai_route
    app.include_router(openai_route.router)

    # LangChain agent API (generic agent interface)
    from web.langchain import route as langchain_route
    app.include_router(langchain_route.router)

    # Confluence RAG API (knowledge retrieval from Confluence wiki)
    from web.langchain_confluence import route as confluence_route
    app.include_router(confluence_route.router)

    # SharePoint RAG API (knowledge retrieval from SharePoint documents)
    from web.langchain_sharepoint import route as sharepoint_route
    app.include_router(sharepoint_route.router)

    # Supervisor Agent API (multi-agent coordinator that routes to sub-agents)
    from web.langchain_document_supervisor import route as supervisor_route
    app.include_router(supervisor_route.router)

    # Jira Agent API (ticket queries, progress reports, follow-up chasing)
    from web.langchain_jira import route as jira_route
    app.include_router(jira_route.router)

    # ========================= End of Routers ========================================

    
    register_app_exception_handler(app)
    uvicorn.run(app, port=fastapi_listen_port, host="0.0.0.0")
