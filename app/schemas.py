from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)


PlatformName = Literal[
    "discord",
    "mock_x",
    "mock_linkedin",
]

VariantStatus = Literal[
    "draft",
    "approved",
    "rejected",
    "published",
]


class PostCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=300,
    )

    markdown: str | None = Field(
        default=None,
        min_length=1,
    )

    url: HttpUrl | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "PostCreate":
        sources = [
            self.markdown is not None,
            self.url is not None,
        ]

        if sum(sources) != 1:
            raise ValueError(
                "Provide exactly one source: markdown or url."
            )

        return self


class PostRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    title: str
    source_type: str
    source_url: str | None
    markdown: str
    created_at: datetime


class VariantRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    post_id: int
    platform: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime


class VariantUpdate(BaseModel):
    content: str = Field(
        min_length=1,
    )


class VariantValidateRequest(BaseModel):
    platform: PlatformName

    content: str = Field(
        min_length=1,
    )


class ConstraintViolationRead(BaseModel):
    rule: str
    message: str


class VariantValidationResult(BaseModel):
    valid: bool
    platform: str
    violations: list[ConstraintViolationRead]


class ScheduleCreate(BaseModel):
    scheduled_at: datetime

    @model_validator(mode="after")
    def timezone_required(
        self,
    ) -> "ScheduleCreate":
        value = self.scheduled_at

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "scheduled_at must include a timezone."
            )

        return self


class ScheduleRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    variant_id: int
    publisher: str
    scheduled_at: datetime
    status: str
    created_at: datetime


class PublishOutcomeRead(BaseModel):
    slot_id: int
    variant_id: int
    publisher: str
    idempotency_key: str
    external_message_id: str | None
    external_url: str | None
    duplicate_prevented: bool


class PublishAttemptRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    slot_id: int
    publisher: str
    idempotency_key: str
    result: str
    external_message_id: str | None
    external_url: str | None
    error: str | None
    attempted_at: datetime


class MockPublishedPostRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    platform: str
    variant_id: int
    content: str
    idempotency_key: str
    created_at: datetime


# ============================================================
# Stretch Goal Schemas
# ============================================================


class ABWinnerSelect(BaseModel):
    label: Literal[
        "A",
        "B",
    ]


class GroundingCheckRequest(BaseModel):
    content: str = Field(
        min_length=1,
    )


class GroundingCheckRead(BaseModel):
    grounded: bool
    coverage: float
    unsupported_numbers: list[str]
    supported_tokens: int
    candidate_tokens: int


class OllamaGenerateRequest(BaseModel):
    model: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )


class AIGeneratedVariantRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    post_id: int
    platform: str
    provider: str
    model: str
    content: str
    grounded: bool
    used_fallback: bool
    created_at: datetime


class AIUsageRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    post_id: int | None
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    input_chars: int
    output_chars: int
    cost_usd: float
    success: bool
    error: str | None
    created_at: datetime


class TenantCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
    )

    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )


class TenantRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    name: str
    slug: str
    created_at: datetime


class TenantCampaignCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=300,
    )

    markdown: str = Field(
        min_length=1,
    )


class TenantCampaignRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    tenant_id: int
    title: str
    markdown: str
    created_at: datetime


class TenantVariantRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    campaign_id: int
    platform: str
    content: str
    status: str
    created_at: datetime
