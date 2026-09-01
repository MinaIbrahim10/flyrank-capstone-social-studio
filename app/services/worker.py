from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
import os
from pathlib import Path
from typing import Any

from apscheduler.jobstores.sqlalchemy import (
    SQLAlchemyJobStore,
)
from apscheduler.schedulers.background import (
    BackgroundScheduler,
)
from sqlalchemy import select

from app import models as models  # noqa: F401
from app.db import Database
from app.models import (
    PublishReceipt,
    ScheduleSlot,
)
from app.services.publishing import (
    PublishInProgress,
    PublishNotAllowed,
    ScheduleNotFound,
    publish_slot,
)


BATCH_JOB_ID = "publish-due-batch"


def as_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value.astimezone(
        timezone.utc
    )


def due_slot_ids(
    database_url: str,
    *,
    now: datetime | None = None,
) -> list[int]:
    database = Database(
        database_url
    )

    database.create_all()

    current = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    current = as_utc(
        current
    )

    try:
        with database.SessionLocal() as session:
            candidates = session.scalars(
                select(
                    ScheduleSlot
                )
                .where(
                    ScheduleSlot.status
                    == "scheduled"
                )
                .order_by(
                    ScheduleSlot.scheduled_at,
                    ScheduleSlot.id,
                )
            ).all()

            return [
                slot.id
                for slot in candidates
                if as_utc(
                    slot.scheduled_at
                )
                <= current
            ]

    finally:
        database.dispose()


def write_crash_marker(
    *,
    successful_count: int,
    slot_id: int,
) -> None:
    marker = os.getenv(
        "SOCIAL_STUDIO_TEST_CRASH_MARKER",
        "",
    ).strip()

    if not marker:
        return

    path = Path(
        marker
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        (
            "intentional-worker-crash\n"
            f"successful_count={successful_count}\n"
            f"last_successful_slot={slot_id}\n"
        )
    )


def requested_test_crash_after() -> int:
    raw = os.getenv(
        "SOCIAL_STUDIO_TEST_CRASH_AFTER_SUCCESSES",
        "0",
    ).strip()

    if not raw:
        return 0

    try:
        value = int(
            raw
        )

    except ValueError as exc:
        raise ValueError(
            "SOCIAL_STUDIO_TEST_CRASH_AFTER_SUCCESSES "
            "must be an integer."
        ) from exc

    if value < 0:
        raise ValueError(
            "SOCIAL_STUDIO_TEST_CRASH_AFTER_SUCCESSES "
            "cannot be negative."
        )

    return value


def run_due_batch(
    database_url: str,
) -> dict[str, Any]:
    slot_ids = due_slot_ids(
        database_url
    )

    result: dict[str, Any] = {
        "due": len(slot_ids),
        "successful": 0,
        "duplicate_prevented": 0,
        "failed": 0,
        "slots": [],
    }

    crash_after = (
        requested_test_crash_after()
    )

    database = Database(
        database_url
    )

    database.create_all()

    try:
        for slot_id in slot_ids:
            try:
                with (
                    database.SessionLocal()
                    as session
                ):
                    outcome = publish_slot(
                        session,
                        slot_id=slot_id,
                    )

                result[
                    "successful"
                ] += 1

                if (
                    outcome
                    .duplicate_prevented
                ):
                    result[
                        "duplicate_prevented"
                    ] += 1

                result[
                    "slots"
                ].append(
                    {
                        "slot_id":
                            slot_id,
                        "status":
                            "success",
                        "duplicate_prevented":
                            outcome
                            .duplicate_prevented,
                    }
                )

                if (
                    crash_after > 0
                    and result[
                        "successful"
                    ]
                    >= crash_after
                ):
                    write_crash_marker(
                        successful_count=(
                            result[
                                "successful"
                            ]
                        ),
                        slot_id=slot_id,
                    )

                    # This is an intentionally hard process
                    # termination used only by the deterministic
                    # crash/restart acceptance test.
                    #
                    # The successful publish has already committed.
                    # Remaining slots in the durable database have
                    # not been claimed yet.
                    os._exit(86)

            except (
                ScheduleNotFound,
                PublishNotAllowed,
                PublishInProgress,
            ) as exc:
                result[
                    "failed"
                ] += 1

                result[
                    "slots"
                ].append(
                    {
                        "slot_id":
                            slot_id,
                        "status":
                            "failed",
                        "error":
                            (
                                f"{type(exc).__name__}: "
                                f"{exc}"
                            ),
                    }
                )

            except Exception as exc:
                result[
                    "failed"
                ] += 1

                result[
                    "slots"
                ].append(
                    {
                        "slot_id":
                            slot_id,
                        "status":
                            "failed",
                        "error":
                            (
                                f"{type(exc).__name__}: "
                                f"{exc}"
                            ),
                    }
                )

    finally:
        database.dispose()

    if slot_ids:
        print(
            "WORKER_BATCH",
            f"due={result['due']}",
            f"successful={result['successful']}",
            (
                "duplicate_prevented="
                f"{result['duplicate_prevented']}"
            ),
            f"failed={result['failed']}",
            flush=True,
        )

    return result


