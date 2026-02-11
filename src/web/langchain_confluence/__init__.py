import datetime
import functools
from typing import Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from web.dependencies import register_system_initial_hook
from web.openai.dependencies import get_global_openai_like_repo
from web.openai.repo import OpenAISettingRepo
from web.persistence.dependencies import require_sql_engine_async_url, require_sql_engine_raw_uri
from web.scheduler.dependencies import require_asyncio_scheduler
from web.langchain.dependencies import register_langchain_agent
from web.langchain_confluence.client import ConfluenceApiClient
from web.langchain_confluence.dependencies import get_ingest_service, register_ingest_service, set_global_confluence_client, set_global_ingest_service, logger, set_global_vector_store
from web.langchain_confluence.ingest_service import IngestService
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_confluence.schemas import ConfluenceV2Config, ConfluenceV2RagConfig
from web.langchain_confluence.tools import create_agent, create_page_summaries_langchain

async def init_hook(config: Dict):
    """
    Initialize hook for confluence langchain plugin. (Part of langchain)

    1) The backed vector store will be initialized
    2) The confluence API client will be initialized
    3) The ingest service will be initialized

    Starting from 0.0.10
    1) It support multiple confluence space ingest
    
    Since
    ------
    0.0.1
    """
    logger.info(f"{'INIT START':15} Langchain confluence hook")

    config_embedding: Dict = config.get("embeddings")
    embeddings = OpenAIEmbeddings(
        model=config_embedding.get("model"), 
        base_url=config_embedding.get("base_url"), 
        api_key=config_embedding.get("api_key"), 
        tiktoken_enabled=False,
        tiktoken_model_name=config_embedding.get("model"),
        encoding_format="float")  # Explicitly set to float

    config_confluence: ConfluenceV2Config = ConfluenceV2Config(**config.get("confluence"))
    async_db_connection_url = require_sql_engine_async_url()
    async_db_connection_raw_url = require_sql_engine_raw_uri()

    logger.info(f"{'INIT':15} Vector store URI: {async_db_connection_url}")

    logger.info(f"{'INIT':15} Confluence API Client: <base_url: {config_confluence.url}, PAT: ***>")
    confluence_client = ConfluenceApiClient(config_confluence.url, config_confluence.api_token)
    set_global_confluence_client(confluence_client)

    openai_repo: OpenAISettingRepo = get_global_openai_like_repo()
    llm_setting = openai_repo.find_default_setting()

    lang_graph = await create_page_summaries_langchain(llm_setting)
    logger.info(f"{'INIT':15} Confluence Summaries Lang graph initialized")
    
    # Initialize Ingest service
    logger.info(f"{'INIT':15} Confluence Ingest Services")

    for item in config_confluence.rags:
        rag: ConfluenceV2RagConfig = item
        vector_store = PGVector(
            embeddings=embeddings,
            # PG database related configuration START
            connection=async_db_connection_url,
            async_mode=True,
            # Note: The async PGVector does not work when 'create_extension' is set to True
            create_extension=False,
            collection_name=rag.vectorstore_collection_name
            # PG database related configuration END
        )
        vectorstore_repo = PGVectorRepo(vector_store, async_db_connection_raw_url)
        if rag.default:
            logger.info(f"{'INIT':15} --> Set as default vector store <confluence_space: {rag.space}>")
            set_global_vector_store(vector_store)
        else:
            pass

        logger.info(f"{'INIT':15} --> Initialize PGVector <confluence_space:{rag.space}, colection_name: {rag.vectorstore_collection_name}>")

        if not rag.agent:
            logger.info(f"{'INIT':15} --> Skipping RAG Agent <confluence_space:{rag.space}, reason: not_enabled>")
        else:
            logger.info(f"{'INIT':15} --> Initialize RAG Agent <confluence_space:{rag.space}, include_sharepoint:{rag.agent.include_sharepoint}>")
            confluence_rag_agent = await create_agent(llm_setting, include_sharepoint_agent=rag.agent.include_sharepoint)

            from web.langchain_sharepoint.dependencies import require_vector_store as require_sharepoint_vector_store
            config = {
                "vectorstore_repo": vectorstore_repo,
                "sharepoint_vectorstore_repo": PGVectorRepo(await require_sharepoint_vector_store(), async_db_connection_raw_url)
            }            
            await register_langchain_agent(rag.agent.name, confluence_rag_agent, extra_config=config)
            logger.info(f"{'INIT':15} --> Register RAG agent <confluence_space:{rag.space} DONE>")
        
        if not rag.ingest.enabled:
            logger.info(f"{'INIT':15} --> Skipping Ingest Service <confluence_space: {rag.space}, reason: not_enabled>")
        else:
            logger.info(f"{'INIT':15} --> Initialize Ingest Service <confluence_space:{rag.space}>")
            ingest_service = IngestService(confluence_client, vectorstore_repo, lang_graph, logger)
            ingest_service.add_ingest_space(rag.space)
            if rag.ingest.default:
                logger.info(f"{'INIT':15} --> Set as default Ingest Service <confluence_space:{rag.space}>")
                set_global_ingest_service(ingest_service)
            
            # Register to global ingest service
            await register_ingest_service(rag.space, ingest_service)

            job_id = f"ingess-{rag.vectorstore_collection_name}-v2-job"

            try:
                cron_expression = rag.ingest.cron_expression
                if cron_expression:
                    logger.info(f"{'INIT':15} --> Schedule Ingest Service using <confluence_space:{rag.space}, cron_expression:{cron_expression}>")
                    sch: AsyncIOScheduler = require_asyncio_scheduler()
                    sch.add_job(id=job_id, func=ingest_periodically, args=[rag.space], trigger=CronTrigger.from_crontab(cron_expression), replace_existing=True)
                else:
                    logger.info(f"{'INIT':15} --> Disable Ingest Service")
                    sch: AsyncIOScheduler = require_asyncio_scheduler()
                    sch.remove_job(job_id=job_id)

            except Exception as e:
                logger.warning(f"{'INIT':15} --> Failed to set scheduler <error:{e}>")

        logger.info(f"{'INIT':15} Confluence Ingest Services DONE")
    
    logger.info(f"{'INIT END':15} Langchain confluence hook")
    
async def ingest_periodically(space: str):
    """
    """
    logger.info(f"{'INGEST':15} KICK start ingest service at <space:{space}, dt:{datetime.datetime.now()}>")
    ingest_service = await get_ingest_service(space)
    if not ingest_service:
        logger.error(f"{'INGEST':15} No ingest service registered for <space: {space}>")
    else:
        await ingest_service.reingest()

register_system_initial_hook(init_hook)