from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    markdown: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Variant(Base):
    __tablename__ = "variants"

    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "platform",
            name="uq_variant_post_platform",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    post_id: Mapped[int] = mapped_column(
        ForeignKey(
            "posts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    __table_args__ = (
        UniqueConstraint(
            "variant_id",
            "scheduled_at",
            "publisher",
            name="uq_schedule_variant_time_publisher",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    variant_id: Mapped[int] = mapped_column(
        ForeignKey(
            "variants.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    publisher: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="scheduled",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class PublishAttempt(Base):
    __tablename__ = "publish_attempts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    slot_id: Mapped[int] = mapped_column(
        ForeignKey(
            "schedule_slots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    publisher: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    result: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    external_message_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    external_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class PublishReceipt(Base):
    __tablename__ = "publish_receipts"

    __table_args__ = (
        UniqueConstraint(
            "slot_id",
            name="uq_publish_receipt_slot",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_publish_receipt_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    slot_id: Mapped[int] = mapped_column(
        ForeignKey(
            "schedule_slots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    publisher: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    external_message_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    external_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class MockPublishedPost(Base):
    __tablename__ = "mock_published_posts"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_mock_post_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    variant_id: Mapped[int] = mapped_column(
        ForeignKey(
            "variants.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
