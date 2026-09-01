from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)
from dataclasses import dataclass


@dataclass(frozen=True)
class PublishResult:
    publisher: str
    external_message_id: str | None
    external_url: str | None


class SocialPublisher(ABC):
    name: str

    @abstractmethod
    def publish(
        self,
        *,
        variant_id: int,
        content: str,
        idempotency_key: str,
    ) -> PublishResult:
        """Publish one already-approved social variant."""
        raise NotImplementedError
