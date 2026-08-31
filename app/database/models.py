from enum import Enum
from uuid import UUID

from sqlalchemy import UUID as SQLUUID
from sqlalchemy import VARCHAR, Enum as SQLEnum, DateTime, func, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class JobStatus(Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
    )

    type: Mapped[str] = mapped_column(
        VARCHAR(50),
        nullable=False,
        index = True
    )

    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus),
        nullable=False,
        index = True
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        index = True
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )

    error_message: Mapped[str | None] = mapped_column(
        VARCHAR(1000),
        nullable=True,
    )

