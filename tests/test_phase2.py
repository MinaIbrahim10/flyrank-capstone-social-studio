from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.constraints import (
    validate_variant,
)


@pytest.fixture
def client(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "phase2.db"
    )

    app = create_app(
        "sqlite:///"
        + str(database_path)
    )

    with TestClient(
        app
    ) as test_client:
        yield test_client


def test_health(
    client: TestClient,
):
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "service":
            "social-media-studio",
    }


def test_markdown_ingestion_persists_source(
    client: TestClient,
):
    response = client.post(
        "/posts",
        json={
            "title":
                "Reliable AI Systems",
            "markdown":
                "# Reliable AI\n\n"
                "Retries must not duplicate "
                "important actions.",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert (
        payload["source_type"]
        == "markdown"
    )

    assert (
        "Retries must not duplicate"
        in payload["markdown"]
    )

    fetched = client.get(
        f"/posts/{payload['id']}"
    )

    assert fetched.status_code == 200

    assert (
        fetched.json()["markdown"]
        == payload["markdown"]
    )


def test_exactly_one_input_source_required(
    client: TestClient,
):
    missing = client.post(
        "/posts",
        json={
            "title": "Missing",
        },
    )

    assert missing.status_code == 422

    both = client.post(
        "/posts",
        json={
            "title": "Both",
            "markdown":
                "Local content",
            "url":
                "https://example.com/article",
        },
    )

    assert both.status_code == 422


def test_url_ingestion_fetches_and_stores_content(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_get(
        url: str,
        **kwargs,
    ):
        request = httpx.Request(
            "GET",
            url,
        )

        return httpx.Response(
            200,
            request=request,
            headers={
                "content-type":
                    "text/html",
            },
            text=(
                "<html>"
                "<head>"
                "<style>hidden</style>"
                "</head>"
                "<body>"
                "<h1>Stored article</h1>"
                "<p>Important source text.</p>"
                "<script>ignored()</script>"
                "</body>"
                "</html>"
            ),
        )

    monkeypatch.setattr(
        "app.services.ingestion.httpx.get",
        fake_get,
    )

    response = client.post(
        "/posts",
        json={
            "title":
                "Fetched Article",
            "url":
                "https://example.com/article",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert (
        payload["source_type"]
        == "url"
    )

    assert (
        "Stored article"
        in payload["markdown"]
    )

    assert (
        "Important source text"
        in payload["markdown"]
    )

    assert (
        "ignored()"
        not in payload["markdown"]
    )


def test_generation_creates_three_valid_draft_variants(
    client: TestClient,
):
    created = client.post(
        "/posts",
        json={
            "title":
                "Idempotent Publishing",
            "markdown":
                "Reliable systems keep publishing "
                "safe during retries and worker "
                "restarts.",
        },
    )

    assert created.status_code == 201

    post_id = created.json()["id"]

    response = client.post(
        f"/posts/{post_id}/variants"
    )

    assert response.status_code == 201

    variants = response.json()

    assert len(variants) == 3

    assert {
        variant["platform"]
        for variant in variants
    } == {
        "discord",
        "mock_x",
        "mock_linkedin",
    }

    assert all(
        variant["status"] == "draft"
        for variant in variants
    )

    assert all(
        "Idempotent Publishing"
        in variant["content"]
        for variant in variants
    )


def test_generated_variants_satisfy_profiles(
    client: TestClient,
):
    created = client.post(
        "/posts",
        json={
            "title":
                "Backend Reliability",
            "markdown":
                "One. Two. Three. Four. "
                "A longer article can contain "
                "many sentences while the X "
                "variant remains concise.",
        },
    )

    post_id = created.json()["id"]

    response = client.post(
        f"/posts/{post_id}/variants"
    )

    assert response.status_code == 201

    for variant in response.json():
        violations = validate_variant(
            variant["platform"],
            variant["content"],
        )

        assert violations == []


def test_generation_does_not_duplicate_rows(
    client: TestClient,
):
    created = client.post(
        "/posts",
        json={
            "title":
                "One Source",
            "markdown":
                "One stored article should produce "
                "only one variant per platform.",
        },
    )

    post_id = created.json()["id"]

    first = client.post(
        f"/posts/{post_id}/variants"
    )

    second = client.post(
        f"/posts/{post_id}/variants"
    )

    assert first.status_code == 201
    assert second.status_code == 201

    first_ids = sorted(
        item["id"]
        for item in first.json()
    )

    second_ids = sorted(
        item["id"]
        for item in second.json()
    )

    assert first_ids == second_ids

    listed = client.get(
        f"/posts/{post_id}/variants"
    )

    assert listed.status_code == 200
    assert len(listed.json()) == 3


def test_max_length_rule_is_named():
    violations = validate_variant(
        "mock_x",
        "x" * 281,
    )

    rules = {
        violation.rule
        for violation in violations
    }

    assert "max_length" in rules


def test_hashtag_rule_is_named():
    violations = validate_variant(
        "mock_x",
        "Update #one #two #three",
    )

    rules = {
        violation.rule
        for violation in violations
    }

    assert "hashtag_count" in rules


def test_tone_rule_is_named():
    violations = validate_variant(
        "mock_x",
        (
            "First sentence. "
            "Second sentence. "
            "Third sentence."
        ),
    )

    rules = {
        violation.rule
        for violation in violations
    }

    assert "tone" in rules


def test_linkedin_tone_rule_blocks_slang():
    violations = validate_variant(
        "mock_linkedin",
        "OMG this backend is amazing.",
    )

    rules = {
        violation.rule
        for violation in violations
    }

    assert "tone" in rules


def test_invalid_variant_endpoint_returns_named_rule(
    client: TestClient,
):
    response = client.post(
        "/variants/validate",
        json={
            "platform": "mock_x",
            "content": "x" * 281,
        },
    )

    assert response.status_code == 422

    rules = {
        violation["rule"]
        for violation
        in response.json()[
            "detail"
        ][
            "violations"
        ]
    }

    assert "max_length" in rules


def test_valid_variant_endpoint_passes(
    client: TestClient,
):
    response = client.post(
        "/variants/validate",
        json={
            "platform":
                "mock_x",
            "content":
                "Reliable retries prevent "
                "duplicate posts. #backend",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "valid": True,
        "platform": "mock_x",
        "violations": [],
    }


def test_database_survives_application_restart(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "persistent.db"
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
    ) as first_client:
        created = first_client.post(
            "/posts",
            json={
                "title":
                    "Persistent Post",
                "markdown":
                    "This record must survive "
                    "an application restart.",
            },
        )

        assert (
            created.status_code
            == 201
        )

    second_app = create_app(
        database_url
    )

    with TestClient(
        second_app
    ) as second_client:
        posts = second_client.get(
            "/posts"
        )

        assert posts.status_code == 200

        assert len(
            posts.json()
        ) == 1

        assert (
            posts.json()[0]["title"]
            == "Persistent Post"
        )
