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
