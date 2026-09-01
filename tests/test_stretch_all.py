from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Database
from app.main import create_app
from app.models import (
    AIGeneratedVariant,
    AIUsageRecord,
    Post,
)
from app.services.ollama import (
    generate_with_ollama,
)


def create_source(
    client: TestClient,
    *,
    title: str = "Stretch Source",
) -> dict:
    response = client.post(
        "/posts",
        json={
            "title":
                title,

            "markdown":
                (
                    "The launch includes 3 verified "
                    "features for durable social "
                    "publishing. Human approval, "
                    "persistent scheduling, and retry "
                    "protection are included."
                ),
        },
    )

    assert (
        response.status_code
        == 201
    )

    return response.json()


def test_ab_variants_are_distinct_and_valid(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "ab.db"
        )
    )

    with TestClient(app) as client:
        post = create_source(
            client
        )

        response = client.post(
            (
                f"/posts/{post['id']}"
                "/ab-experiments/mock_x"
            )
        )

        assert (
            response.status_code
            == 201
        )

        payload = response.json()

        assert (
            len(
                payload[
                    "options"
                ]
            )
            == 2
        )

        a, b = payload[
            "options"
        ]

        assert (
            a[
                "content"
            ]
            != b[
                "content"
            ]
        )

        for option in (
            a,
            b,
        ):
            validation = client.post(
                "/variants/validate",
                json={
                    "platform":
                        "mock_x",

                    "content":
                        option[
                            "content"
                        ],
                },
            )

            assert (
                validation.status_code
                == 200
            )


def test_ab_creation_is_idempotent(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "ab_idempotent.db"
        )
    )

    with TestClient(app) as client:
        post = create_source(
            client
        )

        first = client.post(
            (
                f"/posts/{post['id']}"
                "/ab-experiments/discord"
            )
        )

        second = client.post(
            (
                f"/posts/{post['id']}"
                "/ab-experiments/discord"
            )
        )

        assert (
            first.json()[
                "id"
            ]
            == second.json()[
                "id"
            ]
        )

        assert (
            len(
                second.json()[
                    "options"
                ]
            )
            == 2
        )


def test_ab_winner_and_promotion(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "winner.db"
        )
    )

    with TestClient(app) as client:
        post = create_source(
            client
        )

        # Core variant exists first.
        generated = client.post(
            f"/posts/{post['id']}/variants"
        )

        assert (
            generated.status_code
            == 201
        )

        experiment = client.post(
            (
                f"/posts/{post['id']}"
                "/ab-experiments/mock_x"
            )
        ).json()

        selected = client.post(
            (
                f"/ab-experiments/"
                f"{experiment['id']}/winner"
            ),
            json={
                "label":
                    "B",
            },
        )

        assert (
            selected.status_code
            == 200
        )

        payload = selected.json()

        assert (
            payload[
                "winner_label"
            ]
            == "B"
        )

        winner = next(
            item
            for item
            in payload[
                "options"
            ]
            if item[
                "label"
            ]
            == "B"
        )

        promoted = client.post(
            (
                f"/ab-experiments/"
                f"{experiment['id']}/promote"
            )
        )

        assert (
            promoted.status_code
            == 200
        )

        assert (
            promoted.json()[
                "content"
            ]
            == winner[
                "content"
            ]
        )

        assert (
            promoted.json()[
                "status"
            ]
            == "draft"
        )


def test_ab_promote_without_winner_blocked(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "winner_required.db"
        )
    )

    with TestClient(app) as client:
        post = create_source(
            client
        )

        experiment = client.post(
            (
                f"/posts/{post['id']}"
                "/ab-experiments/mock_x"
            )
        ).json()

        response = client.post(
            (
                f"/ab-experiments/"
                f"{experiment['id']}/promote"
            )
        )

        assert (
            response.status_code
            == 409
        )


def test_grounding_accepts_supported_claims(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "grounded.db"
        )
    )

    with TestClient(app) as client:
        post = create_source(
            client
        )

        response = client.post(
            (
                f"/posts/{post['id']}"
                "/grounding-check"
            ),
            json={
                "content":
                    (
                        "The launch includes 3 verified "
                        "features for durable social "
                        "publishing."
                    ),
            },
        )

        assert (
            response.status_code
            == 200
        )

        assert (
            response.json()[
                "grounded"
            ]
            is True
        )

        assert (
            response.json()[
                "unsupported_numbers"
            ]
            == []
        )


