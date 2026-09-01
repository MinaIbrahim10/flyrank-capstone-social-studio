from __future__ import annotations

import httpx

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Post,
    Variant,
)
from app.schemas import (
    PostCreate,
    PostRead,
    VariantRead,
    VariantValidateRequest,
    VariantValidationResult,
)
from app.services.constraints import (
    validate_variant,
)
from app.services.generator import (
    GeneratedVariantInvalid,
    generate_variants,
)
from app.services.ingestion import (
    create_post,
)


router = APIRouter()


def get_session(
    request: Request,
):
    session = (
        request.app.state.db
        .SessionLocal()
    )

    try:
        yield session
    finally:
        session.close()


@router.get(
    "/health",
)
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service":
            "social-media-studio",
    }


@router.post(
    "/posts",
    response_model=PostRead,
    status_code=status.HTTP_201_CREATED,
)
def ingest_post(
    payload: PostCreate,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return create_post(
            session,
            payload,
        )

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not fetch the supplied URL: "
                f"{exc}"
            ),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/posts",
    response_model=list[PostRead],
)
def list_posts(
    session: Session = Depends(
        get_session
    ),
):
    return session.scalars(
        select(Post)
        .order_by(Post.id)
    ).all()


@router.get(
    "/posts/{post_id}",
    response_model=PostRead,
)
def get_post(
    post_id: int,
    session: Session = Depends(
        get_session
    ),
):
    post = session.get(
        Post,
        post_id,
    )

    if post is None:
        raise HTTPException(
            status_code=404,
            detail="Post not found.",
        )

    return post


@router.post(
    "/posts/{post_id}/variants",
    response_model=list[VariantRead],
    status_code=status.HTTP_201_CREATED,
)
def create_variants(
    post_id: int,
    session: Session = Depends(
        get_session
    ),
):
    post = session.get(
        Post,
        post_id,
    )

    if post is None:
        raise HTTPException(
            status_code=404,
            detail="Post not found.",
        )

    try:
        return generate_variants(
            session,
            post,
        )

    except GeneratedVariantInvalid as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    "Generated variant violated "
                    "its platform constraints."
                ),
                "platform":
                    exc.platform,
                "violations": [
                    {
                        "rule":
                            violation.rule,
                        "message":
                            violation.message,
                    }
                    for violation
                    in exc.violations
                ],
            },
        ) from exc


@router.get(
    "/posts/{post_id}/variants",
    response_model=list[VariantRead],
)
def list_post_variants(
    post_id: int,
    session: Session = Depends(
        get_session
    ),
):
    if (
        session.get(
            Post,
            post_id,
        )
        is None
    ):
        raise HTTPException(
            status_code=404,
            detail="Post not found.",
        )

    return session.scalars(
        select(Variant)
        .where(
            Variant.post_id
            == post_id
        )
        .order_by(
            Variant.id
        )
    ).all()


@router.get(
    "/variants/{variant_id}",
    response_model=VariantRead,
)
def get_variant(
    variant_id: int,
    session: Session = Depends(
        get_session
    ),
):
    variant = session.get(
        Variant,
        variant_id,
    )

    if variant is None:
        raise HTTPException(
            status_code=404,
            detail="Variant not found.",
        )

    return variant


@router.post(
    "/variants/validate",
    response_model=VariantValidationResult,
)
def validate_variant_endpoint(
    payload: VariantValidateRequest,
):
    violations = validate_variant(
        payload.platform,
        payload.content,
    )

    if violations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    "Variant violates platform "
                    "constraints."
                ),
                "platform":
                    payload.platform,
                "violations": [
                    {
                        "rule":
                            violation.rule,
                        "message":
                            violation.message,
                    }
                    for violation
                    in violations
                ],
            },
        )

    return VariantValidationResult(
        valid=True,
        platform=payload.platform,
        violations=[],
    )
