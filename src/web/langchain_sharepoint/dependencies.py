
import logging
from fastapi import Depends
from langgraph.graph import START, StateGraph
from langchain_postgres import PGVector
from web.dependencies import register_logger
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_sharepoint.client import SharepointApiClient
from web.langchain_sharepoint.ingest_service import IngestService
from web.langchain_sharepoint.tools import create_agent
from web.openai.dependencies import require_openai_setting
from web.openai.models import OpenAISetting
from web.persistence.dependencies import require_sql_engine_raw_uri

logger = register_logger("langchain_sharepoint", level=logging.DEBUG, log_filename="langchain_sharepoint")

_sharepoint_pg_vectorstore: PGVector = None
_sharepoint_client: SharepointApiClient = None
_ingest_service: IngestService = None

async def require_vector_store() -> PGVector:
    """
    FastAPI Dependencies method for getting the backend vector store

    Since
    --------
    0.0.3
    """
    return _sharepoint_pg_vectorstore

async def require_vector_repo(vector_store: PGVector = Depends(require_vector_store), async_engine_url = Depends(require_sql_engine_raw_uri)):
    """
    FastAPI Dependencies method for getting the backend vector repository

    Since
    --------
    0.0.3
    """
    return PGVectorRepo(vector_store, async_engine_url)

async def require_ingest_service() -> IngestService:
    """
    FastAPI Dependencies method for getting the sharepoint ingest service

    Since
    --------
    0.0.3
    """
    return _ingest_service

async def require_rag_agent(llm_setting: OpenAISetting = Depends(require_openai_setting)) -> StateGraph:
    # Set system prompt = None for using default prompt
    return create_agent(llm_setting, system_prompt=None)

def get_global_vector_store():
    """
    Since
    -----
    0.0.3
    """
    return _sharepoint_pg_vectorstore

def set_global_vector_store(confluence_pg_vectorstore: PGVector):
    """
    Since
    -----
    0.0.3
    """
    global _sharepoint_pg_vectorstore
    _sharepoint_pg_vectorstore = confluence_pg_vectorstore

def get_global_sharepoint_client():
    """
    Since
    -----
    0.0.3
    """
    global _sharepoint_client
    return _sharepoint_client

def set_global_sharepoint_client(sharepoint_client: PGVector):
    """
    Since
    -----
    0.0.3
    """
    global _sharepoint_client
    _sharepoint_client = sharepoint_client

def set_global_ingest_service(ingest_service: IngestService):
    """
    Since
    -----
    0.0.1
    """
    global _ingest_service
    _ingest_service = ingest_service
