from typing import Dict

from db.persistence import DbManager
from web.dependencies import register_system_core_hook, require_sys_logger
from web.persistence.dependencies import set_global_db_manager

async def init_hook(config: Dict):
    """
    Initialize the database manager

    Since
    --------
    0.0.1
    """
    db_config = config.get("db")
    l = require_sys_logger()
    db_manager: DbManager = DbManager(
        dialect=db_config.get("dialect"),
        sync_driver=db_config.get("sync_driver"),
        async_driver=db_config.get("async_driver"),
        host=db_config.get("host"),
        port=db_config.get("port"),
        db=db_config.get("db"),
        user=db_config.get("user"),
        password=db_config.get("password"),
        debug=db_config.get("debug"))
    set_global_db_manager(db_manager)
    
register_system_core_hook(init_hook)