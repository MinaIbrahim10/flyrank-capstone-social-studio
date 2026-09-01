from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Post,
    Variant,
)
from app.services.constraints import (
    PROFILES,
    validate_variant,
)


def normalize_source(
    markdown: str,
) -> str:
    text = markdown

    text = re.sub(
        r"```.*?```",
        " ",
        text,
        flags=re.DOTALL,
    )

    text = re.sub(
        r"!\[[^\]]*\]\([^)]+\)",
        " ",
        text,
    )

    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
    )

    text = re.sub(
        r"[#>*_`~-]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def words(
    text: str,
    count: int,
) -> str:
    return " ".join(
        text.split()[:count]
    )


def fit_text(
    text: str,
    max_length: int,
) -> str:
    text = text.strip()

    if len(text) <= max_length:
        return text

    return (
        text[: max_length - 1]
        .rstrip()
        + "…"
    )


def concise_fragment(
    text: str,
    max_words: int,
) -> str:
    fragment = words(
        text,
        max_words,
    )

    fragment = re.sub(
        r"[.!?]+",
        ",",
        fragment,
    )

    fragment = re.sub(
        r",+",
        ",",
        fragment,
    )

    return fragment.strip(
        " ,"
    )


def build_discord(
    post: Post,
) -> str:
    source = normalize_source(
        post.markdown
    )

    body = words(
        source,
        80,
    )

    content = (
        f"**{post.title}**\n\n"
        f"{body}\n\n"
        "#blog"
    )

    return fit_text(
        content,
        PROFILES["discord"].max_length,
    )


def build_x(
    post: Post,
) -> str:
    source = normalize_source(
        post.markdown
    )

    body = concise_fragment(
        source,
        24,
    )

    suffix = " #blog"

    available = (
        PROFILES["mock_x"].max_length
        - len(suffix)
    )

    content = (
        f"{post.title}: {body}"
    )

    return (
        fit_text(
            content,
            available,
        )
        + suffix
    )


def build_linkedin(
    post: Post,
) -> str:
    source = normalize_source(
        post.markdown
    )

    body = words(
        source,
        120,
    )

    content = (
        "Professional takeaway: "
        f"{post.title}\n\n"
        f"{body}\n\n"
        "#Insights #Content"
    )

    return fit_text(
        content,
        PROFILES[
            "mock_linkedin"
        ].max_length,
    )


BUILDERS = {
    "discord": build_discord,
    "mock_x": build_x,
    "mock_linkedin": build_linkedin,
}


class GeneratedVariantInvalid(
    ValueError
):
    def __init__(
        self,
        platform: str,
        violations: list[object],
    ) -> None:
        self.platform = platform
        self.violations = violations

        super().__init__(
            f"Generated {platform} variant "
            "violated its constraint profile."
        )


def generate_variants(
    session: Session,
    post: Post,
) -> list[Variant]:
    existing = session.scalars(
        select(Variant)
        .where(
            Variant.post_id
            == post.id
        )
        .order_by(
            Variant.id
        )
    ).all()

    existing_by_platform = {
        variant.platform:
            variant
        for variant in existing
    }

    result: list[Variant] = []

    for (
        platform,
        builder,
    ) in BUILDERS.items():
        current = (
            existing_by_platform
            .get(platform)
        )

        if current is not None:
            result.append(
                current
            )
            continue

        content = builder(
            post
        )

        violations = validate_variant(
            platform,
            content,
        )

        if violations:
            raise GeneratedVariantInvalid(
                platform,
                violations,
            )

        variant = Variant(
            post_id=post.id,
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
