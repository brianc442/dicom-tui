from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable

from ..dicom_reader import filter_tags, get_tag_id


class MetadataPanel(Widget):
    """Right panel — DataTable showing tag name, tag ID, and value."""

    def __init__(self, include: list[str] | None = None) -> None:
        super().__init__()
        self._include: list[str] = include or []
        self._full_tags: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        table = DataTable()
        table.add_columns("Tag Name", "Tag ID", "Value")
        yield table

    def load_file(self, full_tags: dict[str, str]) -> None:
        """Called by app.py with pre-loaded tags when a new file is selected."""
        self._full_tags = full_tags
        if not self._full_tags:
            table = self.query_one(DataTable)
            table.clear()
            table.add_row("(invalid DICOM file)", "", "")
            return
        self._refresh_table()

    def update_filter(self, include: list[str]) -> None:
        """Called by app.py after filter modal dismissal."""
        self._include = include
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        displayed = (
            filter_tags(self._full_tags, self._include)
            if self._include
            else self._full_tags
        )
        for kw, value in displayed.items():
            table.add_row(kw, get_tag_id(kw), value)
