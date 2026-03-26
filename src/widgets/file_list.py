from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..dicom_reader import find_dicoms


class FileListPanel(Widget):
    """Left panel — scrollable list of DICOM files in the current directory."""

    class FileSelected(Message):
        """Posted when the user highlights a different file."""
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(self) -> None:
        super().__init__()
        self._files: list[Path] = []

    def compose(self) -> ComposeResult:
        yield ListView()

    def load_directory(self, path: Path) -> list[Path]:
        """Scan `path` for DICOM files, populate the list, and return discovered files."""
        list_view = self.query_one(ListView)
        list_view.clear()
        self._files = find_dicoms(path)
        if not self._files:
            list_view.append(ListItem(Label("No DICOM files found")))
        else:
            for f in self._files:
                list_view.append(ListItem(Label(f.name)))
        return self._files

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._files):
            self.post_message(self.FileSelected(self._files[idx]))
