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


def wait_until(
    predicate,
    *,
    timeout: float = 12.0,
) -> bool:
    end = (
        time.monotonic()
        + timeout
    )

    while (
        time.monotonic()
        < end
    ):
        if predicate():
            return True

        time.sleep(
            0.15
        )

    return bool(
        predicate()
    )


def terminate(
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


def create_due_mock_slot(
    client: TestClient,
) -> int:
    post = client.post(
        "/posts",
        json={
            "title":
                "True Crash Recovery",

            "markdown":
                (
                    "An external social side effect "
                    "must not be duplicated when a "
                    "worker dies before writing its "
                    "local receipt."
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
                (
                    datetime.now(
                        timezone.utc
                    )
                    + timedelta(
                        seconds=0.9
                    )
                ).isoformat(),
        },
    )

    assert (
        scheduled.status_code
        == 201
    )

    return int(
        scheduled.json()[
            "id"
        ]
    )


def state(
    database_url: str,
    slot_id: int,
) -> dict[str, object]:
    db = Database(
        database_url
    )

    try:
        with db.SessionLocal() as session:
            mock_posts = session.scalar(
                select(
                    func.count(
                        MockPublishedPost.id
                    )
                )
            )

            receipts = session.scalar(
                select(
                    func.count(
                        PublishReceipt.id
                    )
                )
            )

            successful = session.scalar(
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

            started = session.scalar(
                select(
                    func.count(
                        PublishAttempt.id
                    )
                )
                .where(
                    PublishAttempt.result
                    == "started"
                )
            )

            slot = session.get(
                ScheduleSlot,
                slot_id,
            )

            return {
                "mock_posts":
                    int(
                        mock_posts
                        or 0
                    ),

                "receipts":
                    int(
                        receipts
                        or 0
                    ),

                "successful":
                    int(
                        successful
                        or 0
                    ),

                "started":
                    int(
                        started
                        or 0
                    ),

                "slot_status":
                    (
                        slot.status
                        if slot
                        else None
                    ),
            }

    finally:
        db.dispose()


def test_crash_after_external_side_effect_then_restart_exactly_once(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "true_crash.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    app = create_app(
        database_url
    )

    with TestClient(
        app
    ) as client:
        slot_id = (
            create_due_mock_slot(
                client
            )
        )

    marker = (
        tmp_path
        / "after_adapter.marker"
    )

    crash_env = (
        os.environ.copy()
    )

    crash_env.update(
        {
            "DATABASE_URL":
                database_url,

            "PUBLISHER_OVERRIDE":
                "mock_x",

            "SCHEDULER_POLL_SECONDS":
                "0.15",

            (
                "SOCIAL_STUDIO_TEST_"
                "CRASH_AFTER_ADAPTER"
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

    first = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.worker",
        ],
        env=crash_env,
        cwd=str(
            Path.cwd()
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        code = first.wait(
            timeout=12
        )

    except subprocess.TimeoutExpired:
        terminate(
            first
        )

        output = (
            first.stdout.read()
            if first.stdout
            else ""
        )

        raise AssertionError(
            "Worker did not hit the "
            "post-adapter crash window.\n"
            + output
        )

    output_one = (
        first.stdout.read()
        if first.stdout
        else ""
    )

    assert (
        code
        == 87
    ), output_one

    assert marker.exists()

    crashed = state(
        database_url,
        slot_id,
    )

    # The mock external side effect committed.
    assert (
        crashed[
            "mock_posts"
        ]
        == 1
    )

    # The local final receipt did not.
    assert (
        crashed[
            "receipts"
        ]
        == 0
    )

    # The visible attempt proves the interrupted operation.
    assert (
        crashed[
            "started"
        ]
        == 1
    )

    assert (
        crashed[
            "successful"
        ]
        == 0
    )

    assert (
        crashed[
            "slot_status"
        ]
        == "publishing"
    )

    restart_env = (
        os.environ.copy()
    )

    restart_env.update(
        {
            "DATABASE_URL":
                database_url,

            "PUBLISHER_OVERRIDE":
                "mock_x",

            "SCHEDULER_POLL_SECONDS":
                "0.15",
        }
    )

    restart_env.pop(
        (
            "SOCIAL_STUDIO_TEST_"
            "CRASH_AFTER_ADAPTER"
        ),
        None,
    )

    restart_env.pop(
        (
            "SOCIAL_STUDIO_TEST_"
            "CRASH_MARKER"
        ),
        None,
    )

    second = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.worker",
        ],
        env=restart_env,
        cwd=str(
            Path.cwd()
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        completed = wait_until(
            lambda: (
                state(
                    database_url,
                    slot_id,
                )[
                    "slot_status"
                ]
                == "published"
            ),
            timeout=12,
        )

        assert completed

    finally:
        terminate(
            second
        )

    recovered = state(
        database_url,
        slot_id,
    )

    # The retry resolves the original external mock row by its
    # idempotency key instead of creating another row.
    assert (
        recovered[
            "mock_posts"
        ]
        == 1
    )

    assert (
        recovered[
            "receipts"
        ]
        == 1
    )

    assert (
        recovered[
            "successful"
        ]
        == 1
    )

    # Original interrupted attempt remains visible.
    assert (
        recovered[
            "started"
        ]
        == 1
    )

    assert (
        recovered[
            "slot_status"
        ]
        == "published"
    )
