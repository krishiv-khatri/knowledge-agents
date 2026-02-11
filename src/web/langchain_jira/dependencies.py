import logging
from datetime import datetime
from typing import TypedDict
from fastapi import Depends
from langchain_core.runnables import Runnable
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import create_react_agent
from web.dependencies import register_logger
from web.persistence.dependencies import require_async_sql_engine, require_sql_engine_raw_uri
from web.openai.dependencies import require_openai_setting
from web.openai.models import OpenAISetting
from web.langchain.util import create_langchain_openai_stub
from web.langchain_jira.client import JiraApiClient
from web.langchain_jira.ingest_service import IngestService
from web.langchain_jira.repo import JiraFollowupRepo, JiraRepo
from web.langchain_jira.tools import create_image_langgraph, create_progress_langgraph, jira_issue_retrieve_tool, jira_activity_summary_tool, jira_issue_classify_tool, jira_group_status_summary_tool, create_jira_issue_tool

_jira_client: JiraApiClient = None
_ingest_service: IngestService = None
_jira_image_langgraph: Runnable = None

logger = register_logger("langchain_jira", level=logging.DEBUG, log_filename="langchain_jira")

async def require_jira_repo(async_engine_url = Depends(require_sql_engine_raw_uri)):
    """
    FastAPI Dependencies method for getting the backend vector repository

    Since
    --------
    0.0.6
    """
    return JiraRepo(async_engine_url, logger)

async def require_jira_follow_up_repo(async_engine = Depends(require_async_sql_engine)):
    """
    FastAPI Dependencies method for getting the JIRA follow-up repo

    Since
    --------
    0.0.7
    """
    return JiraFollowupRepo(async_engine)

async def require_ingest_service() -> IngestService:
    """
    Since
    --------
    0.0.6
    """
    return _ingest_service



# Define state for application
class State(TypedDict):
    question: str
    tickets: dict
    date: str
    yesterday: str
    today: str


async def require_jira_agent(llm_setting: OpenAISetting = Depends(require_openai_setting)) -> StateGraph:
    system_prompt = f"""
        You are a Jira Agent designed to help users interact with Jira tickets and manage sprint progress for functional groups. Follow these instructions:

        1. Understand the User’s Request
            If the user provides a Jira issue key:
                - Extract and validate the key. The correct format is <PROJECT>-<NUMBER> (e.g., PROJ-1234).
                - Allowed projects should be configured in your environment.
                - If the key is incorrectly formatted (e.g., missing dash, lowercase, or space instead of dash), correct it.
                - If the project code is not allowed, respond: “This project does not exist.”
                - If the key is missing or invalid, respond: “Please provide the Jira ticket key in the format PROJECT-123.”

            If the user refers to a functional group/component:
                - Identify the group/component from the allowed list:
                  AI, Database, DevOps n Tools, Drop Copy, HA n Resiliency, LCH, MDP, Monitoring, NMS, Ops Dashboard, Performance n Capacity, RPS n Quants, RTFP, Site Synchronization, Website, Platform Core Components.
                - If the group/component is not recognized, respond: “Please provide a valid functional group/component.”

        2. Route the Request
            Ticket-related requests:
                - If the user asks for information about a ticket (e.g., "Show me details for PROJECT-123" or "What is PROJECT-123 about?") or a summary of it, use the retrieval tool to get the ticket's title, description, and comments.
                - If the user asks for a summary of activity, status or updates on a ticket (e.g., "Can you summarize updates on PROJECT-123?" or "What has changed in PROJECT-123?"), use the summarization/update tool.
                - If the user asks for classification or categorization (e.g., "Classify PROJECT-123" or "What type of ticket is PROJECT-123?"), use the classification tool.
                - For classification, always return only a valid JSON object as specified by the tool. Do not add any extra commentary or formatting.
                - If the user requests to create a new Jira ticket, use the create_jira_issue_tool.
                  When returning the result of this tool, always output a clear, readable preview of the ticket that was created, including its key, project, issue type, summary, and description. Do not return raw JSON for ticket creation.
                - For the the jira_create_ticket tool make sure you format each field EXACTLY as defined by the schema and consistant with JIRA conventions.
            
            Functional group/component requests:
                - Use the jira_group_status_summary_tool to generate clear, concise daily summaries or status reports for the specified group/component.

        3. If you are unsure which tool to use, select the one that most closely matches the user's intent, or ask the user for clarification.
        4. Never answer user queries directly. Always use the appropriate tool and return its output as instructed.
        5. If the tool provides format instructions or a required output structure, strictly follow them.
        6. If the user's request cannot be fulfilled due to missing or invalid information, respond with a clear instruction on what is needed.

        General Rules
            - Always follow any format or output structure required by the tools.
            - Do not speculate or include information not present in the ticket or component data.
            - If information is missing or unclear, ask the user for the necessary details.
            - Keep all responses factual, objective, and professional.
            - Do not add explanations, commentary, or formatting beyond what is required by the tools.

        For reference, today's date is {str(datetime.now().date())}

        /nothink
        """

    chat_openai = create_langchain_openai_stub(llm_setting, streaming=False)

    agent = create_react_agent(
        model=chat_openai,
        prompt=system_prompt,
        name="jira_agent",
        tools=[jira_issue_retrieve_tool, jira_activity_summary_tool, jira_issue_classify_tool, create_jira_issue_tool, jira_group_status_summary_tool],
        version='v1'
    )

    return agent

async def require_progress_langgraph(llm_setting: OpenAISetting = Depends(require_openai_setting)) -> StateGraph:
    """
    Since
    -----
    0.0.6 (Improved from 0.0.5)
    """
    return await create_progress_langgraph(llm_setting)

async def require_image_langgraph(llm_setting: OpenAISetting = Depends(require_openai_setting)) -> StateGraph:
    """
    Since
    -----
    0.0.8
    """
    return _jira_image_langgraph

def set_global_jira_client(jira_client: JiraApiClient):
    """
    Since
    -----
    0.0.6
    """
    global _jira_client
    _jira_client = jira_client

def set_global_ingest_service(ingest_service: IngestService):
    """
    Since
    -----
    0.0.6
    """
    global _ingest_service
    _ingest_service = ingest_service

def set_global_image_langgaraph(image_langgraph: StateGraph):
    """
    Since
    -----
    0.0.8
    """
    global _jira_image_langgraph
    _jira_image_langgraph = image_langgraph