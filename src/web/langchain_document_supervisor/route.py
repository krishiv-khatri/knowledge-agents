from typing import Annotated
from fastapi import APIRouter, Body, Depends
from langgraph.graph.graph import CompiledGraph
from web.doc import default_response
from web.langchain.util import StreamingResponseWithStatusCode, langchain_stream_with_statuscode_generator
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_confluence.schemas import ChatCompletionRequest
from web.langchain_confluence.dependencies import require_vector_repo as require_confluence_vector_repo
from web.langchain_sharepoint.dependencies import require_vector_repo as require_sharepoint_vector_repo
from web.langchain_document_supervisor.dependencies import require_doc_agent

router = APIRouter(prefix="/api/v1/doc_agent")

tags = ["doc_agent"]

@router.post(
    f"/chat",
    tags=tags,
    include_in_schema=True
)
async def completion(
    body: Annotated[ChatCompletionRequest, Body], 
    agent: CompiledGraph = Depends(require_doc_agent),
    confluence_vectorstore_repo: PGVectorRepo = Depends(require_confluence_vector_repo),
    sharepoint_vectorstore_repo: PGVectorRepo = Depends(require_sharepoint_vector_repo),
):
    """
    Since
    --------
    0.0.5
    """
    msg = {"messages": {"role": "user", "content": body.question }}
    config = {
        "vectorstore_repo": confluence_vectorstore_repo,
        "sharepoint_vectorstore_repo": sharepoint_vectorstore_repo
    }

    # async for chunk in agent.astream(msg, config=config, stream_mode=["updates"]):
    #     print(chunk)
    #     print("\n")

    
    return StreamingResponseWithStatusCode(
        langchain_stream_with_statuscode_generator(agent.astream(msg, config=config, stream_mode=["messages"])),
        media_type='text/chunked')

    #return ""