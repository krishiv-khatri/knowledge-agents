"""
OpenAI-Compatible Proxy

This module provides an OpenAI-compatible chat completions API that routes
requests to the appropriate LangChain/LangGraph agent based on the model name
specified in the request. This allows tools like Open WebUI or any OpenAI
client library to interact with the multi-agent system.

Supported model names:
  - "jira_agent"       -> Jira ticket assistant
  - "confluence_agent" -> Confluence knowledge retrieval (RAG)
  - "master_agent"     -> Supervisor that coordinates all sub-agents
"""

import json
import logging
from fastapi import Body, Depends, FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.graph.graph import CompiledGraph
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage, ToolMessageChunk

from web.dependencies import register_logger
from web.langchain.dependencies import require_supervisor_agent
from web.langchain.util import langchain_stream_with_statuscode_generator
from web.langchain_confluence.dependencies import require_rag_agent
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_jira.dependencies import require_jira_agent, require_jira_repo
from web.langchain_jira.repo import JiraRepo
from web.langchain_jira.schemas import OpenaiCompletionRequest
from web.langchain_confluence.dependencies import require_vector_repo as require_confluence_vector_repo
from web.langchain_sharepoint.dependencies import require_vector_repo as require_sharepoint_vector_repo

# Configure logging to output detailed debug info
logger = register_logger("proxy_log", logging.DEBUG, "proxy.log")

# Setup console logging if not already configured
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)

openai_app = FastAPI()

@openai_app.get("/")
async def start():
    logger.info("Started OpenAI Proxy")

