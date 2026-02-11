import datetime
from typing import Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from web.dependencies import register_system_initial_hook
from web.langchain.dependencies import register_langchain_agent
from web.scheduler.dependencies import require_asyncio_scheduler
from web.persistence.dependencies import require_sql_engine_async_url, require_sql_engine_raw_uri
from web.openai.dependencies import get_global_openai_like_repo
from web.openai.repo import OpenAISettingRepo
from web.langchain_jira.dependencies import require_ingest_service, set_global_image_langgaraph
from web.langchain_jira.client import JiraApiClient
from web.langchain_jira.dependencies import set_global_jira_client, set_global_ingest_service, logger
from web.langchain_jira.ingest_service import IngestService
from web.langchain_jira.repo import JiraRepo
from web.langchain_jira.tools import create_agent, create_image_langgraph, create_progress_langgraph


async def init_hook(config: Dict):
    """
    Initialize hook for Jira langchain plugin. (Part of langchain)

    1) The backed vector store will be initialized
    2) The Jira API client will be initialized
    3) The ingest service will be initialized
    
    Since
    ------
    0.0.6
    """
    logger.info(f"{'INIT START':15} Langchain JIRA hook")


    config_jira: Dict = config.get("jira")
    async_db_connection_url = require_sql_engine_async_url()
    async_db_connection_raw_url = require_sql_engine_raw_uri()

    logger.info(f"{'INIT':15} Database URI: {async_db_connection_url}")
    
    
    logger.info(f"{'INIT':15} Jira API Client: <base_url: {config_jira['url']}, PAT: ***>")
    jira_client = JiraApiClient(config_jira['url'], config_jira['api_token'])
    set_global_jira_client(jira_client)
    jira_repo = JiraRepo(async_db_connection_raw_url, logger)

    openai_repo: OpenAISettingRepo = get_global_openai_like_repo()

    logger.info(f"{'INIT':15} Initialize Function group Langgraph")
    # TODO: model validation
    llm_setting = openai_repo.find_default_setting()

    llm_lang_graph = await create_progress_langgraph(llm_setting)

    logger.info(f"{'INIT':15} Initialize Function group Langgraph DONE")

    logger.info(f"{'INIT':15} Initialize VLM Langgraph")
    # TODO: model validation
    vlm_model = config_jira['model_providers']['vlm']['model']
    vlm_setting = openai_repo.find_setting_by_model(vlm_model)
    if not vlm_setting:
        logger.error(f"{'INIT':15} No VLM model found in the registry <vlm: {vlm_model}>")
    else:
        logger.info(f"{'INIT':15} Using VLM model <vlm: {vlm_setting.extra_configs}>")
        vlm_langgraph = await create_image_langgraph(vlm_setting)
        set_global_image_langgaraph(vlm_langgraph)
        
    logger.info(f"{'INIT':15} Initialize VLM Langgraph DONE")

    # Initialize Ingest service
    logger.info(f"{'INIT':15} Jira Ingest Service")
    ingest_service = IngestService(jira_client, jira_repo, logger, llm_lang_graph, vlm_langgraph)
    set_global_ingest_service(ingest_service)

    # TODO: Refactor
    cron = config_jira.get("cron", "")
    job_id = f"ingess-tickets-job"
    if cron:
        components = cron['components']
        cron_expression = cron['cron_expression']
        logger.info(f"{'INIT':15} Schedule Jira Ingest Service using <cron_expression: {cron_expression}>")
        ingest_service.add_ingest_components(components)        
        sch: AsyncIOScheduler = require_asyncio_scheduler()
        sch.add_job(id=job_id, func=ingest_periodically, trigger=CronTrigger.from_crontab(cron_expression), replace_existing=True)
    else:
        logger.info(f"{'INIT':15} Disable scheduled Jira Ingest Service")
        sch: AsyncIOScheduler = require_asyncio_scheduler()
        sch.remove_job(job_id=job_id)

    logger.info(f"{'INIT':15} Register agent")

    # TODO: This import is ugly and need to be fixed
    # TODO: Support multiple vectorstore
    config = {
        "jira_repo" : jira_repo
    }
    agent = await create_agent(llm_setting)
    await register_langchain_agent("JIRA-Agent", agent, extra_config=config)
    logger.info(f"{'INIT':15} Register agent DONE")
    
    logger.info(f"{'INIT':15} Jira Ingest Service DONE")
    logger.info(f"{'INIT END':15} Langchain Jira hook")
    
async def ingest_periodically():
    """
    """
    logger.info(f"{'INGEST':15} KICK start ingest service at {datetime.datetime.now()}")
    ingest_service = await require_ingest_service()
    await ingest_service.reingest()

register_system_initial_hook(init_hook)
