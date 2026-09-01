from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import os

from sqlalchemy import select

from app.db import Database
from app.models import (
    Post,
    ScheduleSlot,
    Variant,
)
from app.services.generator import (
    generate_variants,
)
from app.services.review import (
    approve_variant,
)
from app.services.scheduling import (
    create_schedule_slot,
)


DEFAULT_DATABASE_URL = (
    "sqlite:///./data/demo.db"
)


def main() -> int:
    database_url = os.getenv(
        "DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )

    database = Database(
        database_url
    )

    database.create_all()

    try:
        with database.SessionLocal() as session:
            post = session.scalar(
                select(
                    Post
                )
                .where(
                    Post.title
                    == "Social Media Studio Demo"
                )
            )

            if post is None:
                post = Post(
                    title=(
                        "Social Media Studio Demo"
                    ),
                    source_type="markdown",
                    source_url=None,
                    markdown=(
                        "# Social Media Studio Demo\n\n"
                        "One stored blog post becomes "
                        "reviewable platform-specific "
                        "social variants. The demo "
                        "publishes only to Mock X."
                    ),
                )

                session.add(
                    post
                )

                session.commit()
                session.refresh(
                    post
                )

            variants = generate_variants(
                session,
                post,
            )

            target = next(
                item
                for item in variants
                if item.platform
                == "mock_x"
            )

            if target.status == "draft":
                target = approve_variant(
                    session,
                    target.id,
                )

            existing_slot = session.scalar(
                select(
                    ScheduleSlot
                )
                .where(
                    ScheduleSlot.variant_id
                    == target.id
                )
                .order_by(
                    ScheduleSlot.id.desc()
                )
            )

            if (
                target.status
                == "approved"
                and existing_slot
                is None
            ):
                existing_slot = (
                    create_schedule_slot(
                        session,
                        variant=target,
                        scheduled_at=(
                            datetime.now(
                                timezone.utc
                            )
                            + timedelta(
                                seconds=8
                            )
                        ),
                    )
                )

            print(
                "DEMO SEED: PASS"
            )

            print(
                f"Post ID: {post.id}"
            )

            print(
                f"Mock X variant ID: {target.id}"
            )

            if existing_slot is not None:
                print(
                    "Schedule slot ID:",
                    existing_slot.id,
                )

            print(
                "Demo publishing target: mock_x"
            )

    finally:
        database.dispose()

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
