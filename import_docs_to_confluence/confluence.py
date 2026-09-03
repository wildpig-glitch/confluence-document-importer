from __future__ import annotations

import html
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests import Response
from requests.auth import HTTPBasicAuth

from import_docs_to_confluence.models import Document


@dataclass(frozen=True)
class ConfluencePage:
    id: str
    title: str
    web_url: str | None = None


class ConfluenceError(RuntimeError):
    """Raised when a Confluence API call fails."""


class ConfluencePublisher:
    """Publishes documents as Confluence pages with file attachments.

    This uses the Confluence Cloud REST v1 content APIs because they support a
    simple space-key based create flow and the standard attachment upload flow.
    """

    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        api_token: str,
        space_key: str,
        parent_page_id: str | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self.base_url = self._normalize_base_url(base_url)
        self.space_key = space_key
        self.parent_page_id = parent_page_id
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(email, api_token)
        self.session.headers.update({"Accept": "application/json"})

    def find_page_by_title(self, title: str) -> ConfluencePage | None:
        params = {
            "spaceKey": self.space_key,
            "title": title,
            "type": "page",
            "status": "current",
            "expand": "_links.webui",
        }
        response = self.session.get(self._url("/rest/api/content"), params=params, timeout=self.timeout_seconds)
        data = self._json_or_raise(response, "find page by title")
        results = data.get("results", [])
        if not results:
            return None

        # Confluence title lookup is exact within a space. If a parent page is
        # configured, callers normally avoid duplicates by title across the space;
        # this keeps v1 simple and predictable.
        return self._page_from_content(results[0])

    def create_page(self, document: Document) -> ConfluencePage:
        payload: dict[str, Any] = {
            "type": "page",
            "title": document.title,
            "space": {"key": self.space_key},
            "body": {
                "storage": {
                    "value": build_page_body(document),
                    "representation": "storage",
                }
            },
        }
        if self.parent_page_id:
            payload["ancestors"] = [{"id": self.parent_page_id}]

        response = self.session.post(self._url("/rest/api/content"), json=payload, timeout=self.timeout_seconds)
        data = self._json_or_raise(response, f"create page {document.title!r}")
        return self._page_from_content(data)

    def update_page_body(self, page: ConfluencePage, document: Document) -> ConfluencePage:
        current_response = self.session.get(
            self._url(f"/rest/api/content/{quote(page.id)}"),
            params={"expand": "version,_links.webui"},
            timeout=self.timeout_seconds,
        )
        current = self._json_or_raise(current_response, f"fetch current page {page.id}")
        next_version = int(current["version"]["number"]) + 1
        payload: dict[str, Any] = {
            "id": page.id,
            "type": "page",
            "title": document.title,
            "space": {"key": self.space_key},
            "version": {"number": next_version, "minorEdit": True},
            "body": {
                "storage": {
                    "value": build_page_body(document),
                    "representation": "storage",
                }
            },
        }
        if self.parent_page_id:
            payload["ancestors"] = [{"id": self.parent_page_id}]

        response = self.session.put(self._url(f"/rest/api/content/{quote(page.id)}"), json=payload, timeout=self.timeout_seconds)
        data = self._json_or_raise(response, f"update page {page.id}")
        return self._page_from_content(data)

    def attach_file(self, page_id: str, file_path: Path) -> None:
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Attachment path is not a file: {file_path}")

        existing_attachment_id = self._find_attachment_id(page_id, file_path.name)
        mime_type, _ = mimetypes.guess_type(file_path.name)
        headers = {"X-Atlassian-Token": "no-check"}
        data = {"minorEdit": "true", "comment": "Imported by document importer"}

        if existing_attachment_id:
            endpoint = f"/rest/api/content/{quote(page_id)}/child/attachment/{quote(existing_attachment_id)}/data"
        else:
            endpoint = f"/rest/api/content/{quote(page_id)}/child/attachment"

        with file_path.open("rb") as handle:
            files = {"file": (file_path.name, handle, mime_type or "application/octet-stream")}
            response = self.session.post(
                self._url(endpoint),
                headers=headers,
                data=data,
                files=files,
                timeout=self.timeout_seconds,
            )
        self._json_or_raise(response, f"attach file {file_path.name!r} to page {page_id}")

    def _find_attachment_id(self, page_id: str, filename: str) -> str | None:
        response = self.session.get(
            self._url(f"/rest/api/content/{quote(page_id)}/child/attachment"),
            params={"filename": filename, "expand": "version"},
            timeout=self.timeout_seconds,
        )
        data = self._json_or_raise(response, f"find attachment {filename!r}")
        results = data.get("results", [])
        if not results:
            return None
        return str(results[0]["id"])

    def _page_from_content(self, content: dict[str, Any]) -> ConfluencePage:
        webui = content.get("_links", {}).get("webui")
        web_url = f"{self.base_url}{webui}" if webui else None
        return ConfluencePage(id=str(content["id"]), title=str(content["title"]), web_url=web_url)

    def _json_or_raise(self, response: Response, action: str) -> dict[str, Any]:
        if response.ok:
            return response.json()
        try:
            body = response.json()
        except ValueError:
            body = response.text
        raise ConfluenceError(f"Confluence API failed to {action}: HTTP {response.status_code}: {body}")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        cleaned = base_url.rstrip("/")
        # Accept either https://example.atlassian.net or .../wiki.
        if not cleaned.endswith("/wiki"):
            cleaned = f"{cleaned}/wiki"
        return cleaned


def build_page_body(document: Document) -> str:
    """Build simple Confluence storage XHTML for a document container page."""
    rows = [
        ("Source", document.source_type),
        ("Original filename", document.original_name),
        ("Attachment filename", document.attachment_path.name),
    ]
    rows.extend((key.replace("_", " ").title(), value) for key, value in document.metadata.items())

    table_rows = "".join(
        "<tr>"
        f"<th>{html.escape(str(label))}</th>"
        f"<td>{html.escape(str(value))}</td>"
        "</tr>"
        for label, value in rows
    )
    return (
        "<h1>Imported Document</h1>"
        "<p>This page was automatically created for an imported source document. "
        "The original file is attached to this page.</p>"
        "<table>"
        "<tbody>"
        f"{table_rows}"
        "</tbody>"
        "</table>"
    )
