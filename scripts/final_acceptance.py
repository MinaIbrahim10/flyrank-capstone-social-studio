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
import tempfile
import time

SCRIPT_PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

if str(SCRIPT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(SCRIPT_PROJECT_ROOT),
    )


import httpx
from dotenv import load_dotenv
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
    Variant,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

load_dotenv(
    PROJECT_ROOT
    / ".env",
    override=True,
)


def wait_until(
    predicate,
    *,
    timeout: float,
    interval: float = 0.25,
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
            interval
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


def create_post_and_variants(
    client: TestClient,
    *,
    title: str,
) -> list[dict]:
    post = client.post(
        "/posts",
        json={
            "title":
                title,

            "markdown":
                (
                    "# Durable Social Publishing\n\n"
                    "A stored source becomes "
                    "platform-specific social content. "
                    "Human approval protects publishing "
                    "and idempotency protects retries."
                ),
        },
    )

    assert (
        post.status_code
        == 201
    ), post.text

    generated = client.post(
        f"/posts/{post.json()['id']}/variants"
    )

    assert (
        generated.status_code
        == 201
    ), generated.text

    return generated.json()


def approve_and_schedule(
    client: TestClient,
    *,
    variant: dict,
    scheduled_at: datetime,
) -> dict:
    approved = client.post(
        f"/variants/{variant['id']}/approve"
    )

    assert (
        approved.status_code
        == 200
    ), approved.text

    assert (
        approved.json()[
            "status"
        ]
        == "approved"
    )

    scheduled = client.post(
        f"/variants/{variant['id']}/schedule",
        json={
            "scheduled_at":
                scheduled_at.isoformat(),
        },
    )

    assert (
        scheduled.status_code
        == 201
    ), scheduled.text

    return scheduled.json()


def database_counts(
    database_url: str,
) -> dict[str, int]:
    db = Database(
        database_url
    )

    try:
        with db.SessionLocal() as session:
            return {
                "mock_posts":
                    int(
                        session.scalar(
                            select(
                                func.count(
                                    MockPublishedPost.id
                                )
                            )
                        )
                        or 0
                    ),

                "receipts":
                    int(
                        session.scalar(
                            select(
                                func.count(
                                    PublishReceipt.id
                                )
                            )
                        )
                        or 0
                    ),

                "success":
                    int(
                        session.scalar(
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
                        or 0
                    ),

                "started":
                    int(
                        session.scalar(
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
                        or 0
                    ),
            }

    finally:
        db.dispose()


# ============================================================
# PROBE 1
# ============================================================

with tempfile.TemporaryDirectory() as tmp:
    probe_db = (
        Path(tmp)
        / "probe123.db"
    )

    app = create_app(
        "sqlite:///"
        + str(probe_db)
    )

    with TestClient(app) as client:
        variants = (
            create_post_and_variants(
                client,
                title=(
                    "Acceptance Probe Source"
                ),
            )
        )

        assert len(
            variants
        ) == 3

        assert {
            item[
                "platform"
            ]
            for item
            in variants
        } == {
            "discord",
            "mock_x",
            "mock_linkedin",
        }

        assert len(
            {
                item[
                    "content"
                ]
                for item
                in variants
            }
        ) >= 2

        for variant in variants:
            validated = client.post(
                "/variants/validate",
                json={
                    "platform":
                        variant[
                            "platform"
                        ],

                    "content":
                        variant[
                            "content"
                        ],
                },
            )

            assert (
                validated.status_code
                == 200
            ), validated.text

        print(
            "PROBE 1: PASS — stored post generated "
            "three valid platform variants"
        )

        # ====================================================
        # PROBE 2
        # ====================================================

        broken = client.post(
            "/variants/validate",
            json={
                "platform":
                    "mock_x",

                "content":
                    "x" * 281,
            },
        )

        assert (
            broken.status_code
            == 422
        )

        rules = {
            item[
                "rule"
            ]
            for item
            in broken.json()[
                "detail"
            ][
                "violations"
            ]
        }

        assert (
            "max_length"
            in rules
        )

        print(
            "PROBE 2: PASS — invalid variant blocked "
            "before review with named max_length rule"
        )

        # ====================================================
        # PROBE 3
        # ====================================================

        draft_discord = next(
            item
            for item in variants
            if item[
                "platform"
            ]
            == "discord"
        )

        blocked = client.post(
            f"/variants/{draft_discord['id']}/schedule",
            json={
                "scheduled_at":
                    (
                        datetime.now(
                            timezone.utc
                        )
                        + timedelta(
                            minutes=10
                        )
                    ).isoformat(),
            },
        )

        assert (
            400
            <= blocked.status_code
            < 500
        )

        assert (
            "approved"
            in str(
                blocked.json()
            ).lower()
        )

        print(
            "PROBE 3: PASS — unapproved scheduling "
            f"blocked with HTTP {blocked.status_code}"
        )


# ============================================================
# PROBE 5 — TRUE SIDE-EFFECT CRASH + RETRY
# ============================================================

with tempfile.TemporaryDirectory() as tmp:
    root = Path(
        tmp
    )

    database_path = (
        root
        / "probe5.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    app = create_app(
        database_url
    )

    with TestClient(app) as client:
        variants = (
            create_post_and_variants(
                client,
                title=(
                    "Probe Five Crash Retry"
                ),
            )
        )

        target = next(
            item
            for item in variants
            if item[
                "platform"
            ]
            == "mock_x"
        )

        slot = approve_and_schedule(
            client,
            variant=target,
            scheduled_at=(
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    seconds=1.0
                )
            ),
        )

    marker = (
        root
        / "probe5.marker"
    )

    first_env = (
        os.environ.copy()
    )

    first_env.update(
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

    first_worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.worker",
        ],
        cwd=str(
            PROJECT_ROOT
        ),
        env=first_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        first_code = (
            first_worker.wait(
                timeout=15
            )
        )

    except subprocess.TimeoutExpired:
        terminate(
            first_worker
        )

        raise RuntimeError(
            "Probe 5 crash point was not reached."
        )

    assert (
        first_code
        == 87
    )

    assert marker.exists()

    after_crash = (
        database_counts(
            database_url
        )
    )

    assert after_crash == {
        "mock_posts":
            1,

        "receipts":
            0,

        "success":
            0,

        "started":
            1,
    }

    second_env = (
        os.environ.copy()
    )

    second_env.update(
        {
            "DATABASE_URL":
                database_url,

            "PUBLISHER_OVERRIDE":
                "mock_x",

            "SCHEDULER_POLL_SECONDS":
                "0.15",
        }
    )

    second_env.pop(
        (
            "SOCIAL_STUDIO_TEST_"
            "CRASH_AFTER_ADAPTER"
        ),
        None,
    )

    second_env.pop(
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
            PROJECT_ROOT
        ),
        env=second_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        recovered = wait_until(
            lambda: (
                database_counts(
                    database_url
                )[
                    "receipts"
                ]
                == 1
            ),
            timeout=15,
        )

        assert recovered

    finally:
        terminate(
            second_worker
        )

    final_state = (
        database_counts(
            database_url
        )
    )

    assert (
        final_state[
            "mock_posts"
        ]
        == 1
    )

    assert (
        final_state[
            "receipts"
        ]
        == 1
    )

    assert (
        final_state[
            "success"
        ]
        == 1
    )

    assert (
        final_state[
            "started"
        ]
        == 1
    )

    db = Database(
        database_url
    )

    try:
        with db.SessionLocal() as session:
            slot_row = session.get(
                ScheduleSlot,
                slot[
                    "id"
                ],
            )

            assert (
                slot_row is not None
            )

            assert (
                slot_row.status
                == "published"
            )

    finally:
        db.dispose()

    print(
        "PROBE 5: PASS — worker crashed after "
        "external mock side effect, restart retried, "
        "exactly one external post exists"
    )


# ============================================================
# PROBE 6 — CONFIG-ONLY ADAPTER SWAP
# ============================================================

with tempfile.TemporaryDirectory() as tmp:
    database_path = (
        Path(tmp)
        / "probe6.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    app = create_app(
        database_url
    )

    with TestClient(app) as client:
        variants = (
            create_post_and_variants(
                client,
                title=(
                    "Probe Six Adapter Swap"
                ),
            )
        )

        # The campaign variant is Discord.
        discord_variant = next(
            item
            for item in variants
            if item[
                "platform"
            ]
            == "discord"
        )

        slot = approve_and_schedule(
            client,
            variant=discord_variant,
            scheduled_at=(
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    seconds=1.0
                )
            ),
        )

    swap_env = (
        os.environ.copy()
    )

    swap_env.update(
        {
            "DATABASE_URL":
                database_url,

            # Only configuration changes.
            "PUBLISHER_OVERRIDE":
                "mock_x",

            "SCHEDULER_POLL_SECONDS":
                "0.15",
        }
    )

    swap_worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.worker",
        ],
        cwd=str(
            PROJECT_ROOT
        ),
        env=swap_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        swapped = wait_until(
            lambda: (
                database_counts(
                    database_url
                )[
                    "mock_posts"
                ]
                == 1
            ),
            timeout=15,
        )

        assert swapped

    finally:
        terminate(
            swap_worker
        )

    db = Database(
        database_url
    )

    try:
        with db.SessionLocal() as session:
            mock_post = session.scalar(
                select(
                    MockPublishedPost
                )
            )

            receipt = session.scalar(
                select(
                    PublishReceipt
                )
                .where(
                    PublishReceipt.slot_id
                    == slot[
                        "id"
                    ]
                )
            )

            assert (
                mock_post is not None
            )

            assert (
                mock_post.platform
                == "mock_x"
            )

            assert (
                receipt is not None
            )

            assert (
                receipt.publisher
                == "mock_x"
            )

    finally:
        db.dispose()

    print(
        "PROBE 6: PASS — Discord campaign routed "
        "through Mock X using configuration only"
    )


