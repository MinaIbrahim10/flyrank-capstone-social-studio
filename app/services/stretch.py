from __future__ import annotations

from dataclasses import dataclass
import re
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ABExperiment,
    ABOption,
    Post,
    Tenant,
    TenantCampaign,
    TenantVariant,
    Variant,
)
from app.services.constraints import (
    PROFILES,
    validate_variant,
)
from app.services.generator import (
    BUILDERS,
    concise_fragment,
    fit_text,
    normalize_source,
    words,
)


class StretchNotFound(
    LookupError
):
    pass


class StretchConflict(
    ValueError
):
    pass


class StretchValidationError(
    ValueError
):
    pass


@dataclass(frozen=True)
class GroundingResult:
    grounded: bool
    coverage: float
    unsupported_numbers: list[str]
    supported_tokens: int
    candidate_tokens: int


GROUNDING_IGNORE = {
    "about",
    "after",
    "again",
    "another",
    "angle",
    "blog",
    "content",
    "could",
    "from",
    "have",
    "insights",
    "into",
    "more",
    "professional",
    "quick",
    "social",
    "take",
    "takeaway",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "today",
    "using",
    "with",
    "worth",
    "your",
}


TOKEN_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_'’-]{2,}"
)

NUMBER_RE = re.compile(
    r"(?<!\w)"
    r"\d+(?:[.,]\d+)?%?"
    r"(?!\w)"
)


def significant_tokens(
    text: str,
) -> set[str]:
    result: set[str] = set()

    for token in TOKEN_RE.findall(
        text.casefold()
    ):
        token = token.strip(
            "_'-’"
        )

        if len(token) < 4:
            continue

        if token in GROUNDING_IGNORE:
            continue

        if token.isdigit():
            continue

        result.add(
            token
        )

    return result


def check_grounding(
    *,
    source: str,
    candidate: str,
) -> GroundingResult:
    source_numbers = set(
        NUMBER_RE.findall(
            source
        )
    )

    candidate_numbers = set(
        NUMBER_RE.findall(
            candidate
        )
    )

    unsupported_numbers = sorted(
        candidate_numbers
        - source_numbers
    )

    source_tokens = significant_tokens(
        source
    )

    candidate_tokens = significant_tokens(
        candidate
    )

    supported = (
        candidate_tokens
        & source_tokens
    )

    if candidate_tokens:
        coverage = (
            len(supported)
            / len(candidate_tokens)
        )

    else:
        coverage = 1.0

    grounded = (
        not unsupported_numbers
        and coverage >= 0.55
    )

    return GroundingResult(
        grounded=grounded,
        coverage=round(
            coverage,
            4,
        ),
        unsupported_numbers=(
            unsupported_numbers
        ),
        supported_tokens=len(
            supported
        ),
        candidate_tokens=len(
            candidate_tokens
        ),
    )


def grounding_for_post(
    post: Post,
    candidate: str,
) -> GroundingResult:
    source = (
        f"{post.title}\n"
        f"{post.markdown}"
    )

    return check_grounding(
        source=source,
        candidate=candidate,
    )


def build_b_variant(
    post: Post,
    platform: str,
) -> str:
    source = normalize_source(
        post.markdown
    )

    if platform == "discord":
        content = (
            f"Quick take — {post.title}\n\n"
            f"{words(source, 65)}\n\n"
            "#blog"
        )

    elif platform == "mock_x":
        body = concise_fragment(
            source,
            19,
        )

        suffix = " #blog"

        available = (
            PROFILES[
                "mock_x"
            ].max_length
            - len(suffix)
        )

        content = (
            fit_text(
                (
                    f"Worth noting — "
                    f"{body}"
                ),
                available,
            )
            + suffix
        )

    elif platform == "mock_linkedin":
        content = (
            f"Another angle: "
            f"{post.title}\n\n"
            f"{words(source, 95)}\n\n"
            "#Insights #Content"
        )

    else:
        raise StretchValidationError(
            f"Unsupported platform: {platform}"
        )

    content = fit_text(
        content,
        PROFILES[
            platform
        ].max_length,
    )

    violations = validate_variant(
        platform,
        content,
    )

    if violations:
        names = ", ".join(
            item.rule
            for item in violations
        )

        raise StretchValidationError(
            "A/B option B violated: "
            + names
        )

    return content


