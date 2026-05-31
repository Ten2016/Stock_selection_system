from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int
    msg: str
    data: Any


def success(data: Any = None, msg: str = "success") -> ApiResponse:
    return ApiResponse(code=0, msg=msg, data=data)


def error(code: int = 1, msg: str = "error", data: Any = None) -> ApiResponse:
    return ApiResponse(code=code, msg=msg, data=data)