# ============================================================
# PROBE 4 — REAL DISCORD, TWO MINUTES OUT
# ============================================================

webhook = os.getenv(
    "DISCORD_WEBHOOK_URL",
    "",
).strip()

if not webhook.startswith(
    "https://discord.com/api/webhooks/"
):
    raise RuntimeError(
        "Probe 4 requires the real local Discord webhook."
    )


real_db_path = (
    PROJECT_ROOT
    / "data"
    / "final_core_gate.db"
)

real_db_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

real_database_url = (
    "sqlite:///"
    + str(
        real_db_path.resolve()
    )
)

real_app = create_app(
    real_database_url
)


def existing_real_receipt() -> PublishReceipt | None:
    db = Database(
        real_database_url
    )

    try:
        db.create_all()

        with db.SessionLocal() as session:
            return session.scalar(
                select(
                    PublishReceipt
                )
                .where(
                    PublishReceipt.publisher
                    == "discord"
                )
                .order_by(
                    PublishReceipt.id
                )
            )

    finally:
        db.dispose()


receipt = (
    existing_real_receipt()
)

slot_id: int

if receipt is None:
    # Refuse to blindly repeat an interrupted historical real
    # Discord gate. This avoids creating an uncontrolled duplicate
    # if a previous process died after Discord accepted a message.
    db = Database(
        real_database_url
    )

    try:
        db.create_all()

        with db.SessionLocal() as session:
            old_slots = session.scalars(
                select(
                    ScheduleSlot
                )
            ).all()

            if old_slots:
                raise RuntimeError(
                    "An incomplete previous real Discord "
                    "final gate exists without a receipt. "
                    "The script will not blindly resend."
                )

    finally:
        db.dispose()

    with TestClient(
        real_app
    ) as client:
        variants = (
            create_post_and_variants(
                client,
                title=(
                    "Final Automatic Discord Scheduler Gate"
                ),
            )
        )

        discord_variant = next(
            item
            for item in variants
            if item[
                "platform"
            ]
            == "discord"
        )

        scheduled_for = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                minutes=2
            )
        )

        slot = approve_and_schedule(
            client,
            variant=discord_variant,
            scheduled_at=(
                scheduled_for
            ),
        )

        slot_id = int(
            slot[
                "id"
            ]
        )

        print(
            "PROBE 4: real Discord slot created"
        )

        print(
            "Scheduled approximately two minutes out:",
            scheduled_for.isoformat(),
        )

    worker_env = (
        os.environ.copy()
    )

    worker_env.update(
        {
            "DATABASE_URL":
                real_database_url,

            "PUBLISHER_OVERRIDE":
                "discord",

            "SCHEDULER_POLL_SECONDS":
                "1",
        }
    )

    real_worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.worker",
        ],
        cwd=str(
            PROJECT_ROOT
        ),
        env=worker_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print(
            "Waiting for automatic scheduler..."
        )

        # Explicitly prove it did not fire early.
        time.sleep(
            30
        )

        early = (
            existing_real_receipt()
        )

        assert (
            early is None
        )

        print(
            "PROBE 4 early-publish check: PASS "
            "— still unpublished after 30 seconds"
        )

        start_wait = time.monotonic()

        last_notice = -1

        while True:
            receipt = (
                existing_real_receipt()
            )

            if receipt is not None:
                break

            elapsed = int(
                time.monotonic()
                - start_wait
            )

            notice = (
                elapsed
                // 15
            )

            if notice != last_notice:
                last_notice = notice

                print(
                    "Still waiting for scheduled "
                    "Discord delivery...",
                    f"elapsed_after_early_check={elapsed}s",
                    flush=True,
                )

            if elapsed > 170:
                raise RuntimeError(
                    "Real Discord automatic scheduler "
                    "did not publish within the gate timeout."
                )

            time.sleep(
                2
            )

    finally:
        terminate(
            real_worker
        )

    assert (
        receipt is not None
    )

    slot_id = int(
        receipt.slot_id
    )

