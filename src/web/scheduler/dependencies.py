import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from web.dependencies import register_logger

_sch = None

_logger = register_logger("scheduler", level=logging.DEBUG, log_filename="scheduler")

def require_asyncio_scheduler() -> AsyncIOScheduler:
    """
    System Level dependencies for getting the global scheduler
    
    Since 
    ------
    0.0.1
    """
    return _sch

def set_global_scheduler(sch: AsyncIOScheduler):
    """
    Since
    -----
    0.0.1
    """
    global _sch
    _sch = sch

def require_scheduler_tasks_logger() -> logging.Logger:
    """
    System Level dependencies for getting the system logger

    Since
    ------
    0.0.1
    """
    return _logger
