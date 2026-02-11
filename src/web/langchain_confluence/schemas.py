from typing import List, Literal
from pydantic import BaseModel, Field

class ChatCompletionRequest(BaseModel):
    """
    The incoming request for the chat completion

    Since
    --------
    0.0.1
    """
    messages: str = Field(title="The messages")
    """
    Since
    --------
    0.0.1
    """
    # agent: Literal['rag','agentic-rag'] = Field(title="The agent you want to use for the chat completion", default="agentic-rag")
    

class IngressRequest(BaseModel):

    space: str = Field(title="The confluence space you want to re-ingress the whole thing")
    """
    Since
    --------
    0.0.1
    """
    gen_summary: bool = Field(title="", default=True)
    """
    Whether generate the summary of each confluence page. Enabling summary generation takes more times for ingress but it provide
    boarder context to LLM to generate the final answer

    Since
    --------
    0.0.1

    """

class ConfluenceV2AgentConfig(BaseModel):
    name: str = Field(title="Agent name")
    """
    Since
    --------
    0.0.10
    """
    include_sharepoint: bool = Field(title="Whether include sharepoint hand-off agent", default=False)
    """
    Since
    --------
    0.0.10
    """

class ConfluenceV2IngestConfig(BaseModel):
    enabled: bool = Field(title="Whether the ingest is enabled or not")    
    """
    Since
    --------
    0.0.10
    """
    default: Optional[bool] = Field(title="Whether it is default ingest service, for backward compatibility only.", default=False)
    """
    Since
    --------
    0.0.10
    """
    limit: int = Field(default=250)
    """
    Since
    --------
    0.0.10
    """    
    cron_expression: Optional[str] = Field(title="The cron expression how long it will perform re-ingest again in the following representation", default='')
    """
    The cron expression how long it will perform re-ingest again in the following representation
    
    <minutes> <hour> <day of the month> month (1-12) day of the week (0- 6)

    Since
    --------
    0.0.10
    """
class ConfluenceV2RagConfig(BaseModel):
    
    space: str = Field(title="The confluence target space for RAG", description="Example space like TEC, SUP, OP")
    """
    Since
    --------
    0.0.10
    """
    default: Optional[bool] = Field(title="Whether it is default vectorstore, for backward compatibility only.", default=False)
    """
    Since
    --------
    0.0.10
    """
    vectorstore_collection_name: str = Field(title="The langchain vector collection name")
    """
    Since
    --------
    0.0.10
    """
    agent: Optional[ConfluenceV2AgentConfig] = Field(title="The agent configuration for this rag", default=None)
    """
    Since
    --------
    0.0.10
    """
    ingest: ConfluenceV2IngestConfig = Field(title="The ingest configuration for this space")
    """
    Since
    --------
    0.0.10
    """

class ConfluenceV2Config(BaseModel):
    version: str = Field(title="The version")
    """
    Since
    --------
    0.0.10
    """
    url: str = Field(title="The target confluence URL")
    """
    Since
    --------
    0.0.10
    """
    api_token: str = Field(title="The API token for accessing confluence")
    """
    Since
    --------
    0.0.10
    """
    email: str = Field(title="The email which own the API token")
    """
    Since
    --------
    0.0.10
    """
    rags: List[ConfluenceV2RagConfig] = Field(title="A set of RAG configuration")
    """
    Since
    --------
    0.0.10
    """