import logging
import openai
from typing import AsyncIterator, Tuple, Union
from fastapi import status
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import AIMessageChunk, ToolMessage, ToolMessageChunk
from starlette.types import Send
from web.openai.models import OpenAISetting
from web.langchain.dependencies import logger

# See this post for detail why we need this: https://github.com/tiangolo/fastapi/discussions/10138
class StreamingResponseWithStatusCode(StreamingResponse):
    '''
    Variation of StreamingResponse that can dynamically decide the HTTP status code, based on the returns from the content iterator (parameter 'content').
    Expects the content to yield tuples of (content: str, status_code: int), instead of just content as it was in the original StreamingResponse.
    The parameter status_code in the constructor is ignored, but kept for compatibility with StreamingResponse.
    '''
    async def stream_response(self, send: Send) -> None:
        first_chunk_content, self.status_code = await self.body_iterator.__anext__()         
        #print(f"First chunk {first_chunk_content}, {self.status_code}")
        if not isinstance(first_chunk_content, bytes):
            first_chunk_content = first_chunk_content.encode(self.charset)
            
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        await send({"type": "http.response.body", "body": first_chunk_content, "more_body": True})

        async for chunk_content, chunk_status in self.body_iterator:             
            #print(f"First chunk {chunk_content}, {chunk_status}")            
            if chunk_status // 100 != 2:
                self.status_code = chunk_status
                await send({"type": "http.response.body", "body": b"", "more_body": False})
                return
            if not isinstance(chunk_content, bytes):
                chunk_content = chunk_content.encode(self.charset)
            await send({"type": "http.response.body", "body": chunk_content, "more_body": True})

        await send({"type": "http.response.body", "body": b"", "more_body": False})

async def langchain_stream_with_statuscode_generator(subscription: AsyncIterator[Tuple[str, AIMessageChunk]]):
    """
    The async iterator return a tuple for each iteration 
    
    The first element in the tuple is the AI message content
    The second element in the tuple is the status code whether it is ok or not
    
    Since
    -----
    0.0.1
    """    
    try:
        async for (mode, chunk) in subscription:
            if isinstance(chunk[0], ToolMessage):
                # Discard tool message to 
                pass
            else:
                #print(type(chunk[0]))
                yield (chunk[0].content, status.HTTP_200_OK)
    except openai.BadRequestError as e:
        logger.error(f"{'ERROR':15} <openai_code:{e.code}>")
        yield (e.code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    except openai.RateLimitError as e:
        logger.error(f"{'ERROR':15} <openai_code:{e.code}>")
        yield (e.code, status.HTTP_429_TOO_MANY_REQUESTS)

def create_langchain_openai_embedding_stub(openai_setting: OpenAISetting) -> Union[ChatOpenAI]:
    """
    Create the langchan compatible service stub. Support OpenAI
    
    Since
    -----
    0.0.1 Stable (Moved from dependencies.py)
    """
    logging.info(f"Creating {openai_setting.provider} embedding <stub:{openai_setting}>")
    if openai_setting.provider == "openai":
        return OpenAIEmbeddings(
            api_key=openai_setting.api_key,
            timeout=openai_setting.chat_timeout_in_seconds
        )
    else:
        raise NotImplementedError("Unsupported")        
        

def create_langchain_openai_stub(openai_setting: OpenAISetting, temperature: float = 0.7, streaming: bool = True) -> Union[ChatOpenAI]:
    """
    Create the langchan compatible service stub.

    Support 
    1. VLLM OpenAI compatible server
    
    Since
    -----
    0.1.4 Stable (Moved from route.py)
    """
    #print("OpenAI setting")
    #print(openai_setting.as_camel_dict())
    
    if openai_setting.provider == "vllm-openai":
        return ChatOpenAI(
            base_url=openai_setting.extra_configs.get("base_url", "https://api.openai.com/v1"),
            api_key=openai_setting.api_key,
            timeout=300,
            streaming=streaming,
            model=openai_setting.model,
            temperature=temperature,
            max_tokens=openai_setting.extra_configs.get("max_token", 8192)
        )    
    return None
