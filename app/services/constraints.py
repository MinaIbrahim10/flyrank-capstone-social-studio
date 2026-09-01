from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PlatformProfile:
    name: str
    max_length: int
    max_hashtags: int
    tone: str
    max_sentences: int | None = None
    forbidden_tone_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstraintViolation:
    rule: str
    message: str


PROFILES: dict[str, PlatformProfile] = {
    "discord": PlatformProfile(
        name="discord",
        max_length=2000,
        max_hashtags=5,
        tone="conversational",
        forbidden_tone_terms=(
            "dear sir or madam",
            "to whom it may concern",
        ),
    ),

    "mock_x": PlatformProfile(
        name="mock_x",
        max_length=280,
        max_hashtags=2,
        tone="concise",
        max_sentences=2,
    ),

    "mock_linkedin": PlatformProfile(
        name="mock_linkedin",
        max_length=3000,
        max_hashtags=3,
        tone="professional",
        forbidden_tone_terms=(
            "lol",
            "lmao",
            "omg",
        ),
    ),
}


HASHTAG_RE = re.compile(
    r"(?<!\w)#[A-Za-z0-9_]+"
)

SENTENCE_RE = re.compile(
    r"[.!?]+"
)


def count_hashtags(
    content: str,
) -> int:
    return len(
        HASHTAG_RE.findall(
            content
        )
    )


def count_sentences(
    content: str,
) -> int:
    matches = SENTENCE_RE.findall(
        content
    )

    if matches:
        return len(matches)

    if content.strip():
        return 1

    return 0


def validate_variant(
    platform: str,
    content: str,
) -> list[ConstraintViolation]:
    profile = PROFILES.get(
        platform
    )

    if profile is None:
        return [
            ConstraintViolation(
                rule="platform",
                message=(
                    "Unknown platform profile: "
                    f"{platform}"
                ),
            )
        ]

    violations: list[
        ConstraintViolation
    ] = []

    if len(content) > profile.max_length:
        violations.append(
            ConstraintViolation(
                rule="max_length",
                message=(
                    f"{platform} allows at most "
                    f"{profile.max_length} characters; "
                    f"received {len(content)}."
                ),
            )
        )

    hashtag_count = count_hashtags(
        content
    )

    if (
        hashtag_count
        > profile.max_hashtags
    ):
        violations.append(
            ConstraintViolation(
                rule="hashtag_count",
                message=(
                    f"{platform} allows at most "
                    f"{profile.max_hashtags} hashtags; "
                    f"received {hashtag_count}."
                ),
            )
        )

    if (
        profile.max_sentences
        is not None
    ):
        sentence_count = count_sentences(
            content
        )

        if (
            sentence_count
            > profile.max_sentences
        ):
            violations.append(
                ConstraintViolation(
                    rule="tone",
                    message=(
                        f"{platform} requires a "
                        f"{profile.tone} style with at most "
                        f"{profile.max_sentences} sentences; "
                        f"received {sentence_count}."
                    ),
                )
            )

    lowered = content.lower()

    for term in (
        profile.forbidden_tone_terms
    ):
        if term in lowered:
            violations.append(
                ConstraintViolation(
                    rule="tone",
                    message=(
                        f"{platform} requires a "
                        f"{profile.tone} tone; "
                        f"forbidden phrase detected: "
                        f"'{term}'."
                    ),
                )
            )

    return violations
