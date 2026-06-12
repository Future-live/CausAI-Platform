from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FavoriteItem(Base):
    __tablename__ = "favorite_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="favorites")
