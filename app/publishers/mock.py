from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MockPublishedPost
from app.publishers.base import (
    PublishResult,
    SocialPublisher,
)


class DatabaseMockPublisher(
    SocialPublisher
):
    def __init__(
        self,
        *,
        session: Session,
        name: str,
    ) -> None:
        self.session = session
        self.name = name

    def publish(
        self,
        *,
        variant_id: int,
        content: str,
        idempotency_key: str,
    ) -> PublishResult:
        existing = self.session.scalar(
            select(MockPublishedPost)
            .where(
                MockPublishedPost.idempotency_key
                == idempotency_key
            )
        )

        if existing is not None:
            return PublishResult(
                publisher=self.name,
                external_message_id=(
                    f"mock-{existing.id}"
                ),
                external_url=(
                    f"mock://{self.name}/"
                    f"{existing.id}"
                ),
            )

        record = MockPublishedPost(
            platform=self.name,
            variant_id=variant_id,
            content=content,
            idempotency_key=idempotency_key,
        )

        self.session.add(record)
        self.session.flush()

        # Treat the mock-platform row as the external side
        # effect. Commit it before returning so a process
        # crash after adapter success can be reconciled on
        # retry through the stable idempotency key.
        self.session.commit()
        self.session.refresh(record)

        return PublishResult(
            publisher=self.name,
            external_message_id=(
                f"mock-{record.id}"
            ),
            external_url=(
                f"mock://{self.name}/"
                f"{record.id}"
            ),
        )


class MockXPublisher(
    DatabaseMockPublisher
):
    def __init__(
        self,
        *,
        session: Session,
    ) -> None:
        super().__init__(
            session=session,
            name="mock_x",
        )


class MockLinkedInPublisher(
    DatabaseMockPublisher
):
    def __init__(
        self,
        *,
        session: Session,
    ) -> None:
        super().__init__(
            session=session,
            name="mock_linkedin",
        )
