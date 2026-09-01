from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import (
    func,
    select,
)

from app.db import Database
from app.main import create_app
from app.models import (
    MockPublishedPost,
    PublishAttempt,
    PublishReceipt,
    ScheduleSlot,
)
from app.services.worker import (
    BATCH_JOB_ID,
    build_scheduler,
    install_due_batch_job,
    start_background_worker,
)


def future_time(
    seconds: float,
) -> str:
    return (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            seconds=seconds
        )
    ).isoformat()


def wait_until(
    predicate,
    *,
    timeout: float = 8.0,
    interval: float = 0.1,
) -> bool:
    deadline = (
        time.monotonic()
        + timeout
    )

    while (
        time.monotonic()
        < deadline
    ):
        if predicate():
            return True

        time.sleep(
            interval
        )

    return bool(
        predicate()
    )


def prepare_mock_x_slot(
    client: TestClient,
    *,
    title: str,
    scheduled_at: str,
) -> tuple[int, int]:
    post = client.post(
        "/posts",
        json={
            "title":
                title,

            "markdown":
                (
                    "Durable scheduling must survive "
                    "worker restarts and must not "
                    "duplicate social posts."
                ),
        },
    )

    assert (
        post.status_code
        == 201
    )

    variants = client.post(
        f"/posts/{post.json()['id']}/variants"
    )

    assert (
        variants.status_code
        == 201
    )

    variant = next(
        item
        for item in variants.json()
        if item[
            "platform"
        ]
        == "mock_x"
    )

    approved = client.post(
        f"/variants/{variant['id']}/approve"
    )

    assert (
        approved.status_code
        == 200
    )

    scheduled = client.post(
        f"/variants/{variant['id']}/schedule",
        json={
            "scheduled_at":
                scheduled_at,
        },
    )

    assert (
        scheduled.status_code
        == 201
    )

    return (
        variant["id"],
        scheduled.json()["id"],
    )


def database_counts(
    database_url: str,
) -> tuple[int, int, int]:
    database = Database(
        database_url
    )

    try:
        with (
            database.SessionLocal()
            as session
        ):
            receipts = session.scalar(
                select(
                    func.count(
                        PublishReceipt.id
                    )
                )
            )

            posts = session.scalar(
                select(
                    func.count(
                        MockPublishedPost.id
                    )
                )
            )

            successes = session.scalar(
                select(
                    func.count(
                        PublishAttempt.id
                    )
                )
                .where(
                    PublishAttempt.result
                    == "success"
                )
            )

            return (
                int(
                    receipts
                    or 0
                ),
                int(
                    posts
                    or 0
                ),
                int(
                    successes
                    or 0
                ),
            )

    finally:
        database.dispose()


def terminate_process(
    process: subprocess.Popen,
) -> None:
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(
            timeout=5
        )

    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(
            timeout=5
        )


def test_apscheduler_job_store_survives_restart(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "persistent_jobs.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    database = Database(
        database_url
    )

    database.create_all()
    database.dispose()

    first = build_scheduler(
        database_url
    )

    first.start(
        paused=True
    )

    try:
        install_due_batch_job(
            first,
            database_url=database_url,
            poll_seconds=10,
        )

        job = first.get_job(
            BATCH_JOB_ID
        )

        assert job is not None

    finally:
        first.shutdown(
            wait=False
        )

    second = build_scheduler(
        database_url
    )

    second.start(
        paused=True
    )

    try:
        persisted = second.get_job(
            BATCH_JOB_ID
        )

        assert persisted is not None

        assert (
            persisted.id
            == BATCH_JOB_ID
        )

    finally:
        second.shutdown(
            wait=False
        )


