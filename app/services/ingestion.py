from __future__ import annotations

from html.parser import HTMLParser
import re

import httpx
from sqlalchemy.orm import Session

from app.models import Post
from app.schemas import PostCreate


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()

        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() in {
            "script",
            "style",
            "noscript",
        }:
            self.ignored_depth += 1

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if (
            tag.lower()
            in {
                "script",
                "style",
                "noscript",
            }
            and self.ignored_depth > 0
        ):
            self.ignored_depth -= 1

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self.ignored_depth != 0:
            return

        cleaned = data.strip()

        if cleaned:
            self.parts.append(cleaned)

    def text(self) -> str:
        return "\n\n".join(
            self.parts
        )


def html_to_text(
    html: str,
) -> str:
    parser = TextExtractor()
    parser.feed(html)

    text = parser.text()

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def fetch_url_content(
    url: str,
) -> str:
    response = httpx.get(
        url,
        timeout=10.0,
        follow_redirects=True,
        headers={
            "User-Agent":
                "SocialMediaStudioCapstone/1.0",
        },
    )

    response.raise_for_status()

    content_type = (
        response.headers
        .get(
            "content-type",
            "",
        )
        .lower()
    )

    if "html" in content_type:
        content = html_to_text(
            response.text
        )
    else:
        content = response.text.strip()

    if not content:
        raise ValueError(
            "The URL returned empty content."
        )

    return content


def create_post(
    session: Session,
    payload: PostCreate,
) -> Post:
    if payload.markdown is not None:
        source_type = "markdown"
        source_url = None
        stored_content = (
            payload.markdown.strip()
        )

    else:
        source_type = "url"
        source_url = str(
            payload.url
        )

        stored_content = fetch_url_content(
            source_url
        )

    if not stored_content:
        raise ValueError(
            "Post content cannot be empty."
        )

    post = Post(
        title=payload.title.strip(),
        source_type=source_type,
        source_url=source_url,
        markdown=stored_content,
    )

    session.add(post)
    session.commit()
    session.refresh(post)

    return post
