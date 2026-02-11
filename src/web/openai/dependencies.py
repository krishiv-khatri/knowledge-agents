import logging
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web.dependencies import register_logger
from web.persistence.dependencies import require_session
from web.openai.exception import OpenAIConfigurationMissing
from web.openai.models import OpenAISetting
from web.openai.repo import OpenAISettingRepo

logger = register_logger("openai_like", level=logging.DEBUG, log_filename="openai_like")
_openai_like_repo: OpenAISettingRepo = None

logger = register_logger("openai_like", level=logging.DEBUG, log_filename="openai_like")

_openai_like_repo: OpenAISettingRepo = None

async def require_openai_setting(provider: str = None, async_session: AsyncSession = Depends(require_session)):
    """
    Dependencies - make sure we have at least one openAI setting
    
    Since
    --------
    0.0.5
    """
    if provider is not None:
        stmt = select(OpenAISetting).where(OpenAISetting.provider == provider).limit(1)
        result = await async_session.execute(stmt)
        found: OpenAISetting = result.scalars().first()
    else:
        found = False

    if not found:
        stmt = select(OpenAISetting).where(OpenAISetting.default == True).limit(1)
        result = await async_session.execute(stmt)
        found: OpenAISetting = result.scalars().first()
    if not found:
        raise OpenAIConfigurationMissing
    return found

def get_global_openai_like_repo():
    """
    Since
    -----
    0.0.6
    """
    return _openai_like_repo

def set_global_openai_like_repo(openai_repo: OpenAISettingRepo):
    """
    Since
    -----
    0.0.6
    """
    global _openai_like_repo
    _openai_like_repo = openai_repo