else:
    slot_id = int(
        receipt.slot_id
    )

    print(
        "PROBE 4: existing successful real "
        "Discord gate receipt found; reusing it safely"
    )


assert receipt is not None

message_id = (
    receipt.external_message_id
)

message_url = (
    receipt.external_url
)

assert message_id

assert message_url

assert message_url.startswith(
    "https://discord.com/channels/"
)


# Verify the message remotely from Discord.
message_endpoint = (
    webhook.split(
        "?",
        1,
    )[0]
    .rstrip("/")
    + "/messages/"
    + str(
        message_id
    )
)

remote = httpx.get(
    message_endpoint,
    timeout=15.0,
)

remote.raise_for_status()

remote_payload = (
    remote.json()
)

assert str(
    remote_payload.get(
        "id"
    )
) == str(
    message_id
)


# Verify local slot/history state.
db = Database(
    real_database_url
)

try:
    with db.SessionLocal() as session:
        slot_row = session.get(
            ScheduleSlot,
            slot_id,
        )

        assert (
            slot_row is not None
        )

        assert (
            slot_row.status
            == "published"
        )

        successes = session.scalars(
            select(
                PublishAttempt
            )
            .where(
                PublishAttempt.slot_id
                == slot_id,
                PublishAttempt.result
                == "success",
            )
        ).all()

        receipts = session.scalars(
            select(
                PublishReceipt
            )
            .where(
                PublishReceipt.slot_id
                == slot_id
            )
        ).all()

        assert len(
            successes
        ) == 1

        assert len(
            receipts
        ) == 1

