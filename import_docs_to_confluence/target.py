from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class ConfluenceTarget:
    """Target values that can be inferred from a Confluence page URL."""

    base_url: str | None = None
    space_key: str | None = None
    parent_page_id: str | None = None


class ConfluenceUrlParseError(ValueError):
    """Raised when a Confluence page URL cannot be parsed."""


def parse_confluence_page_url(url: str) -> ConfluenceTarget:
    """Parse common Confluence Cloud page URLs.

    Supported formats:
    - https://site.atlassian.net/wiki/spaces/SPACE/pages/123456789/Page+Title
    - https://site.atlassian.net/wiki/pages/viewpage.action?pageId=123456789

    The legacy viewpage.action URL does not include a space key, so callers must
    provide --space-key or an equivalent environment/default value.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ConfluenceUrlParseError(f"Expected an absolute Confluence URL, got: {url}")

    path_parts = [part for part in parsed.path.split("/") if part]
    base_url = _base_url(parsed.scheme, parsed.netloc, path_parts)

    # Modern Cloud URL: /wiki/spaces/{spaceKey}/pages/{pageId}/{title}
    try:
        spaces_index = path_parts.index("spaces")
        pages_index = path_parts.index("pages")
    except ValueError:
        spaces_index = -1
        pages_index = -1

    if spaces_index >= 0 and pages_index >= 0:
        if len(path_parts) <= spaces_index + 1 or len(path_parts) <= pages_index + 1:
            raise ConfluenceUrlParseError(f"Could not find space key and page ID in URL: {url}")
        page_id = path_parts[pages_index + 1]
        if not page_id.isdigit():
            raise ConfluenceUrlParseError(f"Expected numeric page ID after /pages/ in URL: {url}")
        return ConfluenceTarget(
            base_url=base_url,
            space_key=path_parts[spaces_index + 1],
            parent_page_id=page_id,
        )

    # Legacy URL: /wiki/pages/viewpage.action?pageId={pageId}
    if path_parts[-2:] == ["pages", "viewpage.action"] or path_parts[-1:] == ["viewpage.action"]:
        page_ids = parse_qs(parsed.query).get("pageId", [])
        if not page_ids or not page_ids[0].isdigit():
            raise ConfluenceUrlParseError(f"Could not find numeric pageId query parameter in URL: {url}")
        return ConfluenceTarget(base_url=base_url, parent_page_id=page_ids[0])

    raise ConfluenceUrlParseError(
        "Unsupported Confluence page URL. Expected a URL like "
        "https://site.atlassian.net/wiki/spaces/SPACE/pages/123456789/Page+Title "
        "or https://site.atlassian.net/wiki/pages/viewpage.action?pageId=123456789"
    )


def _base_url(scheme: str, netloc: str, path_parts: list[str]) -> str:
    # Confluence Cloud normally lives under /wiki. Keep /wiki when present;
    # otherwise return the site origin and let ConfluencePublisher normalize it.
    if path_parts and path_parts[0] == "wiki":
        return f"{scheme}://{netloc}/wiki"
    return f"{scheme}://{netloc}"
