from enum import Enum, auto
from typing import Dict, Generic, List, Optional, TypeVar
from typing_extensions import Literal, TypedDict

from pydantic import BaseModel, Field

T = TypeVar('T')

class StandardResponse(BaseModel):
    """
    Since
    ------
    0.0.1
    """
    status: Literal['ok', 'fail']
    message: Optional[str] = Field(default=None, title="The human readable error message", description="Caller will need to analyst this value when the status = `fail`")

class OkResponse(StandardResponse, Generic[T]):
    """
    Since
    ------
    0.0.1
    """
    data: T

class ErrDetail(TypedDict):
    """
    Since
    ------
    0.0.1
    """
    field: str
    msg: str

class ErrResponse(StandardResponse):
    """
    Since
    ------
    0.0.1
    """
    code: int
    errors: List[ErrDetail]

class Status(Enum):
    """
    Since
    ------
    0.0.1
    """
    OK = auto()
    ERROR = auto()

