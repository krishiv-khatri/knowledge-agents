from typing import Annotated
from fastapi import APIRouter, Body, Depends
from langgraph.graph.graph import CompiledGraph
from web.doc import default_response
from web.langchain.util import StreamingResponseWithStatusCode, langchain_stream_with_statuscode_generator
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_confluence.schemas import ChatCompletionRequest
from web.langchain_sharepoint.dependencies import require_ingest_service, logger, require_rag_agent, require_vector_repo
from web.langchain_sharepoint.ingest_service import IngestService

router = APIRouter(prefix="/api/v1/sharepoint_agent")

tags = ["sharepoint_agent"]

@router.post(
    f"/chat",
    tags=tags,
    include_in_schema=True
)
async def completion(
    body: Annotated[ChatCompletionRequest, Body], 
    agentic_rag: CompiledGraph = Depends(require_rag_agent),
    vectorstore_repo: PGVectorRepo = Depends(require_vector_repo)
):
    """
    Since
    --------
    0.0.3
    """
    msg = {"messages": {"role": "user", "content": body.question }}
    return StreamingResponseWithStatusCode(
        langchain_stream_with_statuscode_generator(agentic_rag.astream(msg, config={"sharepoint_vectorstore_repo": vectorstore_repo}, stream_mode=["messages"])),
        media_type='text/chunked')

"""
- improve header splitting since some chunks have only headers and negligible content
- to not to split by heading 3 (###)
"""
@router.post(
    f"/reingress",
    tags=tags,
    include_in_schema=True)
async def reingress( 
    ingest_servcie: IngestService = Depends(require_ingest_service)):
    """
    Since
    --------
    0.0.3
    """
    await ingest_servcie.reingest()
    return "ok"