def test_worker_does_not_publish_future_slot_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    database_path = (
        tmp_path
        / "future.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    app = create_app(
        database_url
    )

    with TestClient(app) as client:
        prepare_mock_x_slot(
            client,
            title="Future Slot",
            scheduled_at=(
                future_time(
                    2.0
                )
            ),
        )

        scheduler = (
            start_background_worker(
                database_url=database_url,
                poll_seconds=0.15,
            )
        )

        try:
            time.sleep(
                0.6
            )

            posts = client.get(
                "/mock-posts"
            )

            assert (
                posts.status_code
                == 200
            )

            assert (
                len(
                    posts.json()
                )
                == 0
            )

        finally:
            scheduler.shutdown(
                wait=True
            )


def test_due_slot_publishes_automatically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    database_path = (
        tmp_path
        / "automatic.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    app = create_app(
        database_url
    )

    with TestClient(app) as client:
        variant_id, slot_id = (
            prepare_mock_x_slot(
                client,
                title=(
                    "Automatic Scheduled Publish"
                ),
                scheduled_at=(
                    future_time(
                        0.8
                    )
                ),
            )
        )

        scheduler = (
            start_background_worker(
                database_url=database_url,
                poll_seconds=0.15,
            )
        )

        try:
            success = wait_until(
                lambda: (
                    client.get(
                        f"/schedules/{slot_id}"
                    ).json()[
                        "status"
                    ]
                    == "published"
                ),
                timeout=6,
            )

            assert success

            variant = client.get(
                f"/variants/{variant_id}"
            )

            assert (
                variant.json()[
                    "status"
                ]
                == "published"
            )

            mock_posts = client.get(
                "/mock-posts"
            )

            assert (
                len(
                    mock_posts.json()
                )
                == 1
            )

            history = client.get(
                "/publish-history"
            )

            successes = [
                row
                for row
                in history.json()
                if row[
                    "result"
                ]
                == "success"
            ]

            assert (
                len(
                    successes
                )
                == 1
            )

        finally:
            scheduler.shutdown(
                wait=True
            )


