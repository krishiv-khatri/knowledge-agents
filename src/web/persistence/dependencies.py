from typing import AsyncGenerator

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from db.persistence import DbManager

_db_manager: DbManager = None

async def require_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Since
    ------
    0.0.1
    """
    async with _db_manager._async_session_maker() as session:
        yield session


def require_sql_engine() -> Engine:
    """
    Since
    ------
    0.0.1
    """
    return _db_manager.engine()

def require_async_sql_engine() -> AsyncEngine:
    """
    Since
    ------
    0.0.7
    """
    return _db_manager._async_engine

def require_sql_engine_url() -> str:
    """
    Since
    ------
    0.0.1
    """
    return _db_manager._url

def require_sql_engine_async_url() -> str:
    """
    Since
    ------
    0.0.1
    """
    return _db_manager._async_url

def require_sql_engine_raw_uri() -> str:
    """
    Since
    ------
    0.0.1
    """
    return _db_manager._raw_uri

def set_global_db_manager(db_manager: DbManager):
    """
    Since
    -----
    0.0.1
    """
    global _db_manager
    _db_manager = db_manager