def create_ab_experiment(
    session: Session,
    *,
    post_id: int,
    platform: str,
) -> tuple[
    ABExperiment,
    list[ABOption],
]:
    post = session.get(
        Post,
        post_id,
    )

    if post is None:
        raise StretchNotFound(
            "Post not found."
        )

    if platform not in BUILDERS:
        raise StretchValidationError(
            f"Unsupported platform: {platform}"
        )

    existing = session.scalar(
        select(
            ABExperiment
        )
        .where(
            ABExperiment.post_id
            == post_id,
            ABExperiment.platform
            == platform,
        )
    )

    if existing is not None:
        options = session.scalars(
            select(
                ABOption
            )
            .where(
                ABOption.experiment_id
                == existing.id
            )
            .order_by(
                ABOption.label
            )
        ).all()

        return (
            existing,
            list(options),
        )

    option_a = BUILDERS[
        platform
    ](
        post
    )

    option_b = build_b_variant(
        post,
        platform,
    )

    if option_a == option_b:
        raise StretchValidationError(
            "A/B options must be distinct."
        )

    for content in (
        option_a,
        option_b,
    ):
        violations = validate_variant(
            platform,
            content,
        )

        if violations:
            raise StretchValidationError(
                "A/B option violated "
                + ", ".join(
                    item.rule
                    for item in violations
                )
            )

    experiment = ABExperiment(
        post_id=post_id,
        platform=platform,
        status="open",
        winner_label=None,
    )

    session.add(
        experiment
    )

    session.flush()

    options = [
        ABOption(
            experiment_id=experiment.id,
            label="A",
            content=option_a,
            is_winner=False,
        ),
        ABOption(
            experiment_id=experiment.id,
            label="B",
            content=option_b,
            is_winner=False,
        ),
    ]

    session.add_all(
        options
    )

    session.commit()

    session.refresh(
        experiment
    )

    for option in options:
        session.refresh(
            option
        )

    return (
        experiment,
        options,
    )


def get_ab_experiment(
    session: Session,
    experiment_id: int,
) -> tuple[
    ABExperiment,
    list[ABOption],
]:
    experiment = session.get(
        ABExperiment,
        experiment_id,
    )

    if experiment is None:
        raise StretchNotFound(
            "A/B experiment not found."
        )

    options = session.scalars(
        select(
            ABOption
        )
        .where(
            ABOption.experiment_id
            == experiment.id
        )
        .order_by(
            ABOption.label
        )
    ).all()

    return (
        experiment,
        list(options),
    )


def choose_ab_winner(
    session: Session,
    *,
    experiment_id: int,
    label: str,
) -> tuple[
    ABExperiment,
    list[ABOption],
]:
    experiment, options = (
        get_ab_experiment(
            session,
            experiment_id,
        )
    )

    if label not in {
        "A",
        "B",
    }:
        raise StretchValidationError(
            "Winner label must be A or B."
        )

    selected = None

    for option in options:
        option.is_winner = (
            option.label
            == label
        )

        if option.is_winner:
            selected = option

        session.add(
            option
        )

    if selected is None:
        raise StretchValidationError(
            "Selected A/B option does not exist."
        )

    experiment.winner_label = label
    experiment.status = "decided"

    session.add(
        experiment
    )

    session.commit()

    session.refresh(
        experiment
    )

    return (
        experiment,
        options,
    )


