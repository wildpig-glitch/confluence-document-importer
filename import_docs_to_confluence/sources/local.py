from __future__ import annotations

import fnmatch
import mimetypes
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from import_docs_to_confluence.models import Document
from import_docs_to_confluence.sources.base import DocumentSource


class LocalDocumentSource(DocumentSource):
    """Read documents from a local directory."""

    def __init__(
        self,
        directory: Path | str,
        *,
        recursive: bool = False,
        include_globs: Sequence[str] | None = None,
        exclude_globs: Sequence[str] | None = None,
    ) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.recursive = recursive
        self.include_globs = tuple(include_globs or ["*"])
        self.exclude_globs = tuple(exclude_globs or [])

    def iter_documents(self) -> Iterator[Document]:
        if not self.directory.exists():
            raise FileNotFoundError(f"Local directory does not exist: {self.directory}")
        if not self.directory.is_dir():
            raise NotADirectoryError(f"Local path is not a directory: {self.directory}")

        paths: Iterable[Path] = self.directory.rglob("*") if self.recursive else self.directory.iterdir()
        for path in sorted(paths, key=lambda item: str(item).lower()):
            if not path.is_file():
                continue
            relative_path = path.relative_to(self.directory)
            if not self._matches(relative_path):
                continue

            mime_type, _ = mimetypes.guess_type(path.name)
            yield Document(
                title=self._title_from_path(path),
                attachment_path=path,
                original_name=path.name,
                source_type="local",
                metadata={
                    "relative_path": str(relative_path),
                    "mime_type": mime_type or "application/octet-stream",
                    "size_bytes": str(path.stat().st_size),
                },
            )

    def _matches(self, relative_path: Path) -> bool:
        as_posix = relative_path.as_posix()
        included = any(fnmatch.fnmatch(as_posix, pattern) for pattern in self.include_globs)
        excluded = any(fnmatch.fnmatch(as_posix, pattern) for pattern in self.exclude_globs)
        return included and not excluded

    @staticmethod
    def _title_from_path(path: Path) -> str:
        # Preserve dots inside names: "Architecture.v2.pdf" -> "Architecture.v2".
        return path.stem.strip() or path.name
