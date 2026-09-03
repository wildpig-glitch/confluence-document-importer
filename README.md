# Confluence Document Importer

A lightweight Python command-line tool for importing local documents into Confluence Cloud.

For each file in a local directory, the importer creates a Confluence page and attaches the original file to that page. It is designed so additional document sources, such as Google Drive, can be added later without changing the Confluence publishing logic.

## What it does

Given a local folder like this:

```text
docs/
├── onboarding.pdf
├── architecture-notes.docx
└── release-plan.txt
```

The importer creates pages like this under a selected Confluence parent page:

```text
Selected parent page
├── onboarding
├── architecture-notes
└── release-plan
```

Each created page contains a small metadata table and has the corresponding source file attached.

## Current status

This version supports:

- Importing files from a local directory
- Optional recursive file discovery
- Creating one Confluence page per file
- Attaching the original file to the created page
- Using a Confluence parent page URL instead of manually finding the page ID
- Safe default handling for duplicate page titles by appending suffixes like `-1`, `-2`, etc.
- Dry-run mode for local discovery validation

Planned future support:

- Google Drive folder import
- Exporting Google Docs, Sheets, and Slides before upload
- Optional folder hierarchy mirroring in Confluence

## Requirements

- Python 3.10 or newer recommended
- A Confluence Cloud site
- A Confluence API token
- Permission to create pages and upload attachments in the target Confluence space

## Installation

Clone the repository:

```bash
git clone https://github.com/wildpig-glitch/confluence-document-importer.git
cd confluence-document-importer
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

> Note: dry-run mode for local file discovery can run without installing dependencies, but real Confluence imports require `requests`.

## Authentication

The importer uses Confluence Cloud basic authentication with your Atlassian email address and an API token.

You can provide credentials with CLI flags:

```bash
--confluence-email "you@example.com" \
--confluence-api-token "YOUR_API_TOKEN"
```

Or place them in a local `.env` file:

```bash
cp .env.example .env
```

Then edit `.env`:

```bash
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_EMAIL=you@example.com
CONFLUENCE_API_TOKEN=your-api-token
```

Do not commit `.env`. It is ignored by `.gitignore`.

## Recommended usage

The easiest way to select the destination is to paste the Confluence parent page URL.

First run a dry run:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Parent+Page" \
  --dry-run
```

Then run the real import:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Parent+Page" \
  --confluence-email "you@example.com" \
  --confluence-api-token "YOUR_API_TOKEN"
```

For a URL like this:

```text
https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Parent+Page
```

The importer infers:

```text
site:   https://your-domain.atlassian.net/wiki
space:  SPACEKEY
parent: 123456789
```

## Recursive import

By default, only files directly inside `--local-dir` are imported.

Use `--recursive` to include files in subdirectories:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --recursive \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Parent+Page" \
  --confluence-email "you@example.com" \
  --confluence-api-token "YOUR_API_TOKEN"
```

Recursive mode currently discovers files recursively but creates all pages directly under the same selected Confluence parent page. It does not mirror the local directory structure in Confluence.

Example local tree:

```text
docs/
├── a.txt
├── b.txt
└── folder-1/
    ├── c.txt
    └── d.txt
```

With `--recursive`, the Confluence result is:

```text
Parent page
├── a
├── b
├── c
└── d
```

## Include and exclude patterns

Only import PDFs and Word documents:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --include '*.pdf' \
  --include '*.docx' \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Parent+Page" \
  --confluence-email "you@example.com" \
  --confluence-api-token "YOUR_API_TOKEN"
```

Exclude temporary files:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --exclude '~$*' \
  --exclude '*.tmp' \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Parent+Page" \
  --confluence-email "you@example.com" \
  --confluence-api-token "YOUR_API_TOKEN"
```

## Duplicate page title behavior

By default, the importer uses:

```bash
--on-existing rename
```

If a page title already exists in the target Confluence space, the new page is created with a suffix.

Example:

```text
example
example-1
example-2
```

Available policies:

| Policy | Behavior |
| --- | --- |
| `rename` | Default. Create a new page using the next available suffix. |
| `skip` | Skip the file if a page with the same title already exists. |
| `fail` | Report an error if a page with the same title already exists. |
| `update` | Update the existing page body and upload a new attachment version. |

Example:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --parent-page-url "https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Parent+Page" \
  --on-existing fail \
  --confluence-email "you@example.com" \
  --confluence-api-token "YOUR_API_TOKEN"
```

## Supported parent page URL formats

Preferred format:

```text
https://your-domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Page+Title
```

This can infer the site, space key, and parent page ID.

Legacy format:

```text
https://your-domain.atlassian.net/wiki/pages/viewpage.action?pageId=123456789
```

This can infer the site and parent page ID, but not the space key. When using this format, also pass `--space-key`.

Short links such as `/wiki/x/...` are not supported in this version.

## Explicit target usage

Instead of using `--parent-page-url`, you can pass the target pieces manually:

```bash
python3 -m import_docs_to_confluence \
  --local-dir ./docs \
  --confluence-base-url https://your-domain.atlassian.net/wiki \
  --space-key SPACEKEY \
  --parent-page-id 123456789 \
  --confluence-email "you@example.com" \
  --confluence-api-token "YOUR_API_TOKEN"
```

If `--parent-page-id` is omitted, pages are created at the root of the target space.

## CLI reference

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

## Test fixture

This repository includes a small `docs/` directory that can be used for testing:

```text
docs/
├── a.txt
├── b.txt
├── c.txt
├── example.txt
├── directory-1/
│   ├── d.txt
│   ├── e.txt
│   └── summary.txt
└── directory-2/
    ├── f.txt
    └── summary.txt
```

The two `summary.txt` files are useful for testing duplicate title handling with recursive imports.

## Troubleshooting

### `ModuleNotFoundError: No module named 'requests'`

Real Confluence imports require dependencies. Use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### `externally-managed-environment`

On macOS with Homebrew Python, avoid installing packages globally. Use a virtual environment instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### `'latin-1' codec can't encode character '\u201c'`

This usually means a value was pasted with smart quotes:

```text
“you@example.com”
```

Use normal shell quotes instead:

```text
"you@example.com"
```

The importer strips surrounding smart quotes from common CLI values, but if the value still contains unsupported characters, retype the email or token using plain ASCII characters.

## Design notes

The code is split into source and publishing layers:

```text
DocumentSource -> Document -> ConfluencePublisher
```

Current source:

```text
LocalDocumentSource
```

A future Google Drive source can implement the same `DocumentSource` interface and yield downloaded or exported files as `Document` objects. The Confluence publisher should not need to know where the file came from.

## Limitations

- The importer attaches files but does not convert document contents into Confluence page content.
- The duplicate-title check is currently space-wide, not parent-page scoped.
- Recursive mode does not mirror folders as Confluence page hierarchy.
- Google Drive import is planned but not yet implemented.

## License

No license has been added yet. Add one before distributing broadly if needed.
