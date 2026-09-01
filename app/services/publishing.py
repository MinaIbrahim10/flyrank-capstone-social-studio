from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
import hashlib
import os
from pathlib import Path

from sqlalchemy import (
    select,
    update,
)
from sqlalchemy.orm import Session

from app.models import (
    PublishAttempt,
    PublishReceipt,
    ScheduleSlot,
    Variant,
)
from app.publishers.factory import (
    configured_publisher_name,
    create_publisher,
)
from app.publishers.discord import (
    HttpClientLike,
)


class ScheduleNotFound(
    LookupError
):
    pass


class PublishNotAllowed(
    ValueError
):
    pass


class PublishInProgress(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class PublishOutcome:
    slot_id: int
    variant_id: int
    publisher: str
    idempotency_key: str
    external_message_id: str | None
    external_url: str | None
    duplicate_prevented: bool


def normalized_schedule_time(
    slot: ScheduleSlot,
) -> str:
    value = slot.scheduled_at

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )
    else:
        value = value.astimezone(
            timezone.utc
        )

    return value.isoformat()


def make_idempotency_key(
    *,
    slot: ScheduleSlot,
) -> str:
    source = (
        f"variant={slot.variant_id}|"
        f"time={normalized_schedule_time(slot)}|"
        f"publisher={slot.publisher}"
    )

    return hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()


def outcome_from_receipt(
    receipt: PublishReceipt,
    *,
    variant_id: int,
    duplicate_prevented: bool,
) -> PublishOutcome:
    return PublishOutcome(
        slot_id=receipt.slot_id,
        variant_id=variant_id,
        publisher=receipt.publisher,
        idempotency_key=(
            receipt.idempotency_key
        ),
        external_message_id=(
            receipt.external_message_id
        ),
        external_url=(
            receipt.external_url
        ),
        duplicate_prevented=(
            duplicate_prevented
        ),
    )


def test_crash_after_adapter_enabled(
    publisher_name: str,
) -> bool:
    requested = (
        os.getenv(
            "SOCIAL_STUDIO_TEST_CRASH_AFTER_ADAPTER",
            "",
        )
        .strip()
        .lower()
    )

    return (
        requested
        in {
            "1",
            "true",
            "yes",
        }
        and publisher_name.startswith(
            "mock_"
        )
    )


def write_after_adapter_crash_marker(
    *,
    slot_id: int,
    idempotency_key: str,
) -> None:
    raw = os.getenv(
        "SOCIAL_STUDIO_TEST_CRASH_MARKER",
        "",
    ).strip()

    if not raw:
        return

    path = Path(
        raw
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        (
            "intentional-after-adapter-crash\n"
            f"slot_id={slot_id}\n"
            f"idempotency_key={idempotency_key}\n"
        )
    )


