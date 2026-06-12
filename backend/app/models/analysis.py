from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.id"), index=True, nullable=False
    )
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    selected_variables_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    background_edges_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    algorithm_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    progress: Mapped[int] = mapped_column(default=0, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result_edges_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    result_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="jobs")
    dataset_version = relationship("DatasetVersion", back_populates="jobs")