def recover_incomplete_claims(
    database_url: str,
) -> int:
    """Recover claims left by a worker process that no longer exists.

    This runs only at worker startup. A `publishing` slot with no
    receipt is returned to `scheduled`, allowing the restarted worker
    to retry it. If a receipt already exists, the slot is repaired to
    `published`.
    """
    database = Database(
        database_url
    )

    database.create_all()

    recovered = 0

    try:
        with database.SessionLocal() as session:
            slots = session.scalars(
                select(
                    ScheduleSlot
                )
                .where(
                    ScheduleSlot.status
                    == "publishing"
                )
                .order_by(
                    ScheduleSlot.id
                )
            ).all()

            for slot in slots:
                receipt = session.scalar(
                    select(
                        PublishReceipt
                    )
                    .where(
                        PublishReceipt.slot_id
                        == slot.id
                    )
                )

                if receipt is not None:
                    slot.status = "published"

                else:
                    slot.status = "scheduled"

                session.add(
                    slot
                )

                recovered += 1

            session.commit()

    finally:
        database.dispose()

    if recovered:
        print(
            "WORKER_RECOVERY",
            f"claims={recovered}",
            flush=True,
        )

    return recovered


def build_scheduler(
    database_url: str,
) -> BackgroundScheduler:
    return BackgroundScheduler(
        jobstores={
            "default":
                SQLAlchemyJobStore(
                    url=database_url
                )
        },
        timezone=timezone.utc,
        daemon=True,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )


def install_due_batch_job(
    scheduler: BackgroundScheduler,
    *,
    database_url: str,
    poll_seconds: float,
) -> None:
    if poll_seconds <= 0:
        raise ValueError(
            "poll_seconds must be greater than zero."
        )

    scheduler.add_job(
        run_due_batch,
        trigger="interval",
        seconds=poll_seconds,
        kwargs={
            "database_url":
                database_url,
        },
        id=BATCH_JOB_ID,
        name=(
            "Publish due Social Media "
            "Studio schedule slots"
        ),
        replace_existing=True,
        next_run_time=datetime.now(
            timezone.utc
        ),
    )


def start_background_worker(
    *,
    database_url: str,
    poll_seconds: float,
    paused: bool = False,
) -> BackgroundScheduler:
    database = Database(
        database_url
    )

    database.create_all()
    database.dispose()

    recover_incomplete_claims(
        database_url
    )

    scheduler = build_scheduler(
        database_url
    )

    scheduler.start(
        paused=True
    )

    install_due_batch_job(
        scheduler,
        database_url=database_url,
        poll_seconds=poll_seconds,
    )

    if not paused:
        scheduler.resume()

    return scheduler
