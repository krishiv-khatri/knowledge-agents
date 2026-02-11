from typing import Dict
from web.dependencies import register_system_initial_hook
from web.openai.dependencies import get_global_openai_like_repo
from web.openai.repo import OpenAISettingRepo
from web.langchain_document_supervisor.dependencies import register_langchain_agent, logger
from web.langchain_document_supervisor.tools import create_agent

async def init_hook(config: Dict):
    """
    Initialize hook for document supervisor
    
    Since
    ------
    0.0.5
    """
    logger.info(f"{'INIT START':15} Langchain document supervisor hook")

    openai_repo: OpenAISettingRepo = get_global_openai_like_repo()
    llm_setting = openai_repo.find_default_setting()
    
    doc_agent = await create_agent(llm_setting)

    logger.info(f"{'INIT START':15} Register document agent")

    await register_langchain_agent("document_agent", doc_agent)

    logger.info(f"{'INIT END':15} Langchain document supervisor")

register_system_initial_hook(init_hook)
