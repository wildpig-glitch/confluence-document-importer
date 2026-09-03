from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from import_docs_to_confluence.models import Document


class DocumentSource(ABC):
    """Interface for document providers.

    Future sources, such as Google Drive, should implement this interface and
    yield Documents whose `attachment_path` points to a local file available for
    upload. That local file may be the original file or an exported/downloaded
    temporary file.
    """

    @abstractmethod
    def iter_documents(self) -> Iterator[Document]:
        """Yield documents available from this source."""
