from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConnectorDocument:
    """A document ingested by a connector."""
    source_id: str
    title: str
    content: str
    mime_type: str
    metadata: dict = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


class BaseConnector(ABC):
    """Abstract base for all data connectors.

    Three modes:
    - Load: bulk ingest (initial sync)
    - Poll: incremental updates (scheduled)
    - Slim: metadata-only pass (for indexing without full content)
    """

    @abstractmethod
    def load(self, source_config: dict) -> list[ConnectorDocument]:
        """Bulk ingest all documents from source."""
        ...

    @abstractmethod
    def poll(self, source_config: dict, since: datetime) -> list[ConnectorDocument]:
        """Fetch documents modified since last poll."""
        ...

    @abstractmethod
    def slim(self, source_config: dict) -> list[dict]:
        """Return metadata-only list (no content) for indexing."""
        ...
