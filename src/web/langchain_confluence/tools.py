import logging
import traceback
from typing import List
from html2text import html2text
from pydantic import BaseModel, Field
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig, Runnable
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt import create_react_agent
from langgraph.graph import START, StateGraph
from web.dependencies import register_logger
from web.langchain.util import create_langchain_openai_stub
from web.langchain_confluence.client import ConfluenceApiClient
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_sharepoint.tools import sharepoint_search_from_vectorstore
from web.openai.models import OpenAISetting

logger = register_logger("langchain_conference", level=logging.DEBUG, log_filename="langchain_conference")

class UserQuestionSchema(BaseModel):
    """
    Tool that used for searching the ANY Knowledge for user QUESTION 

    This tool MUST NOT BE USED IF user want to summarize a page ID
    """
    question: str = Field(description="The keyword that the user is asking for.")

class SummaryActionSchema(BaseModel):
    """
    Tool that used for summarizing the confluence page ID
    """
    page_id: str = Field(description="The confluence page ID the user is asking for in the user question. The Page ID must be a number")

@tool("confluence_search_tool", args_schema=UserQuestionSchema)
async def confluence_search_from_vectorstore(
    question: str, 
    # Argument 'config' is auto injected into the tool by langchain framework
    config: RunnableConfig) -> str:
    print(f"Running SEARCH tool: <q:{question} cfg:{config}>")
    logger.info(f"Running SEARCH tool: <q:{question} cfg:{config}>")
    try:
        vectorstore_repo: PGVectorRepo = config['configurable'].get("vectorstore_repo")
        
        retrieved_docs: List[Document] = await vectorstore_repo._pg_vector.asimilarity_search(question, k=5)

        context = "\n\n-----\n\n".join(f"Document title: {doc.metadata['title']}\nURL: {doc.metadata['url']}\nLast modified: {doc.metadata['last_modified']}\nDocument content: {doc.page_content}" for doc in retrieved_docs)

        docs_ids = [int(doc.metadata['page_id']) for doc in retrieved_docs]
        summaries = []
        summary_docs: List[Document] = await vectorstore_repo.aget_pages_summary_by_ids(docs_ids)
        for summary_doc in summary_docs:
            #print(summary_doc.id)
            title = summary_doc.metadata['title']
            summaries.append(f"Summary of '{title}:\n{summary_doc}")

        return f"""
            Question: {question}
            Context Chunks: {context}
            Document Summaries: {summaries}
        """
    except Exception as e:
        print(e)        
        traceback.print_exc()

@tool("confluence_summarize_tool", args_schema=SummaryActionSchema)
async def confluence_summarize(
    page_id: str, 
    # Argument 'config' is auto injected into the tool by langchain framework
    config: RunnableConfig) -> str:
    print(f"Running SUMMARIZE tool: <q:{page_id} cfg:{config}>")
    confluence_client: ConfluenceApiClient = config['configurable'].get("confluence_api_client")    
    html = await confluence_client.aget_page_content(page_id)
    #print(f"Running tool: <html: {html}>")
    content = html2text(html)
    return content

DEFAULT_CONFLUENCE_AGENT_SYSTEM_PROMPT = """
    You are a expert for question-answering tasks and collecting the data from different tools. 
    
    Use ONLY the provided materials to answer the question. You will receive:

    Instructions:
    - DECOMPOSE the user question if ask for multiple things
    - If the user intention is to ask to different OR gap analysis between two things, try to summarize and use markdown table format

    - Base your answer primarily on the specific context chunks. If broader understanding is required, refer to the provided document summaries.
    - If the answer is not contained in either the context chunks or the summaries, reply with "No results in the docs."
    - If there is duplicate or outdated information, refer only to the most recent documents by checking the "Last modified" value.
    - Include the title(s) of the documents you reference and their last modified date (in a human-readable format) as needed.
    - At the end of your response, Generate a set of RELEVANT question based on the user query
    - BEFORE the generated relevant question, provide the URLs of all documents referenced.

    Special Instructions:
    - If the user intention is to ask to different OR gap analysis between multiple things, try to use REASONING mode and override any nothink tag
    
    /nothink
"""

async def create_agent(llm_setting: OpenAISetting, system_prompt: str | None = None) -> StateGraph:
    """
    Create the agentic confluence agent based on the given argument

    Args
        llm_setting: The LLM setting
        system_prompt: The overriden system prompt

    Since
    --------
    0.0.6 (Moved from depedencies.py at 0.0.3)
    """
    if not system_prompt:
        # Use default confluence agent system prompt
       system_prompt = DEFAULT_CONFLUENCE_AGENT_SYSTEM_PROMPT

    tools=[confluence_search_from_vectorstore, confluence_summarize]

    # TODO: We should not link to sharepoint search directly right here, we should use hand-off tools to create agent swarm logic here
    if include_sharepoint_agent:
        tools.append(sharepoint_search_from_vectorstore)
    
    chat_openai = create_langchain_openai_stub(llm_setting)
    agent = create_react_agent(
        name="confluence_agent",
        model=chat_openai,
        prompt=system_prompt,
        # TODO: We should not link to sharepoint search directly right here, we should use hand-off tools to create agent swarm logic here
        tools=[confluence_search_from_vectorstore, confluence_summarize],
        version='v1'
    )
    return agent

async def create_page_summaries_langchain(llm_setting: OpenAISetting) -> Runnable:
    """
    Since
    -----
    0.0.1 (Moved at 0.0.7)
    """
    chat_openai = create_langchain_openai_stub(llm_setting)
    # TODO: Centralized Prompt management
    prompt = PromptTemplate.from_template(
        """Summarize the following document by providing a brief overview of its context, purpose and key pieces of information. If it is too long just summarize as much as you can:
        {text}
        SUMMARY:
        /nothink
        """
        )
    return prompt | chat_openai | StrOutputParser()