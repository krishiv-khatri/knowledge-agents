from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.events import JobEvent, EVENT_ALL, JobExecutionEvent, JobSubmissionEvent

from web.dependencies import register_system_core_hook
from web.scheduler.dependencies import require_scheduler_tasks_logger, set_global_scheduler
from web.persistence.dependencies import require_sql_engine

# ========================== Scheudler Init Hook Start      ==================================================

def scheduler_event_listener(event: JobEvent):
    # print("Job")
    # print(event)
    if isinstance(event, JobExecutionEvent):
        print(f"Job executed {event}")
        pass
    if isinstance(event, JobSubmissionEvent):
        print(f"Job submitted {event}")
        pass

async def init_hook(config: Dict):
    """
    The initialization hook for registering the schedule job
    
    Since
    -----
    0.0.1
    """
    logger = require_scheduler_tasks_logger()    
    logger.info(f"{'INIT START':15} scheduler system hook")

    config_schedule = config.get("scheduler", {})
    
    scheduler_name = config_schedule.get("name", "default")

    engine = require_sql_engine()

    jobstores = {
        'default': SQLAlchemyJobStore(engine=engine, tablename=f"{scheduler_name}_apscheduler_jobs")
    }
    executors = {
        'default': ThreadPoolExecutor(20),
        'processpool': ProcessPoolExecutor(5)
    }
    job_defaults = {
        'coalesce': False,
        'max_instances': 3
    }
    _sch = AsyncIOScheduler(jobstores=jobstores, job_defaults=job_defaults)
        
    enabled: bool = config_schedule.get("enabled", False) == True
    if not enabled:
        logger.info(f"{'INIT END':15} Scheduler is configured AS DISABLED")
    else:        
        _sch.start()
    logger.info(f"{'INIT END':15} Scheduler system hook")

    set_global_scheduler(_sch)

register_system_core_hook(init_hook)