def test_grounding_blocks_fabricated_number(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "hallucination.db"
        )
    )

    with TestClient(app) as client:
        post = create_source(
            client
        )

        response = client.post(
            (
                f"/posts/{post['id']}"
                "/grounding-check"
            ),
            json={
                "content":
                    (
                        "The launch includes 99 "
                        "verified features for durable "
                        "social publishing."
                    ),
            },
        )

        assert (
            response.status_code
            == 200
        )

        assert (
            response.json()[
                "grounded"
            ]
            is False
        )

        assert (
            "99"
            in response.json()[
                "unsupported_numbers"
            ]
        )


class FakeOllamaResponse:
    def __init__(
        self,
        content: str,
    ) -> None:
        self.content = content

    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> dict:
        return {
            "response":
                self.content,

            "prompt_eval_count":
                42,

            "eval_count":
                14,
        }


class FakeOllamaClient:
    def __init__(
        self,
        content: str,
    ) -> None:
        self.content = content
        self.calls = 0

    def post(
        self,
        url: str,
        *,
        json: dict,
        timeout: float,
    ) -> FakeOllamaResponse:
        self.calls += 1

        assert (
            url.endswith(
                "/api/generate"
            )
        )

        assert (
            json[
                "stream"
            ]
            is False
        )

        return FakeOllamaResponse(
            self.content
        )


def test_ollama_generation_records_zero_cost(
    tmp_path: Path,
):
    database_url = (
        "sqlite:///"
        + str(
            tmp_path
            / "ollama.db"
        )
    )

    database = Database(
        database_url
    )

    database.create_all()

    try:
        with database.SessionLocal() as session:
            post = Post(
                title="Local Ollama",
                source_type="markdown",
                source_url=None,
                markdown=(
                    "The launch includes 3 verified "
                    "features for durable social "
                    "publishing."
                ),
            )

            session.add(
                post
            )

            session.commit()

            session.refresh(
                post
            )

            fake = FakeOllamaClient(
                (
                    "The launch includes 3 verified "
                    "features for durable social "
                    "publishing. #blog"
                )
            )

            generated = (
                generate_with_ollama(
                    session,
                    post=post,
                    platform="discord",
                    model="fake-local-model",
                    base_url=(
                        "http://127.0.0.1:11434"
                    ),
                    client=fake,
                )
            )

            assert (
                fake.calls
                == 1
            )

            assert (
                generated.grounded
                is True
            )

            usage = session.scalar(
                select(
                    AIUsageRecord
                )
            )

            assert (
                usage is not None
            )

            assert (
                usage.provider
                == "ollama"
            )

            assert (
                usage.cost_usd
                == 0.0
            )

            assert (
                usage.prompt_tokens
                == 42
            )

            assert (
                usage.completion_tokens
                == 14
            )

    finally:
        database.dispose()


def test_ollama_bad_claim_uses_guarded_fallback(
    tmp_path: Path,
):
    database_url = (
        "sqlite:///"
        + str(
            tmp_path
            / "ollama_guard.db"
        )
    )

    database = Database(
        database_url
    )

    database.create_all()

    try:
        with database.SessionLocal() as session:
            post = Post(
                title="Guarded AI",
                source_type="markdown",
                source_url=None,
                markdown=(
                    "The campaign includes 3 "
                    "verified features."
                ),
            )

            session.add(
                post
            )

            session.commit()

            session.refresh(
                post
            )

            fake = FakeOllamaClient(
                (
                    "The campaign includes 999 "
                    "verified features. #blog"
                )
            )

            generated = (
                generate_with_ollama(
                    session,
                    post=post,
                    platform="discord",
                    model="fake-local-model",
                    base_url=(
                        "http://127.0.0.1:11434"
                    ),
                    client=fake,
                )
            )

            assert (
                generated.used_fallback
                is True
            )

            assert (
                "999"
                not in generated.content
            )

            assert (
                "3"
                in generated.content
            )

    finally:
        database.dispose()


