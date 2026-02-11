from typing import List
from pydantic import BaseModel, Field
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from langgraph.graph import START, StateGraph
from web.openai.models import OpenAISetting
from web.langchain.util import create_langchain_openai_stub
from web.langchain_confluence.repo import PGVectorRepo

class UserQuestionSchema(BaseModel):
    """
    Tool that used for searching the Knowledge for question about function specification or func spec ONLY

    This tool MUST NOT BE USED IF User is asking for any technical thing
    """
    question: str = Field(description="The keyword that the user is asking for.")

@tool("sharepoint_search_tool", args_schema=UserQuestionSchema)
async def sharepoint_search_from_vectorstore(
    question: str, 
    # Argument 'config' is auto injected into the tool by langchain framework
    config: RunnableConfig) -> str:
    print(f"Running SHAREPOINT SEARCH tool: <q:{question} cfg:{config}>")
    vectorstore_repo: PGVectorRepo = config['configurable'].get("sharepoint_vectorstore_repo")
    
    retrieved_docs: List[Document] = await vectorstore_repo._pg_vector.asimilarity_search(question, k=15)

    # print("Retieved_docs")
    # print(retrieved_docs)

    context = "\n\n-----\n\n".join(f"Document title: {doc.metadata['title']}\nURL: {doc.metadata['url']}\nDocument content: {doc.page_content}" for doc in retrieved_docs)

    # docs_ids = [int(doc.metadata['page_id']) for doc in retrieved_docs]
    # summaries = []
    # summary_docs: List[Document] = await vectorstore_repo.aget_pages_summary_by_ids(docs_ids)
    # for summary_doc in summary_docs:
    #     #print(summary_doc.id)
    #     title = summary_doc.metadata['title']
    #     summaries.append(f"Summary of '{title}:\n{summary_doc}")

    return f"""
        Question: {question}
        Context Chunks: {context}
    """

DEFAULT_CONFLUENCE_AGENT_SYSTEM_PROMPT = """
    You are an assistant for question-answering tasks. Use ONLY the provided materials to answer the question. You will receive:

    - Specific context chunks retrieved from documents (RAG).
    - Broader summaries of the documents for additional context when needed.

    Instructions:

    - Base your answer primarily on the specific context chunks. If broader understanding is required, refer to the provided document summaries.
    - If the answer is not contained in either the context chunks or the summaries, reply with "No results in the docs."
    - If there is duplicate or outdated information, refer only to the most recent documents by checking the "Last modified" value.
    - Include the title(s) of the documents you reference and their last modified date (in a human-readable format) as needed.
    - At the end of your response, Generate a set of RELEVANT question based on the user query
    - BEFORE the generated relevant question, provide the URLs of all documents referenced.
    
    /nothink
"""
async def create_agent(llm_setting: OpenAISetting, system_prompt: str = None) -> StateGraph:
    """
    Create the agentic sharepoint agent

    Since
    --------
    0.0.5
    """
    if not system_prompt:
        # Use default confluence agent system prompt
        system_prompt = DEFAULT_CONFLUENCE_AGENT_SYSTEM_PROMPT
    
    chat_openai = create_langchain_openai_stub(llm_setting)
    agent = create_react_agent(
        name="sharepoint_agent",
        model=chat_openai,
        prompt=system_prompt,
        tools=[sharepoint_search_from_vectorstore],
        version='v2'
    )
    return agent

