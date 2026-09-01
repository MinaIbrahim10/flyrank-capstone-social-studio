from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "phase3.db"
    )

    app = create_app(
        "sqlite:///"
        + str(database_path)
    )

    with TestClient(
        app
    ) as test_client:
        yield test_client


def future_time(
    minutes: int = 10,
) -> str:
    return (
        datetime.now(timezone.utc)
        + timedelta(minutes=minutes)
    ).isoformat()


def create_variants(
    client: TestClient,
) -> list[dict]:
    post = client.post(
        "/posts",
        json={
            "title":
                "Safe Social Publishing",

            "markdown":
                "Human approval prevents "
                "unreviewed content from being "
                "published. Reliable schedulers "
                "must also prevent duplicates.",
        },
    )

    assert post.status_code == 201

    response = client.post(
        f"/posts/{post.json()['id']}/variants"
    )

    assert response.status_code == 201

    return response.json()


def platform_variant(
    variants: list[dict],
    platform: str,
) -> dict:
    return next(
        variant
        for variant in variants
        if variant["platform"] == platform
    )


def test_generated_variant_starts_as_draft(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    assert all(
        item["status"] == "draft"
        for item in variants
    )


def test_valid_edit_changes_content_and_stays_draft(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "mock_x",
    )

    response = client.put(
        f"/variants/{target['id']}",
        json={
            "content":
                "Human review protects "
                "scheduled publishing. #backend"
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["content"]
        == "Human review protects "
           "scheduled publishing. #backend"
    )

    assert payload["status"] == "draft"


def test_invalid_edit_is_blocked_and_names_rule(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "mock_x",
    )

    original_content = target[
        "content"
    ]

    response = client.put(
        f"/variants/{target['id']}",
        json={
            "content": "x" * 281,
        },
    )

    assert response.status_code == 422

    detail = response.json()[
        "detail"
    ]

    rules = {
        item["rule"]
        for item
        in detail["violations"]
    }

    assert "max_length" in rules

    persisted = client.get(
        f"/variants/{target['id']}"
    )

    assert persisted.status_code == 200

    assert (
        persisted.json()["content"]
        == original_content
    )

    assert (
        persisted.json()["status"]
        == "draft"
    )


def test_approve_draft_variant(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "discord",
    )

    response = client.post(
        f"/variants/{target['id']}/approve"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_reject_draft_variant(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "mock_linkedin",
    )

    response = client.post(
        f"/variants/{target['id']}/reject"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_rejected_variant_cannot_be_approved_without_edit(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "mock_linkedin",
    )

    rejected = client.post(
        f"/variants/{target['id']}/reject"
    )

    assert rejected.status_code == 200

    approved = client.post(
        f"/variants/{target['id']}/approve"
    )

    assert approved.status_code == 409


def test_editing_rejected_variant_returns_it_to_draft(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "mock_linkedin",
    )

    rejected = client.post(
        f"/variants/{target['id']}/reject"
    )

    assert rejected.status_code == 200

    edited = client.put(
        f"/variants/{target['id']}",
        json={
            "content":
                "Professional insight: "
                "human approval improves "
                "publishing safety. #Backend"
        },
    )

    assert edited.status_code == 200

    assert edited.json()["status"] == "draft"


def test_draft_variant_cannot_be_scheduled(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "discord",
    )

    response = client.post(
        f"/variants/{target['id']}/schedule",
        json={
            "scheduled_at":
                future_time(),
        },
    )

    assert response.status_code == 409

    assert (
        "approved"
        in response.json()["detail"].lower()
    )


def test_rejected_variant_cannot_be_scheduled(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "mock_x",
    )

    rejected = client.post(
        f"/variants/{target['id']}/reject"
    )

    assert rejected.status_code == 200

    scheduled = client.post(
        f"/variants/{target['id']}/schedule",
        json={
            "scheduled_at":
                future_time(),
        },
    )

    assert scheduled.status_code == 409


def test_approved_variant_can_be_scheduled(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "discord",
    )

    approved = client.post(
        f"/variants/{target['id']}/approve"
    )

    assert approved.status_code == 200

    scheduled = client.post(
        f"/variants/{target['id']}/schedule",
        json={
            "scheduled_at":
                future_time(),
        },
    )

    assert scheduled.status_code == 201

    payload = scheduled.json()

    assert payload["variant_id"] == target["id"]
    assert payload["publisher"] == "discord"
    assert payload["status"] == "scheduled"


def test_schedule_time_must_be_future(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "discord",
    )

    approved = client.post(
        f"/variants/{target['id']}/approve"
    )

    assert approved.status_code == 200

    past = (
        datetime.now(timezone.utc)
        - timedelta(minutes=5)
    ).isoformat()

    response = client.post(
        f"/variants/{target['id']}/schedule",
        json={
            "scheduled_at": past,
        },
    )

    assert response.status_code == 422


def test_schedule_requires_timezone(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "discord",
    )

    approved = client.post(
        f"/variants/{target['id']}/approve"
    )

    assert approved.status_code == 200

    naive = (
        datetime.now()
        + timedelta(minutes=10)
    ).replace(
        microsecond=0
    ).isoformat()

    response = client.post(
        f"/variants/{target['id']}/schedule",
        json={
            "scheduled_at": naive,
        },
    )

    assert response.status_code == 422


def test_duplicate_schedule_request_returns_same_slot(
    client: TestClient,
):
    variants = create_variants(
        client
    )

    target = platform_variant(
        variants,
        "discord",
    )

    approved = client.post(
        f"/variants/{target['id']}/approve"
    )

    assert approved.status_code == 200

    scheduled_at = future_time(
        20
    )

    first = client.post(
        f"/variants/{target['id']}/schedule",
        json={
            "scheduled_at":
                scheduled_at,
        },
    )

    second = client.post(
        f"/variants/{target['id']}/schedule",
        json={
            "scheduled_at":
                scheduled_at,
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201

    assert (
        first.json()["id"]
        == second.json()["id"]
    )

    schedules = client.get(
        "/schedules"
    )

    assert schedules.status_code == 200
    assert len(schedules.json()) == 1


def test_schedule_persists_across_application_restart(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "persistent_schedule.db"
    )

    database_url = (
        "sqlite:///"
        + str(database_path)
    )

    first_app = create_app(
        database_url
    )

    with TestClient(
        first_app
    ) as first:
        variants = create_variants(
            first
        )

        target = platform_variant(
            variants,
            "discord",
        )

        approved = first.post(
            f"/variants/{target['id']}/approve"
        )

        assert approved.status_code == 200

        scheduled = first.post(
            f"/variants/{target['id']}/schedule",
            json={
                "scheduled_at":
                    future_time(30),
            },
        )

        assert scheduled.status_code == 201

        slot_id = scheduled.json()[
            "id"
        ]

    second_app = create_app(
        database_url
    )

    with TestClient(
        second_app
    ) as second:
        fetched = second.get(
            f"/schedules/{slot_id}"
        )

        assert fetched.status_code == 200

        assert (
            fetched.json()["status"]
            == "scheduled"
        )


def test_missing_variant_review_returns_404(
    client: TestClient,
):
    approve = client.post(
        "/variants/999999/approve"
    )

    reject = client.post(
        "/variants/999999/reject"
    )

    edit = client.put(
        "/variants/999999",
        json={
            "content":
                "Valid content."
        },
    )

    assert approve.status_code == 404
    assert reject.status_code == 404
    assert edit.status_code == 404
