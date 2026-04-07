from __future__ import annotations

from datetime import datetime

from connectors import BaseConnector, ConnectorDocument


class ManualMinIOConnector(BaseConnector):
    """Manual upload adapter — reads from MinIO vizier-assets bucket.

    This is the only connector implemented during the sprint.
    Future connectors (Google Drive, Instagram, WhatsApp) implement
    the same BaseConnector interface.
    """

    def load(self, source_config: dict) -> list[ConnectorDocument]:
        raise NotImplementedError("Implemented post-sprint")

    def poll(self, source_config: dict, since: datetime) -> list[ConnectorDocument]:
        raise NotImplementedError("Implemented post-sprint")

    def slim(self, source_config: dict) -> list[dict]:
        raise NotImplementedError("Implemented post-sprint")
