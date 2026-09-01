from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import (
    MockPublishedPost,
    PublishAttempt,
    PublishReceipt,
)
from app.publishers.discord import (
    DiscordPublisher,
)
from app.publishers.factory import (
    configured_publisher_name,
)
from app.services.publishing import (
    publish_slot,
)


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    database_path = (
        tmp_path
        / "phase4.db"
    )

    monkeypatch.delenv(
        "PUBLISHER_OVERRIDE",
        raising=False,
    )

    monkeypatch.delenv(
        "DISCORD_WEBHOOK_URL",
        raising=False,
    )

    app = create_app(
        "sqlite:///"
        + str(database_path)
    )

    with TestClient(
        app
    ) as test_client:
        yield test_client


def future_time() -> str:
    return (
        datetime.now(timezone.utc)
        + timedelta(minutes=10)
    ).isoformat()


def prepare_variant(
    client: TestClient,
    platform: str,
) -> tuple[dict, dict]:
    post = client.post(
        "/posts",
        json={
            "title":
                "Reliable Publishing",
            "markdown":
                "A clean publisher adapter "
                "lets business logic publish "
                "without knowing platform details.",
        },
    )

    assert post.status_code == 201

    variants = client.post(
        f"/posts/{post.json()['id']}/variants"
    )

    assert variants.status_code == 201

    variant = next(
        item
        for item in variants.json()
        if item["platform"]
        == platform
    )

    approved = client.post(
        f"/variants/{variant['id']}/approve"
    )

    assert approved.status_code == 200

    scheduled = client.post(
        f"/variants/{variant['id']}/schedule",
        json={
            "scheduled_at":
                future_time(),
        },
    )

    assert scheduled.status_code == 201

    return (
        approved.json(),
        scheduled.json(),
    )


def test_factory_default_uses_scheduled_publisher():
    assert (
        configured_publisher_name(
            "discord",
            override=None,
        )
        == "discord"
    )


def test_factory_override_changes_adapter_only():
    assert (
        configured_publisher_name(
            "discord",
            override="mock_x",
        )
        == "mock_x"
    )

    assert (
        configured_publisher_name(
            "discord",
            override="mock_linkedin",
        )
        == "mock_linkedin"
    )


def test_unknown_publisher_is_rejected():
    with pytest.raises(
        ValueError
    ):
        configured_publisher_name(
            "discord",
            override="unknown",
        )


