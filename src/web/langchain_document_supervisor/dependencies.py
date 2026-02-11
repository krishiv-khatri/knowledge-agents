
import logging
from typing import Dict
from langgraph.graph import START, StateGraph
from web.dependencies import register_logger

registered_agent: Dict[str, StateGraph] = {}

logger = register_logger("langchain_doc_supervisor", level=logging.DEBUG, log_filename="langchain_doc_supervisor")

async def register_langchain_agent(name: str, agent_graph: StateGraph):
    """
    Since
    ------
    0.0.5
    """
    registered_agent[name] = agent_graph

async def require_doc_agent() -> StateGraph:
    """
    Since
    ------
    0.0.5
    """
    return registered_agent['document_agent']