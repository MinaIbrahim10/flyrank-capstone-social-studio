from __future__ import annotations

import os
import signal
import threading

from dotenv import load_dotenv

from app.services.worker import (
    start_background_worker,
)


DEFAULT_DATABASE_URL = (
    "sqlite:///./data/social_studio.db"
)


def main() -> int:
    load_dotenv(
        ".env",
        override=False,
    )

    database_url = os.getenv(
        "DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )

    try:
        poll_seconds = float(
            os.getenv(
                "SCHEDULER_POLL_SECONDS",
                "2",
            )
        )

    except ValueError as exc:
        raise SystemExit(
            "SCHEDULER_POLL_SECONDS "
            "must be numeric."
        ) from exc

    if poll_seconds <= 0:
        raise SystemExit(
            "SCHEDULER_POLL_SECONDS "
            "must be greater than zero."
        )

    stop_event = (
        threading.Event()
    )

    def request_stop(
        signum: int,
        frame: object,
    ) -> None:
        stop_event.set()

    signal.signal(
        signal.SIGTERM,
        request_stop,
    )

    signal.signal(
        signal.SIGINT,
        request_stop,
    )

    scheduler = (
        start_background_worker(
            database_url=database_url,
            poll_seconds=poll_seconds,
        )
    )

    print(
        "SOCIAL MEDIA STUDIO WORKER: READY",
        flush=True,
    )

    print(
        f"Database: {database_url}",
        flush=True,
    )

    print(
        f"Poll seconds: {poll_seconds}",
        flush=True,
    )

    try:
        while not stop_event.wait(
            0.25
        ):
            pass

    finally:
        scheduler.shutdown(
            wait=True
        )

        print(
            "SOCIAL MEDIA STUDIO WORKER: STOPPED",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
