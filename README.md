# Import documents to Confluence

A small Python CLI that creates one Confluence page per local document and attaches the source file to that page.

This is intentionally structured so the document source can later be swapped from local files to Google Drive without changing the Confluence publishing logic.

## Current scope: v1 local files

For each local file, the importer:

1. Derives a Confluence page title from the filename.
2. Creates a page in the target Confluence space, optionally under a parent page.
3. Adds a simple metadata table to the page body.
4. Uploads the original file as an attachment.

By default, if a page with the same title already exists in the target space, the importer creates the new page with a conflict-free suffix such as `-1`, `-2`, and so on.

## Project layout

```text
import_docs_to_confluence/
  __main__.py            # Lets you run: python -m import_docs_to_confluence
  cli.py                 # CLI entry point and orchestration
  confluence.py          # Confluence API client/publisher
  models.py              # Shared Document model
  target.py              # Confluence URL parsing and target resolution models
  sources/
    base.py              # DocumentSource interface
    local.py             # LocalDocumentSource implementation
```

For Google Drive v2, add a new source like:

```text
import_docs_to_confluence/sources/gdrive.py
```

that implements `DocumentSource.iter_documents()` and yields `Document` objects with local `attachment_path` values pointing to downloaded or exported files.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For dry-run-only local discovery, you can skip dependency installation and run the module directly with system Python.

Edit `.env` for real imports:

```bash
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_EMAIL=you@example.com
CONFLUENCE_API_TOKEN=your-api-token
```

You can also pass these values directly as CLI flags. If you pass `--parent-page-url`, the site, space key, and parent page ID can usually be inferred from that URL.

## Preferred usage: paste the parent page URL

Dry run first:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Imported+Docs" \
  --dry-run
```

Run the import:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Imported+Docs"
```

With this URL format, the importer infers:

```text
site:   https://your-domain.atlassian.net/wiki
space:  ENG
parent: 123456789
```

## Explicit target usage

You can still pass target pieces explicitly:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --confluence-base-url https://your-domain.atlassian.net/wiki \
  --space-key ENG \
  --parent-page-id 123456789
```

If both URL-inferred values and explicit flags are present, explicit flags win.

If you omit both `--parent-page-url` and `--parent-page-id`, pages are created at the root of the target space.

## Supported parent page URL formats

Supported and can infer site, space, and parent page ID:

```text
https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Page+Title
```

Supported but cannot infer the space key, so pass `--space-key` too:

```text
https://your-domain.atlassian.net/wiki/pages/viewpage.action?pageId=123456789
```

Example:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --parent-page-url "https://your-domain.atlassian.net/wiki/pages/viewpage.action?pageId=123456789" \
  --space-key ENG
```

Short links like `/wiki/x/...` are not supported in v1 because they require resolving the link through Confluence.

## Other examples

Recursive import:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --recursive \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Imported+Docs"
```

Only include PDFs and Word docs:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --include '*.pdf' \
  --include '*.docx' \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Imported+Docs"
```

Exclude temporary files:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --exclude '~$*' \
  --exclude '*.tmp' \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Imported+Docs"
```

## Existing page behavior

Use `--on-existing` to control duplicate page titles:

- `rename` default: create a new page using the next available suffix, for example `example-1`, `example-2`, etc.
- `skip`: leave existing page untouched and do not upload the attachment.
- `fail`: report an error for that document.
- `update`: replace the generated metadata body and upload a new attachment version if an attachment with the same filename already exists.

Example:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Imported+Docs" \
  --on-existing update
```

## CLI options

```text
--source local                 Source type. Currently only local is implemented.
--local-dir PATH               Directory containing files to import.
--recursive                    Import files recursively.
--include GLOB                 Include pattern relative to local dir. Repeatable.
--exclude GLOB                 Exclude pattern relative to local dir. Repeatable.
--parent-page-url URL          Optional Confluence parent page URL. Infers site, space, and parent when possible.
--confluence-base-url URL      Confluence base URL. May also use env var. Can be inferred from parent URL.
--confluence-email EMAIL       Confluence email. May also use env var.
--confluence-api-token TOKEN   Confluence API token. May also use env var.
--space-key KEY                Target Confluence space key. Can be inferred from common parent URL formats.
--parent-page-id ID            Optional parent page ID for imported pages. Can be inferred from parent URL.
--on-existing rename|skip|fail|update Existing page behavior. Default: rename.
--dry-run                      Print planned actions without creating pages or uploading attachments.
--stop-on-error                Stop after the first failed document.
--timeout-seconds N            Per-request HTTP timeout.
```

## Troubleshooting

### `'latin-1' codec can't encode character '\\u201c'`

This usually means one of the command values was pasted with smart quotes, for example:

```text
“your.email@example.com”
```

instead of normal shell quotes:

```text
"your.email@example.com"
```

The importer now strips surrounding smart quotes from common CLI/config values, but if the value still contains non-Basic-Auth characters, retype the email/token using plain ASCII characters.

### `ModuleNotFoundError: No module named 'requests'`

Real Confluence imports require dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Dry-runs do not require `requests`.

## Google Drive extension plan

A future `GoogleDriveDocumentSource` should:

1. Authenticate with Google Drive using OAuth or a service account.
2. List files from a configured folder ID.
3. For regular binary files, download them directly to a temporary working directory.
4. For Google-native files, export them to a chosen format, for example:
   - Google Docs -> `.docx` or `.pdf`
   - Google Sheets -> `.xlsx` or `.pdf`
   - Google Slides -> `.pptx` or `.pdf`
5. Yield the same `Document` model used by the local source.
6. Clean up temporary files after import.

The Confluence publisher should not need to know whether the file came from disk or Google Drive.

## Notes

- Page bodies are intentionally simple container pages; the source document content is not converted into Confluence page content.
- Attachments are uploaded as the original file. If `--on-existing update` is used and an attachment with the same filename exists, a new attachment version is uploaded.
- Page title lookup is currently space-wide by exact title, not parent-page-specific. This keeps v1 simple but means duplicate titles in different parts of the same space may still be treated as existing pages.
