import logging
from typing import Dict, Tuple
import warnings
from fastapi import Depends
from langchain_postgres import PGVector
from langchain_core.runnables import Runnable
from langgraph.graph import START, StateGraph
from web.dependencies import register_logger
from web.langchain_confluence.client import ConfluenceApiClient
from web.langchain_confluence.ingest_service import IngestService
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_confluence.tools import create_agent
from web.persistence.dependencies import require_sql_engine_raw_uri
from web.openai.dependencies import require_openai_setting
from web.openai.models import OpenAISetting

logger = register_logger("langchain_confluence", level=logging.DEBUG, log_filename="langchain_conference")

_confluence_pg_vectorstore: PGVector = None
_confluence_client: ConfluenceApiClient = None
_ingest_service: IngestService = None
_confluence_summaries_langchain: Runnable = None

_registered_ingest_service: Dict[str, IngestService] = {}

async def require_default_vector_store() -> PGVector:
    """
    FastAPI Dependencies method for getting the default backend vector store

    Since
    --------
    0.0.1 (Renamed at 0.0.10)
    """
    return _confluence_pg_vectorstore

async def require_vector_repo(vector_store: PGVector = Depends(require_default_vector_store), async_engine_url = Depends(require_sql_engine_raw_uri)):
    """
    FastAPI Dependencies method for getting the backend vector repository

    Since
    --------
    0.0.1
    """
    return PGVectorRepo(vector_store, async_engine_url)

async def require_confluence_client() -> ConfluenceApiClient:
    """
    Since
    --------
    0.0.1
    """
    return _confluence_client

async def require_ingest_service() -> IngestService:
    """
    Since
    --------
    0.0.1
    """
    return _ingest_service

def require_all_registered_ingest_service() -> Tuple[str, IngestService]:
    """
    Since
    --------
    0.0.10
    """
    return _registered_ingest_service.items()

async def require_page_summaries_langchain() -> Runnable:
    """
    Since
    --------
    0.0.7
    """
    return _confluence_summaries_langchain

async def require_rag_agent(llm_setting: OpenAISetting = Depends(require_openai_setting)) -> StateGraph:
    # Set system prompt = None for using default prompt
    return await create_agent(llm_setting, system_prompt=None)

def get_global_vector_store():
    """
    Since
    -----
    0.0.1
    """
    return _confluence_pg_vectorstore

def set_global_vector_store(confluence_pg_vectorstore: PGVector):
    """
    Since
    -----
    0.0.1
    """
    global _confluence_pg_vectorstore
    _confluence_pg_vectorstore = confluence_pg_vectorstore

def get_global_confluence_client():
    """
    Since
    -----
    0.0.1
    """
    return _confluence_client

def set_global_confluence_client(confluence_client: PGVector):
    """
    Since
    -----
    0.0.1
    """
    global _confluence_client
    _confluence_client = confluence_client

def set_global_ingest_service(ingest_service: IngestService):
    """
    Since
    -----
    0.0.1
    """
    warnings.warn("Deprecated at 0.0.10 after support multiple ingest service", DeprecationWarning)
    global _ingest_service
    _ingest_service = ingest_service

async def register_ingest_service(space: str, ingest_service: IngestService):
    """
    Since
    --------
    0.0.10
    """
    global _registered_ingest_service
    _registered_ingest_service[space] = ingest_service

async def get_ingest_service(space: str):
    """
    Since
    --------
    0.0.10
    """
    global _registered_ingest_service
    print(_registered_ingest_service)
    return _registered_ingest_service.get(space)

def set_global_page_summaries_langchain(langchain: Runnable):
    """
    Since
    -----
    0.0.7
    """
    global _confluence_summaries_langchain
    _confluence_summaries_langchain = langchain
