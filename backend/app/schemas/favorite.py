from typing import Any

from pydantic import BaseModel, Field


class FavoriteCreate(BaseModel):
    kind: str = Field(default="note", min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=160)
    description: str | None = None
    dataset_id: str | None = None
    group_name: str | None = Field(default=None, max_length=80)
    sort_order: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class FavoriteRead(BaseModel):
    id: str
    kind: str
    title: str
    description: str | None = None
    dataset_id: str | None = None
    group_name: str | None = None
    sort_order: int = 0
    payload: dict[str, Any]
    snapshot: dict[str, Any]
    created_at: str
