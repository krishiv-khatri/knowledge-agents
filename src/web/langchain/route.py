import json
from typing import Annotated, Dict, Union
from fastapi import APIRouter, Body, Header
from fastapi.responses import StreamingResponse
from langchain_core.messages.tool import ToolMessage
from langchain_core.messages import AIMessageChunk
from langgraph.graph.graph import CompiledGraph
from langchain_core.runnables import Runnable
from openai.types.chat.completion_create_params import CompletionCreateParams
from web.langchain.schemas import AgentRegistryConfiguration
from web.langchain.dependencies import get_all_registered_agents, get_langchain_agent

_prefix = "/langchain/openai/api/v1"

router = APIRouter(prefix=_prefix)

"""
Since
--------
0.0.10
"""
tags = ["langchain"]

@router.post(
    "/chat/completions",
    tags=tags)
async def chat_completions(body: Annotated[Dict, Body]):
    # Since FastAPI does not validate `body` using TypedDict(CompletionCreateParams)
    # We need to cast it manually
    """
    Since
    --------
    0.0.10
    """
    typed_body: CompletionCreateParams = body
    agent_to_dispatch: AgentRegistryConfiguration = await get_langchain_agent(full_qualified_agent_name=body['model'])
    if not agent_to_dispatch:
        # TODO: Better error handling
        raise HTTPException(status_code=500, detail="No model/agent found")
    else:
        #msg = {"messages": json.dumps(body['messages'])}
        agent: Union[CompiledGraph, Runnable] = agent_to_dispatch.chain_or_graph
        agent_config: Dict = agent_to_dispatch.extra_config

        async def proxy_stream():
            async for chunk in agent.astream(typed_body, config=agent_config, stream_mode=["messages"]):
                # The chunk is a tuple of tuple Tuple[str,Tuple[Message]]
                if (isinstance(chunk[1][0], ToolMessage)):
                    # skip
                    pass
                else:
                    ai_chunk: AIMessageChunk = chunk[1][0]
                    #print(type(ai_chunk))
                    sse_data = {
                        "id": ai_chunk.id,
                        "object": "chat.completion.chunk",
                        "choices": [{"delta": {"content": ai_chunk.content}}],
                    }
                    yield f"data: {json.dumps(sse_data)}\n\n"
    return StreamingResponse(proxy_stream(), media_type="text/event-stream")

@router.get(
    "/models",
    tags=tags)
async def get_models(host: Annotated[str | None, Header()] = None):
    """
    Since
    --------
    0.0.10
    """
    models = {
        "object": "list",
        "data": [
            {
                "id": f'{full_qualified_agent_name}',
                "object": "model",
                "api": {
                    "type": "openai",
                    "url": f"http://{host}/{_prefix}"
                }
            } for (full_qualified_agent_name, _) in get_all_registered_agents()
        ]
    }
    return models