def test_restart_after_schedule_becomes_due(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    database_path = (
        tmp_path
        / "restart.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    app = create_app(
        database_url
    )

    with TestClient(app) as client:
        _, slot_id = (
            prepare_mock_x_slot(
                client,
                title=(
                    "Restart Persistence"
                ),
                scheduled_at=(
                    future_time(
                        1.2
                    )
                ),
            )
        )

        first = (
            start_background_worker(
                database_url=database_url,
                poll_seconds=0.15,
            )
        )

        time.sleep(
            0.35
        )

        first.shutdown(
            wait=True
        )

        slot_before = client.get(
            f"/schedules/{slot_id}"
        )

        assert (
            slot_before.json()[
                "status"
            ]
            == "scheduled"
        )

        time.sleep(
            1.1
        )

        second = (
            start_background_worker(
                database_url=database_url,
                poll_seconds=0.15,
            )
        )

        try:
            success = wait_until(
                lambda: (
                    client.get(
                        f"/schedules/{slot_id}"
                    ).json()[
                        "status"
                    ]
                    == "published"
                ),
                timeout=6,
            )

            assert success

            assert (
                len(
                    client.get(
                        "/mock-posts"
                    ).json()
                )
                == 1
            )

        finally:
            second.shutdown(
                wait=True
            )


def test_hard_worker_crash_mid_batch_then_restart_has_zero_duplicates(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "crash_batch.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    app = create_app(
        database_url
    )

    scheduled_at = (
        future_time(
            1.0
        )
    )

    with TestClient(app) as client:
        _, slot_one = (
            prepare_mock_x_slot(
                client,
                title=(
                    "Crash Batch First"
                ),
                scheduled_at=(
                    scheduled_at
                ),
            )
        )

        _, slot_two = (
            prepare_mock_x_slot(
                client,
                title=(
                    "Crash Batch Second"
                ),
                scheduled_at=(
                    scheduled_at
                ),
            )
        )

    marker = (
        tmp_path
        / "worker_crashed.marker"
    )

    environment = (
        os.environ.copy()
    )

    environment.update(
        {
            "DATABASE_URL":
                database_url,

            "PUBLISHER_OVERRIDE":
                "mock_x",

            "SCHEDULER_POLL_SECONDS":
                "0.15",

            (
                "SOCIAL_STUDIO_TEST_"
                "CRASH_AFTER_SUCCESSES"
            ):
                "1",

            (
                "SOCIAL_STUDIO_TEST_"
                "CRASH_MARKER"
            ):
                str(
                    marker
                ),
        }
    )

    first_worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.worker",
        ],
        cwd=str(
            Path.cwd()
        ),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        return_code = (
            first_worker.wait(
                timeout=12
            )
        )

    except subprocess.TimeoutExpired:
        terminate_process(
            first_worker
        )

        output = (
            first_worker.stdout.read()
            if first_worker.stdout
            else ""
        )

        raise AssertionError(
            "Crash worker did not terminate "
            "at the deterministic crash point.\n"
            + output
        )

    output_one = (
        first_worker.stdout.read()
        if first_worker.stdout
        else ""
    )

    assert (
        return_code
        == 86
    ), output_one

    assert marker.exists()

    receipts_after_crash, posts_after_crash, successes_after_crash = (
        database_counts(
            database_url
        )
    )

    assert (
        receipts_after_crash
        == 1
    )

    assert (
        posts_after_crash
        == 1
    )

    assert (
        successes_after_crash
        == 1
    )

    restart_environment = (
        os.environ.copy()
    )

    restart_environment.update(
        {
            "DATABASE_URL":
                database_url,

            "PUBLISHER_OVERRIDE":
                "mock_x",

            "SCHEDULER_POLL_SECONDS":
                "0.15",
        }
    )

    restart_environment.pop(
        (
            "SOCIAL_STUDIO_TEST_"
            "CRASH_AFTER_SUCCESSES"
        ),
        None,
    )

    restart_environment.pop(
        (
            "SOCIAL_STUDIO_TEST_"
            "CRASH_MARKER"
        ),
        None,
    )

    second_worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.worker",
        ],
        cwd=str(
            Path.cwd()
        ),
        env=restart_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        completed = wait_until(
            lambda: (
                database_counts(
                    database_url
                )
                == (
                    2,
                    2,
                    2,
                )
            ),
            timeout=12,
            interval=0.15,
        )

        if not completed:
            output_two = (
                second_worker.stdout.read()
                if (
                    second_worker.poll()
                    is not None
                    and second_worker.stdout
                )
                else ""
            )

            raise AssertionError(
                "Restarted worker did not complete "
                "the remaining durable slot.\n"
                + output_two
            )

    finally:
        terminate_process(
            second_worker
        )

    database = Database(
        database_url
    )

    try:
        with (
            database.SessionLocal()
            as session
        ):
            receipts = session.scalars(
                select(
                    PublishReceipt
                )
                .order_by(
                    PublishReceipt.slot_id
                )
            ).all()

            mock_posts = session.scalars(
                select(
                    MockPublishedPost
                )
                .order_by(
                    MockPublishedPost.id
                )
            ).all()

            successes = session.scalars(
                select(
                    PublishAttempt
                )
                .where(
                    PublishAttempt.result
                    == "success"
                )
                .order_by(
                    PublishAttempt.id
                )
            ).all()

            slots = session.scalars(
                select(
                    ScheduleSlot
                )
                .where(
                    ScheduleSlot.id.in_(
                        [
                            slot_one,
                            slot_two,
                        ]
                    )
                )
                .order_by(
                    ScheduleSlot.id
                )
            ).all()

        assert (
            len(
                receipts
            )
            == 2
        )

        assert (
            len(
                mock_posts
            )
            == 2
        )

        assert (
            len(
                successes
            )
            == 2
        )

        assert (
            len(
                {
                    receipt.slot_id
                    for receipt
                    in receipts
                }
            )
            == 2
        )

        assert all(
            slot.status
            == "published"
            for slot
            in slots
        )

        assert {
            slot.id
            for slot
            in slots
        } == {
            slot_one,
            slot_two,
        }

    finally:
        database.dispose()