def publish_slot(
    session: Session,
    *,
    slot_id: int,
    publisher_override: str | None = None,
    discord_webhook_url: str | None = None,
    http_client: HttpClientLike | None = None,
) -> PublishOutcome:
    slot = session.get(
        ScheduleSlot,
        slot_id,
    )

    if slot is None:
        raise ScheduleNotFound(
            "Schedule slot not found."
        )

    variant = session.get(
        Variant,
        slot.variant_id,
    )

    if variant is None:
        raise PublishNotAllowed(
            "Scheduled variant no longer exists."
        )

    existing_receipt = session.scalar(
        select(PublishReceipt)
        .where(
            PublishReceipt.slot_id
            == slot.id
        )
    )

    if existing_receipt is not None:
        return outcome_from_receipt(
            existing_receipt,
            variant_id=variant.id,
            duplicate_prevented=True,
        )

    if variant.status not in {
        "approved",
        "published",
    }:
        raise PublishNotAllowed(
            "Only an approved variant can be published."
        )

    if slot.status == "published":
        receipt = session.scalar(
            select(PublishReceipt)
            .where(
                PublishReceipt.slot_id
                == slot.id
            )
        )

        if receipt is None:
            raise PublishNotAllowed(
                "Published slot is missing its receipt."
            )

        return outcome_from_receipt(
            receipt,
            variant_id=variant.id,
            duplicate_prevented=True,
        )

    if slot.status == "publishing":
        raise PublishInProgress(
            "This schedule slot is already being published."
        )

    claim = session.execute(
        update(ScheduleSlot)
        .where(
            ScheduleSlot.id
            == slot.id,
            ScheduleSlot.status
            == "scheduled",
        )
        .values(
            status="publishing"
        )
    )

    if claim.rowcount != 1:
        session.rollback()

        refreshed = session.get(
            ScheduleSlot,
            slot.id,
        )

        if (
            refreshed is not None
            and refreshed.status
            == "published"
        ):
            receipt = session.scalar(
                select(PublishReceipt)
                .where(
                    PublishReceipt.slot_id
                    == slot.id
                )
            )

            if receipt is not None:
                return outcome_from_receipt(
                    receipt,
                    variant_id=variant.id,
                    duplicate_prevented=True,
                )

        raise PublishInProgress(
            "Another publisher already claimed "
            "this schedule slot."
        )

    session.commit()

    slot = session.get(
        ScheduleSlot,
        slot.id,
    )

    variant = session.get(
        Variant,
        variant.id,
    )

    idempotency_key = (
        make_idempotency_key(
            slot=slot,
        )
    )

    publisher_name = (
        configured_publisher_name(
            slot.publisher,
            override=publisher_override,
        )
    )

    attempt = PublishAttempt(
        slot_id=slot.id,
        publisher=publisher_name,
        idempotency_key=(
            idempotency_key
        ),
        result="started",
        external_message_id=None,
        external_url=None,
        error=None,
    )

    session.add(
        attempt
    )

    session.commit()
    session.refresh(
        attempt
    )

    attempt_id = attempt.id

    try:
        publisher = create_publisher(
            name=publisher_name,
            session=session,
            discord_webhook_url=(
                discord_webhook_url
            ),
            http_client=http_client,
        )

        result = publisher.publish(
            variant_id=variant.id,
            content=variant.content,
            idempotency_key=(
                idempotency_key
            ),
        )

        # Test-only hard crash.
        #
        # For mock publishers the adapter's external-side-effect
        # row has already committed. We terminate before the local
        # receipt/status transaction, creating the exact recovery
        # window needed by the final crash/retry acceptance probe.
        if test_crash_after_adapter_enabled(
            publisher_name
        ):
            write_after_adapter_crash_marker(
                slot_id=slot.id,
                idempotency_key=(
                    idempotency_key
                ),
            )

            os._exit(87)

        attempt = session.get(
            PublishAttempt,
            attempt_id,
        )

        if attempt is None:
            raise RuntimeError(
                "Publish attempt disappeared."
            )

        attempt.result = "success"

        attempt.external_message_id = (
            result.external_message_id
        )

        attempt.external_url = (
            result.external_url
        )

        attempt.error = None

        receipt = PublishReceipt(
            slot_id=slot.id,
            publisher=publisher_name,
            idempotency_key=(
                idempotency_key
            ),
            external_message_id=(
                result.external_message_id
            ),
            external_url=(
                result.external_url
            ),
        )

        session.add(
            receipt
        )

        slot = session.get(
            ScheduleSlot,
            slot.id,
        )

        variant = session.get(
            Variant,
            variant.id,
        )

        if slot is None:
            raise RuntimeError(
                "Schedule slot disappeared."
            )

        if variant is None:
            raise RuntimeError(
                "Variant disappeared."
            )

        slot.status = "published"
        variant.status = "published"

        session.add(
            slot
        )

        session.add(
            variant
        )

        session.add(
            attempt
        )

        session.commit()

        session.refresh(
            receipt
        )

        return outcome_from_receipt(
            receipt,
            variant_id=variant.id,
            duplicate_prevented=False,
        )

    except Exception as exc:
        session.rollback()

        slot = session.get(
            ScheduleSlot,
            slot_id,
        )

        if (
            slot is not None
            and slot.status
            == "publishing"
        ):
            slot.status = "scheduled"
            session.add(
                slot
            )

        attempt = session.get(
            PublishAttempt,
            attempt_id,
        )

        if attempt is not None:
            attempt.result = "failed"
            attempt.error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            attempt.external_message_id = None
            attempt.external_url = None

            session.add(
                attempt
            )

        session.commit()

        raise