def test_mock_x_publish_creates_local_post(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    variant, slot = prepare_variant(
        client,
        "mock_x",
    )

    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    response = client.post(
        f"/schedules/{slot['id']}/publish"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["publisher"] == "mock_x"

    assert (
        payload["duplicate_prevented"]
        is False
    )

    assert (
        payload["external_url"]
        .startswith(
            "mock://mock_x/"
        )
    )

    mock_posts = client.get(
        "/mock-posts"
    )

    assert mock_posts.status_code == 200
    assert len(mock_posts.json()) == 1

    assert (
        mock_posts.json()[0]["variant_id"]
        == variant["id"]
    )


def test_mock_linkedin_publish_creates_local_post(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    _, slot = prepare_variant(
        client,
        "mock_linkedin",
    )

    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_linkedin",
    )

    response = client.post(
        f"/schedules/{slot['id']}/publish"
    )

    assert response.status_code == 200

    assert (
        response.json()["publisher"]
        == "mock_linkedin"
    )

    posts = client.get(
        "/mock-posts"
    )

    assert len(posts.json()) == 1

    assert (
        posts.json()[0]["platform"]
        == "mock_linkedin"
    )


def test_repeated_publish_returns_same_receipt_and_one_post(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    _, slot = prepare_variant(
        client,
        "mock_x",
    )

    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    first = client.post(
        f"/schedules/{slot['id']}/publish"
    )

    second = client.post(
        f"/schedules/{slot['id']}/publish"
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert (
        first.json()["idempotency_key"]
        == second.json()["idempotency_key"]
    )

    assert (
        first.json()["external_message_id"]
        == second.json()["external_message_id"]
    )

    assert (
        first.json()["duplicate_prevented"]
        is False
    )

    assert (
        second.json()["duplicate_prevented"]
        is True
    )

    posts = client.get(
        "/mock-posts"
    )

    assert len(posts.json()) == 1


def test_publish_marks_variant_and_slot_published(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    variant, slot = prepare_variant(
        client,
        "mock_x",
    )

    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    published = client.post(
        f"/schedules/{slot['id']}/publish"
    )

    assert published.status_code == 200

    variant_after = client.get(
        f"/variants/{variant['id']}"
    )

    slot_after = client.get(
        f"/schedules/{slot['id']}"
    )

    assert (
        variant_after.json()["status"]
        == "published"
    )

    assert (
        slot_after.json()["status"]
        == "published"
    )


def test_publish_history_records_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    _, slot = prepare_variant(
        client,
        "mock_x",
    )

    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    published = client.post(
        f"/schedules/{slot['id']}/publish"
    )

    assert published.status_code == 200

    history = client.get(
        "/publish-history"
    )

    assert history.status_code == 200
    assert len(history.json()) == 1

    record = history.json()[0]

    assert record["result"] == "success"
    assert record["publisher"] == "mock_x"


def test_adapter_swap_requires_configuration_only(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    _, slot = prepare_variant(
        client,
        "discord",
    )

    monkeypatch.setenv(
        "PUBLISHER_OVERRIDE",
        "mock_x",
    )

    response = client.post(
        f"/schedules/{slot['id']}/publish"
    )

    assert response.status_code == 200

    assert (
        response.json()["publisher"]
        == "mock_x"
    )

    assert len(
        client.get(
            "/mock-posts"
        ).json()
    ) == 1


class FakeDiscordResponse:
    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> dict:
        return {
            "id":
                "111111111111111111",

            "channel_id":
                "222222222222222222",

            "guild_id":
                "333333333333333333",
        }


class FakeDiscordClient:
    def __init__(
        self,
    ) -> None:
        self.calls: list[dict] = []

    def post(
        self,
        url: str,
        *,
        json: dict,
        timeout: float,
    ) -> FakeDiscordResponse:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )

        return FakeDiscordResponse()


def test_discord_adapter_calls_webhook_and_returns_live_url():
    fake = FakeDiscordClient()

    publisher = DiscordPublisher(
        webhook_url=(
            "https://discord.com/api/webhooks/"
            "123456789012345678/"
            "fake-token-for-test-only"
        ),
        http_client=fake,
    )

    result = publisher.publish(
        variant_id=1,
        content="Hello from the capstone.",
        idempotency_key="abc",
    )

    assert len(fake.calls) == 1

    assert (
        fake.calls[0]["json"]["content"]
        == "Hello from the capstone."
    )

    assert "wait=true" in (
        fake.calls[0]["url"]
    )

    assert (
        result.external_message_id
        == "111111111111111111"
    )

    assert result.external_url == (
        "https://discord.com/channels/"
        "333333333333333333/"
        "222222222222222222/"
        "111111111111111111"
    )


def test_discord_placeholder_is_rejected():
    with pytest.raises(
        ValueError
    ):
        DiscordPublisher(
            webhook_url=(
                "https://discord.com/api/"
                "webhooks/REPLACE_ME"
            )
        )


def test_discord_publish_is_idempotent_at_service_boundary(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "discord_service.db"
    )

    app = create_app(
        "sqlite:///"
        + str(database_path)
    )

    with TestClient(app) as client:
        variant, slot = prepare_variant(
            client,
            "discord",
        )

        fake = FakeDiscordClient()

        with (
            app.state.db
            .SessionLocal()
        ) as session:
            first = publish_slot(
                session,
                slot_id=slot["id"],
                publisher_override="discord",
                discord_webhook_url=(
                    "https://discord.com/api/webhooks/"
                    "123456789012345678/"
                    "fake-token-for-test-only"
                ),
                http_client=fake,
            )

        with (
            app.state.db
            .SessionLocal()
        ) as session:
            second = publish_slot(
                session,
                slot_id=slot["id"],
                publisher_override="discord",
                discord_webhook_url=(
                    "https://discord.com/api/webhooks/"
                    "123456789012345678/"
                    "fake-token-for-test-only"
                ),
                http_client=fake,
            )

        assert len(fake.calls) == 1

        assert (
            first.external_message_id
            == second.external_message_id
        )

        assert (
            first.duplicate_prevented
            is False
        )

        assert (
            second.duplicate_prevented
            is True
        )

        assert variant["status"] == "approved"


def test_receipt_and_mock_rows_are_unique(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "unique.db"
    )

    app = create_app(
        "sqlite:///"
        + str(database_path)
    )

    with TestClient(app) as client:
        _, slot = prepare_variant(
            client,
            "mock_x",
        )

        with (
            app.state.db
            .SessionLocal()
        ) as session:
            first = publish_slot(
                session,
                slot_id=slot["id"],
                publisher_override="mock_x",
            )

        with (
            app.state.db
            .SessionLocal()
        ) as session:
            second = publish_slot(
                session,
                slot_id=slot["id"],
                publisher_override="mock_x",
            )

        assert (
            first.idempotency_key
            == second.idempotency_key
        )

        with (
            app.state.db
            .SessionLocal()
        ) as session:
            receipts = session.scalars(
                select(
                    PublishReceipt
                )
            ).all()

            mock_posts = session.scalars(
                select(
                    MockPublishedPost
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
            ).all()

        assert len(receipts) == 1
        assert len(mock_posts) == 1
        assert len(successes) == 1


class FailingDiscordResponse:
    def raise_for_status(
        self,
    ) -> None:
        request = httpx.Request(
            "POST",
            (
                "https://discord.com/"
                "api/webhooks/test"
            ),
        )

        response = httpx.Response(
            500,
            request=request,
        )

        raise httpx.HTTPStatusError(
            "Discord failed",
            request=request,
            response=response,
        )

    def json(
        self,
    ) -> dict:
        return {}


class FailingDiscordClient:
    def post(
        self,
        url: str,
        *,
        json: dict,
        timeout: float,
    ) -> FailingDiscordResponse:
        return FailingDiscordResponse()


def test_failed_publish_is_recorded_and_slot_can_retry(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "failure.db"
    )

    app = create_app(
        "sqlite:///"
        + str(database_path)
    )

    with TestClient(app) as client:
        _, slot = prepare_variant(
            client,
            "discord",
        )

        with pytest.raises(
            httpx.HTTPStatusError
        ):
            with (
                app.state.db
                .SessionLocal()
            ) as session:
                publish_slot(
                    session,
                    slot_id=slot["id"],
                    publisher_override="discord",
                    discord_webhook_url=(
                        "https://discord.com/api/webhooks/"
                        "123456789012345678/"
                        "fake-token-for-test-only"
                    ),
                    http_client=(
                        FailingDiscordClient()
                    ),
                )

        slot_after = client.get(
            f"/schedules/{slot['id']}"
        )

        assert (
            slot_after.json()["status"]
            == "scheduled"
        )

        history = client.get(
            "/publish-history"
        )

        assert len(history.json()) == 1
        assert (
            history.json()[0]["result"]
            == "failed"
        )


class DiscordMessageWithoutGuildResponse:
    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> dict:
        return {
            "id":
                "444444444444444444",

            "channel_id":
                "555555555555555555",
        }


class DiscordWebhookMetadataResponse:
    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> dict:
        return {
            "id":
                "666666666666666666",

            "guild_id":
                "777777777777777777",

            "channel_id":
                "555555555555555555",
        }


class DiscordMetadataFallbackClient:
    def __init__(
        self,
    ) -> None:
        self.post_calls = 0
        self.get_calls = 0

    def post(
        self,
        url: str,
        *,
        json: dict,
        timeout: float,
    ) -> DiscordMessageWithoutGuildResponse:
        self.post_calls += 1

        return (
            DiscordMessageWithoutGuildResponse()
        )

    def get(
        self,
        url: str,
        *,
        timeout: float,
    ) -> DiscordWebhookMetadataResponse:
        self.get_calls += 1

        return (
            DiscordWebhookMetadataResponse()
        )


def test_discord_adapter_recovers_location_from_webhook_metadata():
    fake = (
        DiscordMetadataFallbackClient()
    )

    publisher = DiscordPublisher(
        webhook_url=(
            "https://discord.com/api/webhooks/"
            "123456789012345678/"
            "fake-token-for-test-only"
        ),
        http_client=fake,
    )

    result = publisher.publish(
        variant_id=1,
        content=(
            "Realistic Discord metadata "
            "fallback test."
        ),
        idempotency_key="metadata-test",
    )

    assert fake.post_calls == 1
    assert fake.get_calls == 1

    assert (
        result.external_message_id
        == "444444444444444444"
    )

    assert result.external_url == (
        "https://discord.com/channels/"
        "777777777777777777/"
        "555555555555555555/"
        "444444444444444444"
    )
