from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Document:
    """A source document ready to publish into Confluence.

    The source can be a local file today, or a downloaded/exported temporary file
    from Google Drive later. `attachment_path` is the file that will be uploaded.
    """

    title: str
    attachment_path: Path
    original_name: str
    source_type: str
    metadata: Mapping[str, str] = field(default_factory=dict)
