from typing import Any

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class PaginatedRows(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
