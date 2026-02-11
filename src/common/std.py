# Do not change any thing in this file. It is copied from common library

from typing import TypeVar, Generic

T = TypeVar("T")


class Result(Generic[T]):

    def __init__(self, ok: T, error: Exception):
        self._ok = ok
        self._error = error

    def is_ok(self) -> bool:
        return self._ok is not None

    def unwrap(self) -> T:
        if self.is_ok():
            return self._ok
        else:
            raise self._error

    @staticmethod
    def from_ok(ok: T) -> "Result[T]":
        return Result(ok, None)

    @staticmethod
    def from_error(error: Exception) -> "Result[T]":
        return Result(None, error)
