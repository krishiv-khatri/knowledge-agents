
import logging
import typing

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pymysql import OperationalError
from sqlalchemy.exc import SQLAlchemyError

from starlette.exceptions import HTTPException as StarletteHTTPException

registered_handlers = {}

def register_exception_handler(ex: typing.Type[Exception], handler: typing.Callable):
    """
    Since
    ------
    0.0.1
    """
    registered_handlers[ex] = handler

def unregister_exception_handler(ex: typing.Type[Exception]):
    """
    Since
    ------
    0.0.1
    """
    registered_handlers.pop(ex)

def register_app_exception_handler(app: FastAPI):    
    for (key, handler) in registered_handlers.items():
        logging.info(f"Add {key} handler to {app.title}")
        app.add_exception_handler(key, handler)
        
def _construct_error(errors: typing.Sequence[any]):
    """
    Since
    ------
    0.0.1
    """
    print(errors)
    result = []
    for err in errors:
        if isinstance(err, dict):
            type = err.get("type", "")
            loc = err.get("loc", [])            
            # TODO: not follow open-closed principles
            if type == "json_invalid":
                key = "body"
                error_msg = err.get("ctx", {}).get("error", "")
            elif type == "literal_error":
                key = ".".join(loc) 
                error_msg = err.get("msg", "")
            else:
                key = ".".join(loc) 
                error_msg = f"{key} is {type}"
            result.append({ "field": key, "msg" : error_msg})        
    return result
        

async def pydantic_exception_handler(request: Request, exc: ValidationError):
    """
    Since
    ------
    0.0.1
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "message": f"Oops! {exc.errors()} did something. There goes a rainbow..."},
    )

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """
    Since
    ------
    0.0.1
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "fail",
            "message": exc._message()
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Since
    ------
    0.0.1
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "fail",
            "message": exc.detail
        }
    )

async def fastapi_request_validation_exection_handler(request: Request, exc: RequestValidationError):
    """
    Default exception for `fastapi.exceptions.RequestValidationError`. Transform to standard response with error attached.    
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "fail",
            "message": "validation error",
            "errors": _construct_error(exc.errors())
        }
    )

register_exception_handler(ValidationError, pydantic_exception_handler)
register_exception_handler(StarletteHTTPException, http_exception_handler)
register_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
register_exception_handler(RequestValidationError, fastapi_request_validation_exection_handler)
