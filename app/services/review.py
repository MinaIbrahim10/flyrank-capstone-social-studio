from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Variant
from app.services.constraints import (
    ConstraintViolation,
    validate_variant,
)


class VariantNotFound(
    LookupError
):
    pass


class InvalidReviewTransition(
    ValueError
):
    pass


@dataclass(frozen=True)
class InvalidVariantEdit(
    ValueError,
):
    platform: str
    violations: list[ConstraintViolation]

    def __str__(self) -> str:
        return (
            "Edited content violates "
            "platform constraints."
        )


def get_variant_or_raise(
    session: Session,
    variant_id: int,
) -> Variant:
    variant = session.get(
        Variant,
        variant_id,
    )

    if variant is None:
        raise VariantNotFound(
            "Variant not found."
        )

    return variant


def edit_variant(
    session: Session,
    *,
    variant_id: int,
    content: str,
) -> Variant:
    variant = get_variant_or_raise(
        session,
        variant_id,
    )

    if variant.status == "published":
        raise InvalidReviewTransition(
            "A published variant cannot be edited."
        )

    violations = validate_variant(
        variant.platform,
        content,
    )

    if violations:
        raise InvalidVariantEdit(
            platform=variant.platform,
            violations=violations,
        )

    variant.content = content.strip()

    # Any human edit requires a fresh approval.
    variant.status = "draft"

    session.add(
        variant
    )

    session.commit()
    session.refresh(
        variant
    )

    return variant


def approve_variant(
    session: Session,
    variant_id: int,
) -> Variant:
    variant = get_variant_or_raise(
        session,
        variant_id,
    )

    if variant.status != "draft":
        raise InvalidReviewTransition(
            "Only a draft variant can be approved."
        )

    violations = validate_variant(
        variant.platform,
        variant.content,
    )

    if violations:
        raise InvalidVariantEdit(
            platform=variant.platform,
            violations=violations,
        )

    variant.status = "approved"

    session.add(
        variant
    )

    session.commit()
    session.refresh(
        variant
    )

    return variant


def reject_variant(
    session: Session,
    variant_id: int,
) -> Variant:
    variant = get_variant_or_raise(
        session,
        variant_id,
    )

    if variant.status != "draft":
        raise InvalidReviewTransition(
            "Only a draft variant can be rejected."
        )

    variant.status = "rejected"

    session.add(
        variant
    )

    session.commit()
    session.refresh(
        variant
    )

    return variant
