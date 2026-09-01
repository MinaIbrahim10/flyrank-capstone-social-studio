from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ScheduleSlot,
    Variant,
)


class VariantNotApproved(
    ValueError
):
    pass


class InvalidScheduleTime(
    ValueError
):
    pass


def publisher_for_platform(
    platform: str,
) -> str:
    mapping = {
        "discord":
            "discord",

        "mock_x":
            "mock_x",

        "mock_linkedin":
            "mock_linkedin",
    }

    if platform not in mapping:
        raise ValueError(
            f"Unsupported platform: {platform}"
        )

    return mapping[platform]


def create_schedule_slot(
    session: Session,
    *,
    variant: Variant,
    scheduled_at: datetime,
) -> ScheduleSlot:
    if variant.status != "approved":
        raise VariantNotApproved(
            "Only an approved variant can be scheduled."
        )

    if (
        scheduled_at.tzinfo is None
        or scheduled_at.utcoffset() is None
    ):
        raise InvalidScheduleTime(
            "scheduled_at must include a timezone."
        )

    scheduled_utc = (
        scheduled_at
        .astimezone(timezone.utc)
    )

    now_utc = datetime.now(
        timezone.utc
    )

    if scheduled_utc <= now_utc:
        raise InvalidScheduleTime(
            "scheduled_at must be in the future."
        )

    publisher = publisher_for_platform(
        variant.platform
    )

    existing = session.scalar(
        select(ScheduleSlot)
        .where(
            ScheduleSlot.variant_id
            == variant.id,
            ScheduleSlot.scheduled_at
            == scheduled_utc,
            ScheduleSlot.publisher
            == publisher,
        )
    )

    if existing is not None:
        return existing

    slot = ScheduleSlot(
        variant_id=variant.id,
        publisher=publisher,
        scheduled_at=scheduled_utc,
        status="scheduled",
    )

    session.add(
        slot
    )

    session.commit()
    session.refresh(
        slot
    )

    return slot
