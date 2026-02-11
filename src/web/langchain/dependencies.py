import logging
import os
from typing import Dict, Tuple
from web.dependencies import register_logger
from web.langchain.schemas import AgentRegistryConfiguration
from langgraph.graph.graph import CompiledGraph

logger = register_logger("LangchainAIService", level=logging.DEBUG, log_filename="langchain")
"""
The logger

Since
--------
0.0.10
"""

_default_organization = os.environ.get('USER') if os.environ.get('AGENT_PROVIDER') is None else os.environ.get('AGENT_PROVIDER')
_registered_agents: Dict[str, AgentRegistryConfiguration] = {}

async def register_langchain_agent(agent_name: str, chain_or_graph: CompiledGraph, extra_config: Dict = {}):
    """
    Since
    --------
    0.0.10
    """
    full_qualified_agent_name = f"{_default_organization}/{agent_name}"
    _registered_agents[full_qualified_agent_name] = AgentRegistryConfiguration(organization=_default_organization, agent_name=agent_name, chain_or_graph=chain_or_graph, extra_config=extra_config)

async def get_langchain_agent(full_qualified_agent_name: str):
    """
    Since
    --------
    0.0.10
    """
    return _registered_agents.get(full_qualified_agent_name)

def get_all_registered_agents() -> Tuple[str, AgentRegistryConfiguration]:
    """
    Since
    --------
    0.0.10
    """
    return _registered_agents.items()