def test_ai_usage_endpoint(
    tmp_path: Path,
):
    database_url = (
        "sqlite:///"
        + str(
            tmp_path
            / "usage_api.db"
        )
    )

    database = Database(
        database_url
    )

    database.create_all()

    try:
        with database.SessionLocal() as session:
            usage = AIUsageRecord(
                post_id=None,
                provider="ollama",
                model="local-model",
                prompt_tokens=10,
                completion_tokens=5,
                input_chars=100,
                output_chars=50,
                cost_usd=0.0,
                success=True,
                error=None,
            )

            session.add(
                usage
            )

            session.commit()

    finally:
        database.dispose()

    app = create_app(
        database_url
    )

    with TestClient(app) as client:
        response = client.get(
            "/ai-usage"
        )

        assert (
            response.status_code
            == 200
        )

        assert (
            len(
                response.json()
            )
            == 1
        )

        assert (
            response.json()[0][
                "cost_usd"
            ]
            == 0.0
        )


def test_tenant_campaign_isolation(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "tenant.db"
        )
    )

    with TestClient(app) as client:
        alpha = client.post(
            "/tenants",
            json={
                "name":
                    "Agency Alpha",

                "slug":
                    "agency-alpha",
            },
        ).json()

        beta = client.post(
            "/tenants",
            json={
                "name":
                    "Agency Beta",

                "slug":
                    "agency-beta",
            },
        ).json()

        campaign = client.post(
            (
                f"/tenants/{alpha['id']}"
                "/campaigns"
            ),
            json={
                "title":
                    "Alpha Private Campaign",

                "markdown":
                    (
                        "Private Alpha campaign "
                        "content."
                    ),
            },
        )

        assert (
            campaign.status_code
            == 201
        )

        campaign_id = (
            campaign.json()[
                "id"
            ]
        )

        correct = client.get(
            (
                f"/tenants/{alpha['id']}"
                f"/campaigns/{campaign_id}"
            )
        )

        assert (
            correct.status_code
            == 200
        )

        cross_tenant = client.get(
            (
                f"/tenants/{beta['id']}"
                f"/campaigns/{campaign_id}"
            )
        )

        assert (
            cross_tenant.status_code
            == 404
        )


def test_tenant_generates_isolated_three_variants(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "tenant_variants.db"
        )
    )

    with TestClient(app) as client:
        tenant = client.post(
            "/tenants",
            json={
                "name":
                    "Client One",

                "slug":
                    "client-one",
            },
        ).json()

        campaign = client.post(
            (
                f"/tenants/{tenant['id']}"
                "/campaigns"
            ),
            json={
                "title":
                    "Client Launch",

                "markdown":
                    (
                        "The client launch uses "
                        "durable publishing and "
                        "human approval."
                    ),
            },
        ).json()

        response = client.post(
            (
                f"/tenants/{tenant['id']}"
                f"/campaigns/{campaign['id']}"
                "/variants"
            )
        )

        assert (
            response.status_code
            == 201
        )

        assert {
            item[
                "platform"
            ]
            for item
            in response.json()
        } == {
            "discord",
            "mock_x",
            "mock_linkedin",
        }


def test_duplicate_tenant_slug_is_blocked(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "tenant_duplicate.db"
        )
    )

    with TestClient(app) as client:
        first = client.post(
            "/tenants",
            json={
                "name":
                    "First",

                "slug":
                    "same-client",
            },
        )

        second = client.post(
            "/tenants",
            json={
                "name":
                    "Second",

                "slug":
                    "same-client",
            },
        )

        assert (
            first.status_code
            == 201
        )

        assert (
            second.status_code
            == 409
        )


def test_unknown_tenant_cannot_create_campaign(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "unknown_tenant.db"
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/tenants/999/campaigns",
            json={
                "title":
                    "No tenant",

                "markdown":
                    "Should not be stored.",
            },
        )

        assert (
            response.status_code
            == 404
        )


def test_invalid_ab_winner_label_is_422(
    tmp_path: Path,
):
    app = create_app(
        "sqlite:///"
        + str(
            tmp_path
            / "winner_schema.db"
        )
    )

    with TestClient(app) as client:
        post = create_source(
            client
        )

        experiment = client.post(
            (
                f"/posts/{post['id']}"
                "/ab-experiments/mock_x"
            )
        ).json()

        response = client.post(
            (
                f"/ab-experiments/"
                f"{experiment['id']}/winner"
            ),
            json={
                "label":
                    "C",
            },
        )

        assert (
            response.status_code
            == 422
        )
