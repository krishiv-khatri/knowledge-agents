from typing import Dict, Union
from pydantic import BaseModel, ConfigDict, Field
from langgraph.graph.graph import CompiledGraph

class AgentRegistryConfiguration(BaseModel):
    """
    Since
    --------
    0.0.10
    """    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    organization: str = Field(title="The agent organization")
    """
    The agent organization

    Since
    --------
    0.0.10
    """
    agent_name: str = Field(title="The agent name")
    """
    The agent name that exposed to the client

    Since
    --------
    0.0.10
    """
    chain_or_graph: Union[CompiledGraph] = Field(title="The langchain or langgraph")
    """
    Since
    --------
    0.0.10
    """
    extra_config: Dict = Field(title="The extra configuration that pass into", default={})
    """
    Since
    --------
    0.0.10
    """