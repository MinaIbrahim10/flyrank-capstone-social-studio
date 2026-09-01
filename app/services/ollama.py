from __future__ import annotations

import re
import time

import httpx
from sqlalchemy.orm import Session

from app.models import (
    AIGeneratedVariant,
    AIUsageRecord,
    Post,
)
from app.services.constraints import (
    validate_variant,
)
from app.services.generator import (
    BUILDERS,
)
from app.services.stretch import (
    grounding_for_post,
)


class OllamaGenerationError(
    RuntimeError
):
    pass


def clean_model_response(
    value: str,
) -> str:
    text = value.strip()

    text = re.sub(
        r"^```(?:text|markdown)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    text = text.strip()

    if (
        len(text) >= 2
        and text[0] == '"'
        and text[-1] == '"'
    ):
        text = text[1:-1].strip()

    return text


def build_prompt(
    *,
    post: Post,
    platform: str,
) -> str:
    return f"""
You are generating one social post.

Platform: {platform}

Rules:
- Return ONLY the social post.
- Use only facts present in the source.
- Never invent numbers, prices, dates, names, statistics or claims.
- Keep the meaning grounded in the source.
- Respect the platform length and tone requirements.

Title:
{post.title}

Source:
{post.markdown}
""".strip()


def record_failed_usage(
    session: Session,
    *,
    post: Post,
    model: str,
    prompt: str,
    error: str,
) -> None:
    usage = AIUsageRecord(
        post_id=post.id,
        provider="ollama",
        model=model,
        prompt_tokens=0,
        completion_tokens=0,
        input_chars=len(
            prompt
        ),
        output_chars=0,
        cost_usd=0.0,
        success=False,
        error=error,
    )

    session.add(
        usage
    )

    session.commit()


def generate_with_ollama(
    session: Session,
    *,
    post: Post,
    platform: str,
    model: str,
    base_url: str,
    client: object | None = None,
) -> AIGeneratedVariant:
    if platform not in BUILDERS:
        raise OllamaGenerationError(
            f"Unsupported platform: {platform}"
        )

    prompt = build_prompt(
        post=post,
        platform=platform,
    )

    owned_client = None

    if client is None:
        owned_client = httpx.Client(
            timeout=180.0
        )

        active_client = (
            owned_client
        )

    else:
        active_client = client

    started = time.monotonic()

    try:
        response = active_client.post(
            (
                base_url.rstrip("/")
                + "/api/generate"
            ),
            json={
                "model":
                    model,

                "prompt":
                    prompt,

                "stream":
                    False,
            },
            timeout=180.0,
        )

        response.raise_for_status()

        payload = response.json()

        raw = str(
            payload.get(
                "response",
                "",
            )
        )

        candidate = clean_model_response(
            raw
        )

        if not candidate:
            raise OllamaGenerationError(
                "Ollama returned empty content."
            )

    except Exception as exc:
        error = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        record_failed_usage(
            session,
            post=post,
            model=model,
            prompt=prompt,
            error=error,
        )

        if isinstance(
            exc,
            OllamaGenerationError,
        ):
            raise

        raise OllamaGenerationError(
            error
        ) from exc

    finally:
        if owned_client is not None:
            owned_client.close()

    elapsed_ms = int(
        (
            time.monotonic()
            - started
        )
        * 1000
    )

    grounding = grounding_for_post(
        post,
        candidate,
    )

    violations = validate_variant(
        platform,
        candidate,
    )

    used_fallback = bool(
        violations
        or not grounding.grounded
    )

    if used_fallback:
        candidate = BUILDERS[
            platform
        ](
            post
        )

        grounding = grounding_for_post(
            post,
            candidate,
        )

    final_violations = validate_variant(
        platform,
        candidate,
    )

    if final_violations:
        raise OllamaGenerationError(
            "Final guarded AI output violated "
            "platform constraints."
        )

    prompt_tokens = int(
        payload.get(
            "prompt_eval_count",
            0,
        )
        or 0
    )

    completion_tokens = int(
        payload.get(
            "eval_count",
            0,
        )
        or 0
    )

    generated = AIGeneratedVariant(
        post_id=post.id,
        platform=platform,
        provider="ollama",
        model=model,
        content=candidate,
        grounded=True,
        used_fallback=used_fallback,
    )

    usage = AIUsageRecord(
        post_id=post.id,
        provider="ollama",
        model=model,
        prompt_tokens=(
            prompt_tokens
        ),
        completion_tokens=(
            completion_tokens
        ),
        input_chars=len(
            prompt
        ),
        output_chars=len(
            raw
        ),
        # Local Ollama has no per-token API charge.
        cost_usd=0.0,
        success=True,
        error=(
            (
                "guarded_fallback "
                f"elapsed_ms={elapsed_ms}"
            )
            if used_fallback
            else (
                f"elapsed_ms={elapsed_ms}"
            )
        ),
    )

    session.add(
        generated
    )

    session.add(
        usage
    )

    session.commit()

    session.refresh(
        generated
    )

    return generated
