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
    ScheduleSlot,
    Variant,
)
from app.schemas import (
    PostCreate,
    PostRead,
    ScheduleCreate,
    ScheduleRead,
    VariantRead,
    VariantUpdate,
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
from app.services.review import (
    InvalidReviewTransition,
    InvalidVariantEdit,
    VariantNotFound,
    approve_variant,
    edit_variant,
    reject_variant,
)
from app.services.scheduling import (
    InvalidScheduleTime,
    VariantNotApproved,
    create_schedule_slot,
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


def invalid_edit_detail(
    exc: InvalidVariantEdit,
) -> dict[str, object]:
    return {
        "message":
            "Variant violates platform constraints.",

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
    }


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
                "message":
                    "Generated variant violated "
                    "its platform constraints.",

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


@router.put(
    "/variants/{variant_id}",
    response_model=VariantRead,
)
def update_variant(
    variant_id: int,
    payload: VariantUpdate,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return edit_variant(
            session,
            variant_id=variant_id,
            content=payload.content,
        )

    except VariantNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except InvalidReviewTransition as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except InvalidVariantEdit as exc:
        raise HTTPException(
            status_code=422,
            detail=invalid_edit_detail(
                exc
            ),
        ) from exc


@router.post(
    "/variants/{variant_id}/approve",
    response_model=VariantRead,
)
def approve_variant_endpoint(
    variant_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return approve_variant(
            session,
            variant_id,
        )

    except VariantNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except InvalidReviewTransition as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except InvalidVariantEdit as exc:
        raise HTTPException(
            status_code=422,
            detail=invalid_edit_detail(
                exc
            ),
        ) from exc


@router.post(
    "/variants/{variant_id}/reject",
    response_model=VariantRead,
)
def reject_variant_endpoint(
    variant_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return reject_variant(
            session,
            variant_id,
        )

    except VariantNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except InvalidReviewTransition as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


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
                "message":
                    "Variant violates platform "
                    "constraints.",

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


@router.post(
    "/variants/{variant_id}/schedule",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
def schedule_variant(
    variant_id: int,
    payload: ScheduleCreate,
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

    try:
        return create_schedule_slot(
            session,
            variant=variant,
            scheduled_at=payload.scheduled_at,
        )

    except VariantNotApproved as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except InvalidScheduleTime as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/schedules",
    response_model=list[ScheduleRead],
)
def list_schedules(
    session: Session = Depends(
        get_session
    ),
):
    return session.scalars(
        select(ScheduleSlot)
        .order_by(
            ScheduleSlot.id
        )
    ).all()


@router.get(
    "/schedules/{slot_id}",
    response_model=ScheduleRead,
)
def get_schedule(
    slot_id: int,
    session: Session = Depends(
        get_session
    ),
):
    slot = session.get(
        ScheduleSlot,
        slot_id,
    )

    if slot is None:
        raise HTTPException(
            status_code=404,
            detail="Schedule slot not found.",
        )

    return slot


# ============================================================
# Phase 4 publishing endpoints
# ============================================================

from app.models import (
    MockPublishedPost as Phase4MockPublishedPost,
    PublishAttempt as Phase4PublishAttempt,
)
from app.schemas import (
    MockPublishedPostRead as Phase4MockPublishedPostRead,
    PublishAttemptRead as Phase4PublishAttemptRead,
    PublishOutcomeRead as Phase4PublishOutcomeRead,
)
from app.services.publishing import (
    PublishInProgress as Phase4PublishInProgress,
    PublishNotAllowed as Phase4PublishNotAllowed,
    ScheduleNotFound as Phase4ScheduleNotFound,
    publish_slot as phase4_publish_slot,
)


@router.post(
    "/schedules/{slot_id}/publish",
    response_model=Phase4PublishOutcomeRead,
)
def publish_schedule_slot(
    slot_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return phase4_publish_slot(
            session,
            slot_id=slot_id,
        )

    except Phase4ScheduleNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Phase4PublishNotAllowed as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except Phase4PublishInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Publishing provider failed: "
                f"{exc}"
            ),
        ) from exc


@router.get(
    "/publish-history",
    response_model=list[
        Phase4PublishAttemptRead
    ],
)
def publish_history(
    session: Session = Depends(
        get_session
    ),
):
    return session.scalars(
        select(
            Phase4PublishAttempt
        )
        .order_by(
            Phase4PublishAttempt.id
        )
    ).all()


@router.get(
    "/mock-posts",
    response_model=list[
        Phase4MockPublishedPostRead
    ],
)
def list_mock_posts(
    session: Session = Depends(
        get_session
    ),
):
    return session.scalars(
        select(
            Phase4MockPublishedPost
        )
        .order_by(
            Phase4MockPublishedPost.id
        )
    ).all()


# ============================================================
# Stretch Goal API
# ============================================================

import os as stretch_os

from app.models import (
    AIGeneratedVariant as StretchAIGeneratedVariant,
    AIUsageRecord as StretchAIUsageRecord,
    Tenant as StretchTenant,
    TenantCampaign as StretchTenantCampaign,
    TenantVariant as StretchTenantVariant,
)
from app.schemas import (
    ABWinnerSelect as StretchABWinnerSelect,
    AIGeneratedVariantRead as StretchAIGeneratedVariantRead,
    AIUsageRead as StretchAIUsageRead,
    GroundingCheckRead as StretchGroundingCheckRead,
    GroundingCheckRequest as StretchGroundingCheckRequest,
    OllamaGenerateRequest as StretchOllamaGenerateRequest,
    PlatformName as StretchPlatformName,
    TenantCampaignCreate as StretchTenantCampaignCreate,
    TenantCampaignRead as StretchTenantCampaignRead,
    TenantCreate as StretchTenantCreate,
    TenantRead as StretchTenantRead,
    TenantVariantRead as StretchTenantVariantRead,
)
from app.services.ollama import (
    OllamaGenerationError as StretchOllamaGenerationError,
    generate_with_ollama as stretch_generate_with_ollama,
)
from app.services.stretch import (
    StretchConflict as StretchServiceConflict,
    StretchNotFound as StretchServiceNotFound,
    StretchValidationError as StretchServiceValidationError,
    choose_ab_winner as stretch_choose_ab_winner,
    create_ab_experiment as stretch_create_ab_experiment,
    create_tenant as stretch_create_tenant,
    create_tenant_campaign as stretch_create_tenant_campaign,
    experiment_payload as stretch_experiment_payload,
    generate_tenant_variants as stretch_generate_tenant_variants,
    get_ab_experiment as stretch_get_ab_experiment,
    grounding_for_post as stretch_grounding_for_post,
    promote_ab_winner as stretch_promote_ab_winner,
    require_tenant as stretch_require_tenant,
    require_tenant_campaign as stretch_require_tenant_campaign,
)


def stretch_http_error(
    exc: Exception,
) -> HTTPException:
    if isinstance(
        exc,
        StretchServiceNotFound,
    ):
        return HTTPException(
            status_code=404,
            detail=str(exc),
        )

    if isinstance(
        exc,
        StretchServiceConflict,
    ):
        return HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return HTTPException(
        status_code=422,
        detail=str(exc),
    )


@router.post(
    "/posts/{post_id}/ab-experiments/{platform}",
    status_code=status.HTTP_201_CREATED,
)
def create_ab_experiment_endpoint(
    post_id: int,
    platform: StretchPlatformName,
    session: Session = Depends(
        get_session
    ),
):
    try:
        experiment, options = (
            stretch_create_ab_experiment(
                session,
                post_id=post_id,
                platform=platform,
            )
        )

        return stretch_experiment_payload(
            experiment,
            options,
        )

    except (
        StretchServiceNotFound,
        StretchServiceConflict,
        StretchServiceValidationError,
    ) as exc:
        raise stretch_http_error(
            exc
        ) from exc


@router.get(
    "/ab-experiments/{experiment_id}",
)
def get_ab_experiment_endpoint(
    experiment_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        experiment, options = (
            stretch_get_ab_experiment(
                session,
                experiment_id,
            )
        )

        return stretch_experiment_payload(
            experiment,
            options,
        )

    except StretchServiceNotFound as exc:
        raise stretch_http_error(
            exc
        ) from exc


@router.post(
    "/ab-experiments/{experiment_id}/winner",
)
def choose_ab_winner_endpoint(
    experiment_id: int,
    payload: StretchABWinnerSelect,
    session: Session = Depends(
        get_session
    ),
):
    try:
        experiment, options = (
            stretch_choose_ab_winner(
                session,
                experiment_id=experiment_id,
                label=payload.label,
            )
        )

        return stretch_experiment_payload(
            experiment,
            options,
        )

    except (
        StretchServiceNotFound,
        StretchServiceConflict,
        StretchServiceValidationError,
    ) as exc:
        raise stretch_http_error(
            exc
        ) from exc


@router.post(
    "/ab-experiments/{experiment_id}/promote",
    response_model=VariantRead,
)
def promote_ab_winner_endpoint(
    experiment_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return stretch_promote_ab_winner(
            session,
            experiment_id=experiment_id,
        )

    except (
        StretchServiceNotFound,
        StretchServiceConflict,
        StretchServiceValidationError,
    ) as exc:
        raise stretch_http_error(
            exc
        ) from exc


@router.post(
    "/posts/{post_id}/grounding-check",
    response_model=StretchGroundingCheckRead,
)
def grounding_check_endpoint(
    post_id: int,
    payload: StretchGroundingCheckRequest,
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

    result = stretch_grounding_for_post(
        post,
        payload.content,
    )

    return StretchGroundingCheckRead(
        grounded=result.grounded,
        coverage=result.coverage,
        unsupported_numbers=(
            result.unsupported_numbers
        ),
        supported_tokens=(
            result.supported_tokens
        ),
        candidate_tokens=(
            result.candidate_tokens
        ),
    )


@router.post(
    "/posts/{post_id}/ollama/{platform}",
    response_model=StretchAIGeneratedVariantRead,
    status_code=status.HTTP_201_CREATED,
)
def ollama_generate_endpoint(
    post_id: int,
    platform: StretchPlatformName,
    payload: StretchOllamaGenerateRequest,
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

    model = (
        payload.model
        or stretch_os.getenv(
            "OLLAMA_MODEL",
            "gemma4:e4b-it",
        )
    )

    base_url = stretch_os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )

    try:
        return stretch_generate_with_ollama(
            session,
            post=post,
            platform=platform,
            model=model,
            base_url=base_url,
        )

    except StretchOllamaGenerationError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@router.get(
    "/ai-usage",
    response_model=list[
        StretchAIUsageRead
    ],
)
def ai_usage_endpoint(
    session: Session = Depends(
        get_session
    ),
):
    return session.scalars(
        select(
            StretchAIUsageRecord
        )
        .order_by(
            StretchAIUsageRecord.id
        )
    ).all()


@router.post(
    "/tenants",
    response_model=StretchTenantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant_endpoint(
    payload: StretchTenantCreate,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return stretch_create_tenant(
            session,
            name=payload.name,
            slug=payload.slug,
        )

    except StretchServiceConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get(
    "/tenants",
    response_model=list[
        StretchTenantRead
    ],
)
def list_tenants_endpoint(
    session: Session = Depends(
        get_session
    ),
):
    return session.scalars(
        select(
            StretchTenant
        )
        .order_by(
            StretchTenant.id
        )
    ).all()


@router.post(
    "/tenants/{tenant_id}/campaigns",
    response_model=StretchTenantCampaignRead,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant_campaign_endpoint(
    tenant_id: int,
    payload: StretchTenantCampaignCreate,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return stretch_create_tenant_campaign(
            session,
            tenant_id=tenant_id,
            title=payload.title,
            markdown=payload.markdown,
        )

    except StretchServiceNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/tenants/{tenant_id}/campaigns",
    response_model=list[
        StretchTenantCampaignRead
    ],
)
def list_tenant_campaigns_endpoint(
    tenant_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        stretch_require_tenant(
            session,
            tenant_id,
        )

    except StretchServiceNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return session.scalars(
        select(
            StretchTenantCampaign
        )
        .where(
            StretchTenantCampaign.tenant_id
            == tenant_id
        )
        .order_by(
            StretchTenantCampaign.id
        )
    ).all()


@router.get(
    "/tenants/{tenant_id}/campaigns/{campaign_id}",
    response_model=StretchTenantCampaignRead,
)
def get_tenant_campaign_endpoint(
    tenant_id: int,
    campaign_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return stretch_require_tenant_campaign(
            session,
            tenant_id=tenant_id,
            campaign_id=campaign_id,
        )

    except StretchServiceNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/tenants/{tenant_id}/campaigns/{campaign_id}/variants",
    response_model=list[
        StretchTenantVariantRead
    ],
    status_code=status.HTTP_201_CREATED,
)
def generate_tenant_variants_endpoint(
    tenant_id: int,
    campaign_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        return stretch_generate_tenant_variants(
            session,
            tenant_id=tenant_id,
            campaign_id=campaign_id,
        )

    except (
        StretchServiceNotFound,
        StretchServiceValidationError,
    ) as exc:
        raise stretch_http_error(
            exc
        ) from exc


@router.get(
    "/tenants/{tenant_id}/campaigns/{campaign_id}/variants",
    response_model=list[
        StretchTenantVariantRead
    ],
)
def list_tenant_variants_endpoint(
    tenant_id: int,
    campaign_id: int,
    session: Session = Depends(
        get_session
    ),
):
    try:
        campaign = (
            stretch_require_tenant_campaign(
                session,
                tenant_id=tenant_id,
                campaign_id=campaign_id,
            )
        )

    except StretchServiceNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return session.scalars(
        select(
            StretchTenantVariant
        )
        .where(
            StretchTenantVariant.campaign_id
            == campaign.id
        )
        .order_by(
            StretchTenantVariant.id
        )
    ).all()
