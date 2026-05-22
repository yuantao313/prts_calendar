from __future__ import annotations

from abc import ABC, abstractmethod


class DataSource(ABC):
    """Abstract base for calendar data sources.

    Subclasses should accept (source_id, name, params) in __init__,
    where *params* is the raw dict from config.json.
    """

    def __init__(self, source_id: str, name: str, params: dict):
        self.source_id = source_id
        self.name = name
        self.params = params
        self.uid_prefix = params.get("uid_prefix", source_id)

    @abstractmethod
    def get_events(self) -> list[dict]:
        """
        Return a list of event dicts.  Each dict has keys:
          - title       (str)
          - start       (datetime)
          - end         (datetime)
          - description (str, optional)
          - url         (str, optional)
        """

    def collect_events(self) -> list[dict]:
        """Convenience: fill missing optional keys."""
        events = self.get_events()
        for ev in events:
            ev.setdefault("description", "")
            ev.setdefault("url", "")
        return events
