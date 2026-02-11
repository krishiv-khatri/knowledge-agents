from typing import Annotated, Dict, List
from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import StreamingResponse
from web.doc import default_response
from langchain_core.runnables import Runnable
from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph
from langchain_postgres import PGVector
from web.langchain_confluence.schemas import ChatCompletionRequest
from web.langchain.util import StreamingResponseWithStatusCode, langchain_stream_with_statuscode_generator
from web.langchain_confluence.ingest_service import IngestService
from web.langchain_confluence.dependencies import require_ingest_service, require_page_summaries_langchain, require_rag_agent, require_vector_repo, require_default_vector_store, logger
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_confluence.schemas import ChatCompletionRequest
from web.langchain_sharepoint.dependencies import require_vector_repo as require_sharepoint_vector_repo

router = APIRouter(prefix="/api/v1")

tags = ["confluence_assistant"]

@router.post(
    f"/chat",
    tags=tags,
    include_in_schema=True
)
async def completion(
    body: Annotated[ChatCompletionRequest, Body], 
    agentic_rag: CompiledGraph = Depends(require_rag_agent),
    confluence_vectorstore_repo: PGVectorRepo = Depends(require_vector_repo),
    sharepoint_vectorstore_repo: PGVectorRepo = Depends(require_sharepoint_vector_repo)
):
    """
    Since
    --------
    0.0.1
    """
    # if body.agent == '' or body.agent == 'rag':
    #     return StreamingResponseWithStatusCode(
    #         langchain_stream_with_statuscode_generator(rag.astream({"question": body.question }, stream_mode=["messages"])),
    #         media_type='text/chunked')
    # else:
    #     # msg = {"messages": {"role": "user", "content": body.question }}
    #     # async for (mode, chunk) in agentic_rag.astream(msg, config={"vectorstore": vector_store}, stream_mode=["updates"]):
    #     #     print(chunk)
    #     #     print("\n")
    #     # return "ok"
    #     config = {
    #         "vectorstore_repo": confluence_vectorstore_repo,
    #         "sharepoint_vectorstore_repo": sharepoint_vectorstore_repo
    #     }
    #     # msg = {"messages": {"role": "user", "content": body.question }}
    #     return StreamingResponseWithStatusCode(
    #         langchain_stream_with_statuscode_generator(agentic_rag.astream({'messages': body.messages}, config=config, stream_mode=["messages"])),
    #         media_type='text/chunked')
    config = {
            "vectorstore_repo": confluence_vectorstore_repo,
            "sharepoint_vectorstore_repo": sharepoint_vectorstore_repo
        }
    response = await agentic_rag.ainvoke({'messages': body.messages}, config=config)
    print(response["messages"][-1].content)
    return response["messages"][-1].content

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
    0.0.1
    """
    await ingest_servcie.reingest()
    return "ok"

@router.post(
    f"/embeddings",
    tags=tags,
    include_in_schema=True
)
async def embeddings(question: str, vectorstore: PGVector = Depends(require_default_vector_store)):
    """
    Since
    --------
    0.0.1
    """
    return await vectorstore.embeddings.aembed_query(question)

@router.post(
    f"/rag",
    tags=tags,
    include_in_schema=True
)
async def test_rag(
    query: Annotated[ChatCompletionRequest, Body], 
    agentic_rag: CompiledGraph = Depends(require_rag_agent),
    confluence_vectorstore_repo: PGVectorRepo = Depends(require_vector_repo),
    sharepoint_vectorstore_repo: PGVectorRepo = Depends(require_sharepoint_vector_repo)):
    """
    Since
    --------
    0.0.1
    """
    config = {
        "vectorstore_repo": confluence_vectorstore_repo,
        "sharepoint_vectorstore_repo": sharepoint_vectorstore_repo
    }
    msg = {"messages": {"role": "user", "content": query.question }}
    response: Dict = await agentic_rag.ainvoke(msg, config=config)
    messages: List[MessageLikeRepresentation] = response['messages']
    retrieved_chunks = await confluence_vectorstore_repo._pg_vector.asimilarity_search(query.question, k=15)
    return {"retrieved_docs": retrieved_chunks, "answer": messages[-1].content }

@router.post(
    f"/test_summaries",
    tags=tags,
    include_in_schema=True
)
async def test_summaries(
    query: Annotated[ChatCompletionRequest, Body], summaries_langchain: Runnable = Depends(require_page_summaries_langchain)):
    """
    Since
    --------
    0.0.1
    """
    result: str = await summaries_langchain.ainvoke({"text": query.question})
    return {"answer": result }

@router.post(
    f"/diagram",
    tags=tags,
    include_in_schema=True
)
async def diagram(lang_graph: StateGraph = Depends(require_rag_agent)):
    # See .venv/lib/python3.10/site-packages/langchain_core/runnables/graph.py for the private datatype 
    graph = lang_graph.get_graph()
    image_bytes: bytes = graph.draw_mermaid_png()
    return Response(content=image_bytes, media_type="image/png")


# @router.post(
#     f"/confluence/chat/completion",
#     tags=tags,
#     include_in_schema=True
# )
# async def openai_like_chat_completion(req: Request):
#     try:
#         body = await request.json()
#         logger.info(f"Received request body: {body}")
#     except Exception as e:
#         logger.error(f"Invalid JSON body: {e}")
#         raise HTTPException(status_code=400, detail="Invalid JSON body")

#     # Force streaming to True to get incremental tokens from upstream
#     body["stream"] = True
    
#     async for chunk in agentic_rag.astream(msg, config=config, stream_mode=["messages"]):
#         #text = chunk.decode("utf-8").strip()
#         text = chunk.decode("utf-8")
#         if not text:
#             continue
#         sse_data = {
#             "id": "chatcmpl-123",
#             "object": "chat.completion.chunk",
#             "choices": [{"delta": {"content": text}}],
#         }
#         yield f"data: {json.dumps(sse_data)}\n\n"


#     # async def proxy_stream():
#     #     try:
#     #         async with httpx.AsyncClient(timeout=None) as client:
#     #             async with client.stream(
#     #                 "POST",
#     #                 UPSTREAM_STREAMING_ENDPOINT,
#     #                 json=body,
#     #                 headers={"Accept": "text/event-stream"},
#     #             ) as response:
#     #                 if response.status_code != 200:
#     #                     content = await response.aread()
#     #                     yield f"data: {{\"error\": \"Upstream error {response.status_code}\"}}\n\n"
#     #                     return

#     #                 async for chunk in response.aiter_bytes():
#     #                     #text = chunk.decode("utf-8").strip()
#     #                     text = chunk.decode("utf-8")
#     #                     if not text:
#     #                         continue
#     #                     sse_data = {
#     #                         "id": "chatcmpl-123",
#     #                         "object": "chat.completion.chunk",
#     #                         "choices": [{"delta": {"content": text}}],
#     #                     }
#     #                     yield f"data: {json.dumps(sse_data)}\n\n"

#     #         # Send done event at end of stream
#     #         yield b"data: [DONE]\n\n"

#     #     except Exception as e:
#     #         yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

#     # return StreamingResponse(proxy_stream(), media_type="text/event-stream")
#     # #return StreamingResponse(proxy_stream(), media_type="text/chunked")
#     pass