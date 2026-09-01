from __future__ import annotations

from typing import Protocol

import httpx

from app.publishers.base import (
    PublishResult,
    SocialPublisher,
)


class HttpResponseLike(Protocol):
    def raise_for_status(self) -> None:
        ...

    def json(self) -> dict:
        ...


class HttpClientLike(Protocol):
    def post(
        self,
        url: str,
        *,
        json: dict,
        timeout: float,
    ) -> HttpResponseLike:
        ...


class DiscordPublisher(
    SocialPublisher
):
    name = "discord"

    def __init__(
        self,
        *,
        webhook_url: str,
        http_client: HttpClientLike | None = None,
    ) -> None:
        cleaned = webhook_url.strip()

        if not cleaned:
            raise ValueError(
                "DISCORD_WEBHOOK_URL is required "
                "for real Discord publishing."
            )

        if "REPLACE_ME" in cleaned:
            raise ValueError(
                "DISCORD_WEBHOOK_URL still contains "
                "the placeholder value."
            )

        if not cleaned.startswith(
            "https://discord.com/api/webhooks/"
        ):
            raise ValueError(
                "DISCORD_WEBHOOK_URL must be a "
                "Discord webhook URL."
            )

        self.webhook_url = cleaned
        self.http_client = (
            http_client
            if http_client is not None
            else httpx
        )

    def publish(
        self,
        *,
        variant_id: int,
        content: str,
        idempotency_key: str,
    ) -> PublishResult:
        separator = (
            "&"
            if "?" in self.webhook_url
            else "?"
        )

        url = (
            self.webhook_url
            + separator
            + "wait=true"
        )

        response = self.http_client.post(
            url,
            json={
                "content": content,
            },
            timeout=15.0,
        )

        response.raise_for_status()

        payload = response.json()

        message_id = (
            str(payload["id"])
            if payload.get("id")
            is not None
            else None
        )

        channel_id = (
            str(payload["channel_id"])
            if payload.get("channel_id")
            is not None
            else None
        )

        guild_id = (
            str(payload["guild_id"])
            if payload.get("guild_id")
            is not None
            else None
        )

        # Discord webhook execution may return a Message
        # without every location field needed for a normal
        # Discord browser URL. In that case, read the webhook
        # metadata without exposing the webhook token.
        if (
            message_id
            and (
                channel_id is None
                or guild_id is None
            )
        ):
            get_method = getattr(
                self.http_client,
                "get",
                None,
            )

            if callable(get_method):
                metadata_response = get_method(
                    self.webhook_url,
                    timeout=15.0,
                )

                metadata_response.raise_for_status()

                metadata = (
                    metadata_response.json()
                )

                if channel_id is None:
                    value = metadata.get(
                        "channel_id"
                    )

                    if value is not None:
                        channel_id = str(
                            value
                        )

                if guild_id is None:
                    value = metadata.get(
                        "guild_id"
                    )

                    if value is not None:
                        guild_id = str(
                            value
                        )

        external_url = None

        if (
            message_id
            and channel_id
            and guild_id
        ):
            external_url = (
                "https://discord.com/channels/"
                f"{guild_id}/"
                f"{channel_id}/"
                f"{message_id}"
            )

        return PublishResult(
            publisher=self.name,
            external_message_id=message_id,
            external_url=external_url,
        )