@openai_app.post("/chat/completions")
async def chat_completions(request: Request,
                           supervisor_agent: CompiledGraph = Depends(require_supervisor_agent),
                           jira_agent: CompiledGraph = Depends(require_jira_agent),
                           jira_repo: JiraRepo = Depends(require_jira_repo),
                           agentic_rag: CompiledGraph = Depends(require_rag_agent),
                           confluence_vectorstore_repo: PGVectorRepo = Depends(require_confluence_vector_repo),
                           sharepoint_vectorstore_repo: PGVectorRepo = Depends(require_sharepoint_vector_repo)):
    # dict mapping model to agent
    agents = {'jira_agent': {'agent': jira_agent, 'config': {"jira_repo": jira_repo}}, 'confluence_agent': {'agent': agentic_rag, 'config': {
            "vectorstore_repo": confluence_vectorstore_repo,
            "sharepoint_vectorstore_repo": sharepoint_vectorstore_repo
        }}}

    try:
        body = await request.json()
        logger.info(f"Received request body: {body}")
    except Exception as e:
        logger.error(f"Invalid JSON body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    body = OpenaiCompletionRequest(**body)
    if not body.messages:
        raise HTTPException(status_code=400, detail="Messages list is empty")

    if body.model == "master_agent":
        config = {"jira_agent": jira_agent, "confluence_agent": agentic_rag, "jira_repo": jira_repo, "vectorstore_repo": confluence_vectorstore_repo, "sharepoint_vectorstore_repo": sharepoint_vectorstore_repo}
        messages = {"messages": body.messages}
        # async for chunk in supervisor_agent.astream(messages, config=config, stream_mode=["debug"]):
        #         print(f"CHUNK: {chunk}")
        #         # logger.debug("[DEBUG] Stream chunk:", f"{chunk}")
        async def proxy_stream():
            async for chunk in supervisor_agent.astream(messages, config=config, stream_mode=["messages"]):
                #print("[DEBUG] Stream chunk:", chunk)
                msg = chunk[1][0]
                logger.info(f"[DEBUG] Stream chunk: {msg}")
                content = None
                if isinstance(msg, ToolMessage) or isinstance(msg, ToolMessageChunk):
                    tool_msg_chunk: ToolMessageChunk = msg
                    if (tool_msg_chunk.name == "confluence_agent"):
                        content = msg.content
                    else:
                        content = None                
                if isinstance(msg, AIMessage) or isinstance(msg, AIMessageChunk):
                    content = msg.content                
                if not content:
                    continue

                logger.info(f"[DEBUG] Stream content: {content}")
                sse_data = {

                    "object": "chat.completion.chunk",
                    "choices": [{"delta": {"content": content}}],
                }
                yield f"data: {json.dumps(sse_data)}\n\n"

        return StreamingResponse(proxy_stream(), media_type="text/event-stream")
    else:
        agent = agents[body.model]['agent']
        config = agents[body.model]['config']

        msg = {"messages": body.messages}
        async def proxy_stream():
            async for chunk in langchain_stream_with_statuscode_generator(agent.astream(msg, config=config, stream_mode=["messages"])):
                text = chunk[0]
                if not text:
                    continue
                sse_data = {
                    "id": "chatcmpl-123",
                    "object": "chat.completion.chunk",
                    "choices": [{"delta": {"content": text}}],
                }
                yield f"data: {json.dumps(sse_data)}\n\n"
        
        return StreamingResponse(proxy_stream(), media_type="text/event-stream")



# @openai_app.post("/chat/completions")
# async def chat_completions(request: Request,
#                            jira_agent: CompiledGraph = Depends(require_jira_agent),
#                            jira_repo: JiraRepo = Depends(require_jira_repo),
#                            agentic_rag: CompiledGraph = Depends(require_rag_agent),
#                            confluence_vectorstore_repo: PGVectorRepo = Depends(require_vector_repo),
#                            sharepoint_vectorstore_repo: PGVectorRepo = Depends(require_sharepoint_vector_repo)):
#     # dict mapping model to agent
#     agents = {'jira_agent': {'agent': jira_agent, 'config': {"jira_repo": jira_repo}}, 'confluence_agent': {'agent': agentic_rag, 'config': {
#             "vectorstore_repo": confluence_vectorstore_repo,
#             "sharepoint_vectorstore_repo": sharepoint_vectorstore_repo
#         }}}

#     try:
#         body = await request.json()
#         logger.info(f"Received request body: {body}")
#     except Exception as e:
#         logger.error(f"Invalid JSON body: {e}")
#         raise HTTPException(status_code=400, detail="Invalid JSON body")
#     body = OpenaiCompletionRequest(**body)
#     if not body.messages:
#         raise HTTPException(status_code=400, detail="Messages list is empty")

#     agent = agents[body.model]['agent']
#     config = agents[body.model]['config']

#     msg = {"messages": body.messages}
#     async def proxy_stream():
#         async for chunk in langchain_stream_with_statuscode_generator(agent.astream(msg, config=config, stream_mode=["messages"])):
#             text = chunk[0]
#             if not text:
#                 continue
#             sse_data = {
#                 "id": "chatcmpl-123",
#                 "object": "chat.completion.chunk",
#                 "choices": [{"delta": {"content": text}}],
#             }
#             yield f"data: {json.dumps(sse_data)}\n\n"
    
#     return StreamingResponse(proxy_stream(), media_type="text/event-stream")


@openai_app.get("/models")
async def get_models():
    """
    Returns the list of available agent models exposed via the OpenAI-compatible API.
    Update the URL to match your deployment endpoint.
    """
    import os
    api_url = os.getenv("OPENAI_PROXY_URL", "http://localhost:8000/openai")
    models = {
    "object": "list",
    "data": [
        {
        "id": "jira_agent",
        "object": "model",
        "api": {
            "type": "openai",
            "url": api_url
        }
        },
        {
        "id": "confluence_agent",
        "object": "model",
        "api": {
            "type": "openai",
            "url": api_url
        }
        },
        {
        "id": "master_agent",
        "object": "model",
        "api": {
            "type": "openai",
            "url": api_url
        }
        }
    ]
    }
    return models
"""
[DEBUG] Stream chunk: (('supervisor:2e153650-1be8-945f-9700-971c53c60ad9', 'agent:f0c6aa5c-e70b-1774-f0f6-c43f6369f25c'), 'messages', (AIMessageChunk(content='', additional_kwargs={}, response_metadata={}, id='run--6a784f7d-0a7b-4c62-96dd-d6722de3083a'), {'langgraph_step': 1, 'langgraph_node': 'agent', 'langgraph_triggers': ('branch:to:agent',), 'langgraph_path': ('__pregel_pull', 'agent'), 'langgraph_checkpoint_ns': 'supervisor:2e153650-1be8-945f-9700-971c53c60ad9|agent:f0c6aa5c-e70b-1774-f0f6-c43f6369f25c', 'checkpoint_ns': 'supervisor:2e153650-1be8-945f-9700-971c53c60ad9', 'ls_provider': 'openai', 'ls_model_name': 'Qwen/Qwen3-32B-AWQ', 'ls_model_type': 'chat', 'ls_temperature': 0.7, 'ls_max_tokens': 8192}))
"""