finally:
    db.dispose()


# Retry through the API only AFTER the scheduler completed.
#
# This must resolve the persistent receipt and must not call the
# Discord adapter again.
with TestClient(
    create_app(
        real_database_url
    )
) as retry_client:
    retry = retry_client.post(
        f"/schedules/{slot_id}/publish"
    )

    assert (
        retry.status_code
        == 200
    ), retry.text

    retry_payload = (
        retry.json()
    )

    assert (
        retry_payload[
            "duplicate_prevented"
        ]
        is True
    )

    assert str(
        retry_payload[
            "external_message_id"
        ]
    ) == str(
        message_id
    )

    assert (
        retry_payload[
            "external_url"
        ]
        == message_url
    )


# Re-fetch same real message after retry.
remote_again = httpx.get(
    message_endpoint,
    timeout=15.0,
)

remote_again.raise_for_status()

assert str(
    remote_again.json().get(
        "id"
    )
) == str(
    message_id
)


print(
    "PROBE 4: PASS — approved variant was "
    "automatically published by the worker "
    "about two minutes after scheduling"
)

print(
    "PROBE 4 real Discord message ID:",
    message_id,
)

print(
    "PROBE 4 live Discord URL:",
    message_url,
)

print(
    "PROBE 4 retry protection: PASS — "
    "persistent receipt reused"
)

print()
print(
    "========================================"
)

print(
    "ALL SIX FINAL ACCEPTANCE PROBES: PASS"
)

print(
    "========================================"
)
