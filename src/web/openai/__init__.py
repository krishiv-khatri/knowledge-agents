from typing import Dict

from web.dependencies import register_system_initial_hook
from web.openai.dependencies import logger, set_global_openai_like_repo
from web.openai.repo import OpenAISettingRepo
from web.persistence.dependencies import require_sql_engine

async def init_hook(config: Dict):
    """
    Initialize hook for openai-like hook
    
    Since
    ------
    0.0.6
    """
    logger.info(f"{'INIT START':15} Langchain openai-like hook")

    openai_like_repo = OpenAISettingRepo(require_sql_engine())
    set_global_openai_like_repo(openai_like_repo)

    logger.info(f"{'INIT END':15} Langchain openai-like hook")

register_system_initial_hook(init_hook)
