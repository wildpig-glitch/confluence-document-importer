from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from import_docs_to_confluence.models import Document
from import_docs_to_confluence.sources import LocalDocumentSource
from import_docs_to_confluence.target import ConfluenceTarget, parse_confluence_page_url

ExistingPolicy = Literal["rename", "skip", "fail", "update"]


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv_if_available()
    args = parse_args(argv)

    source = build_source(args)
    target = resolve_target(args)
    print_target(target, dry_run=args.dry_run)
    publisher = None if args.dry_run else build_publisher(args, target)

    result = ImportResult()
    for document in source.iter_documents():
        try:
            process_document(
                document,
                publisher=publisher,
                existing_policy=args.on_existing,
                dry_run=args.dry_run,
                result=result,
            )
        except Exception as exc:  # Keep importing independent documents.
            result.failed += 1
            print(f"ERROR {document.original_name}: {exc}", file=sys.stderr)
            if args.stop_on_error:
                break

    print_summary(result, dry_run=args.dry_run)
    return 1 if result.failed else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one Confluence page per local document and attach the document file.",
    )
    parser.add_argument("--source", choices=["local"], default="local", help="Document source to import from.")
    parser.add_argument("--local-dir", type=Path, required=True, help="Directory containing files to import.")
    parser.add_argument("--recursive", action="store_true", help="Import files recursively from --local-dir.")
    parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Glob pattern to include, relative to --local-dir. Can be passed multiple times. Default: *",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Glob pattern to exclude, relative to --local-dir. Can be passed multiple times.",
    )

    parser.add_argument("--confluence-base-url", default=os.getenv("CONFLUENCE_BASE_URL"), help="Base URL, e.g. https://example.atlassian.net/wiki. Can be inferred from --parent-page-url.")
    parser.add_argument("--confluence-email", default=os.getenv("CONFLUENCE_EMAIL"), help="Confluence account email")
    parser.add_argument("--confluence-api-token", default=os.getenv("CONFLUENCE_API_TOKEN"), help="Confluence API token")
    parser.add_argument("--space-key", help="Target Confluence space key. Can be inferred from common --parent-page-url formats.")
    parser.add_argument("--parent-page-id", help="Optional parent page ID for imported pages")
    parser.add_argument("--parent-page-url", help="Optional Confluence parent page URL. Infers base URL, space key, and page ID when possible.")
    parser.add_argument(
        "--on-existing",
        choices=["rename", "skip", "fail", "update"],
        default="rename",
        help="What to do when a page with the same title already exists in the space.",
    )
    parser.add_argument("--dry-run", action="store_true", help="List actions without creating pages or uploading attachments.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop after the first failed document.")
    parser.add_argument("--timeout-seconds", type=float, default=30, help="HTTP timeout per Confluence request.")
    return parser.parse_args(argv)


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def build_source(args: argparse.Namespace) -> LocalDocumentSource:
    if args.source != "local":
        raise ValueError(f"Unsupported source: {args.source}")
    return LocalDocumentSource(
        args.local_dir,
        recursive=args.recursive,
        include_globs=args.include,
        exclude_globs=args.exclude,
    )


def resolve_target(args: argparse.Namespace) -> ConfluenceTarget:
    parent_page_url = normalize_config_value(args.parent_page_url, "PARENT_PAGE_URL") if args.parent_page_url else None
    inferred = parse_confluence_page_url(parent_page_url) if parent_page_url else ConfluenceTarget()
    target = ConfluenceTarget(
        base_url=normalize_config_value(args.confluence_base_url, "CONFLUENCE_BASE_URL") or inferred.base_url,
        space_key=normalize_config_value(args.space_key, "SPACE_KEY") or inferred.space_key,
        parent_page_id=normalize_config_value(args.parent_page_id, "PARENT_PAGE_ID") or inferred.parent_page_id,
    )
    if not target.space_key:
        raise ValueError(
            "Missing target space. Pass --space-key or use a parent URL in the form "
            "https://site.atlassian.net/wiki/spaces/SPACE/pages/PAGE_ID/Page+Title"
        )
    return target