def promote_ab_winner(
    session: Session,
    *,
    experiment_id: int,
) -> Variant:
    experiment, options = (
        get_ab_experiment(
            session,
            experiment_id,
        )
    )

    if (
        experiment.status
        != "decided"
        or not experiment.winner_label
    ):
        raise StretchConflict(
            "Choose an A/B winner before promotion."
        )

    winner = next(
        (
            item
            for item in options
            if item.label
            == experiment.winner_label
        ),
        None,
    )

    if winner is None:
        raise StretchConflict(
            "Winner option is missing."
        )

    violations = validate_variant(
        experiment.platform,
        winner.content,
    )

    if violations:
        raise StretchValidationError(
            "Winning option no longer "
            "passes platform constraints."
        )

    variant = session.scalar(
        select(
            Variant
        )
        .where(
            Variant.post_id
            == experiment.post_id,
            Variant.platform
            == experiment.platform,
        )
    )

    if variant is None:
        variant = Variant(
            post_id=experiment.post_id,
            platform=experiment.platform,
            content=winner.content,
            status="draft",
        )

        session.add(
            variant
        )

    else:
        if variant.status == "published":
            raise StretchConflict(
                "Published core variant cannot "
                "be replaced by an A/B winner."
            )

        variant.content = winner.content
        variant.status = "draft"

        session.add(
            variant
        )

    session.commit()
    session.refresh(
        variant
    )

    return variant


def experiment_payload(
    experiment: ABExperiment,
    options: list[ABOption],
) -> dict[str, object]:
    return {
        "id":
            experiment.id,

        "post_id":
            experiment.post_id,

        "platform":
            experiment.platform,

        "status":
            experiment.status,

        "winner_label":
            experiment.winner_label,

        "options": [
            {
                "id":
                    option.id,

                "label":
                    option.label,

                "content":
                    option.content,

                "is_winner":
                    option.is_winner,
            }
            for option
            in options
        ],
    }


def create_tenant(
    session: Session,
    *,
    name: str,
    slug: str,
) -> Tenant:
    tenant = Tenant(
        name=name.strip(),
        slug=slug.strip(),
    )

    session.add(
        tenant
    )

    try:
        session.commit()

    except IntegrityError as exc:
        session.rollback()

        raise StretchConflict(
            "Tenant slug already exists."
        ) from exc

    session.refresh(
        tenant
    )

    return tenant


def require_tenant(
    session: Session,
    tenant_id: int,
) -> Tenant:
    tenant = session.get(
        Tenant,
        tenant_id,
    )

    if tenant is None:
        raise StretchNotFound(
            "Tenant not found."
        )

    return tenant


def create_tenant_campaign(
    session: Session,
    *,
    tenant_id: int,
    title: str,
    markdown: str,
) -> TenantCampaign:
    require_tenant(
        session,
        tenant_id,
    )

    campaign = TenantCampaign(
        tenant_id=tenant_id,
        title=title,
        markdown=markdown,
    )

    session.add(
        campaign
    )

    session.commit()

    session.refresh(
        campaign
    )

    return campaign


def require_tenant_campaign(
    session: Session,
    *,
    tenant_id: int,
    campaign_id: int,
) -> TenantCampaign:
    require_tenant(
        session,
        tenant_id,
    )

    campaign = session.scalar(
        select(
            TenantCampaign
        )
        .where(
            TenantCampaign.id
            == campaign_id,
            TenantCampaign.tenant_id
            == tenant_id,
        )
    )

    if campaign is None:
        raise StretchNotFound(
            "Campaign not found for this tenant."
        )

    return campaign


def generate_tenant_variants(
    session: Session,
    *,
    tenant_id: int,
    campaign_id: int,
) -> list[TenantVariant]:
    campaign = require_tenant_campaign(
        session,
        tenant_id=tenant_id,
        campaign_id=campaign_id,
    )

    existing = session.scalars(
        select(
            TenantVariant
        )
        .where(
            TenantVariant.campaign_id
            == campaign.id
        )
        .order_by(
            TenantVariant.id
        )
    ).all()

    if existing:
        return list(
            existing
        )

    pseudo_post = SimpleNamespace(
        title=campaign.title,
        markdown=campaign.markdown,
    )

    result: list[
        TenantVariant
    ] = []

    for platform, builder in (
        BUILDERS.items()
    ):
        content = builder(
            pseudo_post
        )

        violations = validate_variant(
            platform,
            content,
        )

        if violations:
            raise StretchValidationError(
                (
                    f"Tenant {platform} variant "
                    "violated constraints."
                )
            )

        variant = TenantVariant(
            campaign_id=campaign.id,
            platform=platform,
            content=content,
            status="draft",
        )

        session.add(
            variant
        )

        result.append(
            variant
        )

    session.commit()

    for variant in result:
        session.refresh(
            variant
        )

    return result
