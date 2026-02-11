from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class ChatCompletionRequest(BaseModel):
    """
    The incoming request for the Jira agent

    Since
    --------
    0.0.5
    """
    key: str = Field(title="The issue key")
    fields: Optional[List[Literal['description','type', "priority", "component", "labels"]]] = Field(title="The fields you want to update. Leave empty to update all.", default=None)

class AgentCompletionRequest(BaseModel):
    """
    The incoming request for the Jira agent

    Since
    --------
    0.0.5
    """
    question: str = Field(title="The user query")

class JiraTags(BaseModel):
    """Fixed set of tags for ticket classification"""
    issuetype: Literal["Bug", "Story", "Epic", "Improvement", "Task"] = Field(
        description="The type of the ticket"
    )
    priority: Literal["Blocker", "High", "Medium", "Low", "Minor"] = Field(
        description="The degree of priority of the ticket"
    )
    components: List[Literal["AI", "Database", "DevOps n Tools", "Drop Copy", "HA n Resiliency", "LCH", "MDP", "Monitoring", "NMS", "Ops Dashboard", "Performance n Capacity", "RPS n Quants", "RTFP", "Site Synchronization", "Website", "Platform Core Components"]] = Field(
        description="The dominant component(s) the ticket belongs to."
    )
    # business_unit_owner: Literal["BD", "Dev", "Infra", "IT Support", "Ops", "Product", "Quant", "Surveillence"] = Field(
    #     description="The business owner of the ticket"
    # )
    labels: list[str] = Field(description=(
        "Associated labels for the ticket. Choose from: "
        "Vendor, NCM, Conformance, release_tagged, qa_verified, incident_triaged, "
        "New_Starter, qa_elligible, Version_1, 1.1.0-pre, EXT, ITE, LCH, "
        "InternalBusinessTesting, DR. If none apply, generate a new concise label."
        )
    )

class QueryResponsePayload(BaseModel):
    query: str
    response: str
    user_email: Optional[str]
