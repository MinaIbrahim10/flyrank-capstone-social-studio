from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.publishers.base import (
    SocialPublisher,
)
from app.publishers.discord import (
    DiscordPublisher,
    HttpClientLike,
)
from app.publishers.mock import (
    MockLinkedInPublisher,
    MockXPublisher,
)


SUPPORTED_PUBLISHERS = {
    "discord",
    "mock_x",
    "mock_linkedin",
}


def configured_publisher_name(
    default_name: str,
    *,
    override: str | None = None,
) -> str:
    selected = (
        override
        if override is not None
        else os.getenv(
            "PUBLISHER_OVERRIDE",
            "",
        )
    )

    selected = selected.strip()

    if not selected:
        selected = default_name

    if selected not in SUPPORTED_PUBLISHERS:
        raise ValueError(
            "Unsupported publisher: "
            f"{selected}"
        )

    return selected


def create_publisher(
    *,
    name: str,
    session: Session,
    discord_webhook_url: str | None = None,
    http_client: HttpClientLike | None = None,
) -> SocialPublisher:
    if name == "mock_x":
        return MockXPublisher(
            session=session,
        )

    if name == "mock_linkedin":
        return MockLinkedInPublisher(
            session=session,
        )

    if name == "discord":
        webhook = (
            discord_webhook_url
            if discord_webhook_url is not None
            else os.getenv(
                "DISCORD_WEBHOOK_URL",
                "",
            )
        )

        return DiscordPublisher(
            webhook_url=webhook,
            http_client=http_client,
        )

    raise ValueError(
        f"Unsupported publisher: {name}"
    )
