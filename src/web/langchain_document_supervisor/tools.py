from langgraph.graph import START, StateGraph
from langgraph_supervisor import create_supervisor
from web.openai.models import OpenAISetting
from web.langchain.util import create_langchain_openai_stub
from web.langchain_confluence.tools import create_agent as create_confluence_agent
from web.langchain_sharepoint.tools import create_agent as create_sharepoint_agent

DEFAULT_SUPERVISOR_AGENT_SYSTEM_PROMPT = """
    You are a supervisor managing two agents
    - a technical spec agent. Assign any thing related to technical to this agent
    - a functional spec agent. Assign any thing related to functional to this agent
    
    INSTRUCTION:
    
    - ASSIGN work to one agent at a time, do not call agents in parallel.
    - DECOMPOSE the user question into small piece so that the technical spec agent and functional spec agent able to understand the user question
    - REPLY to client if user question does not have information
"""

DEFAULT_CONFLUENCE_AGENT_SYSTEM_PROMPT = """
    You are a technical specification assistant for answering anything about technical.
    
    Use ONLY the provided materials to answer the question. You will receive from the tools

    - Specific context chunks retrieved from documents (RAG).
    - Broader summaries of the documents for additional context when needed.
    - After you're done with your tasks, respond to the supervisor directly
    - Respond ONLY with the results of your work, do NOT include ANY other text.

    Instructions:

    - Base your answer primarily on the specific context chunks. If broader understanding is required, refer to the provided document summaries.
    - If the answer is not contained in either the context chunks or the summaries, reply with "No results in the docs."
    - If there is duplicate or outdated information, refer only to the most recent documents by checking the "Last modified" value.
    - Include the title(s) of the documents you reference and their last modified date (in a human-readable format) as needed.
    - At the end of your response, Generate a set of RELEVANT question based on the user query
    - BEFORE the generated relevant question, provide the URLs of all documents referenced.    
    
    /nothink
"""

DEFAULT_SHAREPOINT_AGENT_SYSTEM_PROMPT = """
    You are a functional specification assistant for question-answering tasks. Use ONLY the provided materials to answer the question. You will receive:

    - Specific context chunks retrieved from documents (RAG).
    - Broader summaries of the documents for additional context when needed.
    - After you're done with your tasks, respond to the supervisor directly
    - Respond ONLY with the results of your work, do NOT include ANY other text.

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
    Create the agentic supervisor which include

    1) technical specification agent
    2) functional specification agent

    Since
    --------
    0.0.5
    """
    if not system_prompt:
        # Use default supervisor agent system prompt
        system_prompt = DEFAULT_SUPERVISOR_AGENT_SYSTEM_PROMPT

    tech_spec_agent = await create_confluence_agent(llm_setting, DEFAULT_CONFLUENCE_AGENT_SYSTEM_PROMPT)
    function_spec_agent = await create_sharepoint_agent(llm_setting, DEFAULT_SHAREPOINT_AGENT_SYSTEM_PROMPT)

    chat_openai = create_langchain_openai_stub(llm_setting)
    agent = create_supervisor(
        model=chat_openai,
        agents=[tech_spec_agent, function_spec_agent],
        prompt=DEFAULT_SUPERVISOR_AGENT_SYSTEM_PROMPT,
        add_handoff_back_messages=True,
        output_mode="full_history",
        parallel_tool_calls=True  # Enable parallel tool calls
    ).compile()
    return agent
