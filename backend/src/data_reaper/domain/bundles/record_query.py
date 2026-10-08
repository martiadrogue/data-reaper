"""The filters a dataset record listing takes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordQuery:
    """Which records to list; `None` filters nothing.

    Attributes:
        text: Matched literally, any case, within the name or address.
        source: The exact source, e.g. `thefork.es`.
    """

    text: str | None = None
    source: str | None = None

    @property
    def has_filters(self) -> bool:
        """Return whether any filter is set."""
        return None is not self.text or None is not self.source