def print_target(target: ConfluenceTarget, *, dry_run: bool) -> None:
    prefix = "Dry-run target" if dry_run else "Import target"
    print(f"{prefix}: site={target.base_url or '<not required for dry-run>'}, space={target.space_key}, parent={target.parent_page_id or '<space root>'}")


def build_publisher(args: argparse.Namespace, target: ConfluenceTarget) -> Any:
    try:
        from import_docs_to_confluence.confluence import ConfluencePublisher
    except ImportError as exc:
        raise RuntimeError(
            "The 'requests' package is required for real Confluence imports. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    email = value_from_arg_or_env(args.confluence_email, "CONFLUENCE_EMAIL")
    api_token = value_from_arg_or_env(args.confluence_api_token, "CONFLUENCE_API_TOKEN")
    validate_basic_auth_value(email, "CONFLUENCE_EMAIL")
    validate_basic_auth_value(api_token, "CONFLUENCE_API_TOKEN")

    return ConfluencePublisher(
        base_url=value_from_arg_or_env(target.base_url, "CONFLUENCE_BASE_URL"),
        email=email,
        api_token=api_token,
        space_key=value_from_arg_or_env(target.space_key, "SPACE_KEY"),
        parent_page_id=target.parent_page_id,
        timeout_seconds=args.timeout_seconds,
    )


def process_document(
    document: Document,
    *,
    publisher: Any | None,
    existing_policy: ExistingPolicy,
    dry_run: bool,
    result: ImportResult,
) -> None:
    print(f"Processing {document.original_name} -> page {document.title!r}")
    if dry_run:
        print(f"DRY RUN would create page {document.title!r} and attach {document.attachment_path}")
        result.created += 1
        return

    if publisher is None:
        raise ValueError("Publisher is required unless --dry-run is set.")

    existing_page = publisher.find_page_by_title(document.title)

    if existing_page:
        if existing_policy == "rename":
            original_title = document.title
            document = replace(document, title=next_available_title(publisher, document.title))
            print(f"RENAME page title {original_title!r} -> {document.title!r} to avoid a conflict")
        elif existing_policy == "skip":
            print(f"SKIP existing page: {existing_page.title} ({existing_page.web_url or existing_page.id})")
            result.skipped += 1
            return
        elif existing_policy == "fail":
            raise RuntimeError(f"Page already exists: {existing_page.title} ({existing_page.web_url or existing_page.id})")
        elif existing_policy == "update":
            page = publisher.update_page_body(existing_page, document)
            publisher.attach_file(page.id, document.attachment_path)
            print(f"UPDATED {page.title}: {page.web_url or page.id}")
            result.updated += 1
            return

    page = publisher.create_page(document)
    publisher.attach_file(page.id, document.attachment_path)
    print(f"CREATED {page.title}: {page.web_url or page.id}")
    result.created += 1


def next_available_title(publisher: Any, base_title: str) -> str:
    suffix = 1
    while True:
        candidate = f"{base_title}-{suffix}"
        if publisher.find_page_by_title(candidate) is None:
            return candidate
        suffix += 1


def normalize_config_value(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    quote_pairs = {
        '"': '"',
        "'": "'",
        "“": "”",
        "‘": "’",
    }
    if len(normalized) >= 2 and normalized[0] in quote_pairs and normalized[-1] == quote_pairs[normalized[0]]:
        normalized = normalized[1:-1].strip()
        print(f"Note: stripped surrounding quotes from {name}.")
    return normalized or None


def validate_basic_auth_value(value: str, name: str) -> None:
    try:
        value.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError(
            f"{name} contains a character that cannot be used in HTTP Basic Auth. "
            "This often happens when a command is pasted with smart quotes like “...” instead of normal quotes like \"...\". "
            f"Please re-enter {name} using plain ASCII characters."
        ) from exc


def value_from_arg_or_env(value: str | None, env_name: str) -> str:
    normalized = normalize_config_value(value, env_name)
    if normalized:
        return normalized
    raise ValueError(f"Missing required value. Pass argument or set {env_name}.")


def print_summary(result: ImportResult, *, dry_run: bool) -> None:
    prefix = "Dry-run summary" if dry_run else "Import summary"
    print(
        f"{prefix}: created={result.created}, updated={result.updated}, "
        f"skipped={result.skipped}, failed={result.failed}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
