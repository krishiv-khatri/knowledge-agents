"""
Application Bootstrap & Dependency Injection

This module manages the application lifecycle:
  - Logger initialization and registration (per-component log files)
  - System hook registration (core services like DB, scheduler)
  - Plugin hook registration (optional integrations)
  - Bootstrap sequence that runs all hooks at startup

The hook system allows each module (Confluence, Jira, SharePoint, etc.) to
register async initialization functions that are called during FastAPI startup.
"""

import logging
from logging.config import fileConfig
import traceback
from typing import Awaitable, Dict
from logging.handlers import TimedRotatingFileHandler


config_path = "conf/setting.yaml"

_system_hooks = []

_hooks = []

# Log path path (0.0.1)
_log_base_path: str = "logs"

_cache_logger: Dict[str, logging.Logger] = {}

def register_system_core_hook(coro: Awaitable):
    """
    Since
    -----
    0.0.1
    """
    _system_hooks.append(coro)


def register_system_initial_hook(coro: Awaitable):
    """

    Since
    -----
    0.0.1
    """
    _hooks.append(coro)


def init_logger_config(logging_config_path: str, base_log_path: str):
    """
    Initialize logger configuration by the `specified logging config path`

    Since
    -----
    0.0.1
    """
    global _log_base_path
    print(f"Using logging path {logging_config_path}")
    fileConfig(logging_config_path)
    _log_base_path = base_log_path


def register_logger(name: str, level: int = logging.INFO, log_filename=""):
    """
    Support register logging service on the fly so that each component can have their own logger

    Since
    -----
    0.0.1
    """
    logger = _cache_logger.get(name)
    if not logger:
        logger = logging.getLogger(name)
        logger.setLevel(level)

        log_filename = log_filename if log_filename else name

        # configure the handler and formatter for logger2
        handler = TimedRotatingFileHandler(
            filename=f"{_log_base_path}/{log_filename}.log",
            when="midnight",
            interval=1,
            backupCount=5,
        )
        fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)9s - %(message)s")

        # add formatter to the handler
        handler.setFormatter(fmt)
        # add handler to the logger
        logger.addHandler(handler)
        _cache_logger[name] = logger
    return logger


async def bootstrap(config: Dict):
    try:
        print(f"{'Initializing':15} System Hook Cycle {config}")

        for hooks in _system_hooks:
            try:
                await hooks(config)
            except Exception as e:
                print(str(e))
                traceback.print_exc()

        print(f"{'Initialized':15} System Hook Cycle")
        print(f"{'Initializing':15} System Plugin Cycle")

        for hooks in _hooks:
            try:
                await hooks(config)
            except Exception as e:
                print(str(e))
                traceback.print_exc()

        print(f"{'Initializing':15} System Plugin Cycle")

    except Exception as e:
        print(str(e))
        traceback.print_exc()


# ========================== Logger Start ==================================================


def require_sys_logger() -> logging.Logger:
    """
    System Level dependencies for getting the system logger

    Since
    ------
    0.0.1
    """
    return logging.getLogger("System")

# ========================== Logger  End  ==================================================