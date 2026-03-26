from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..dicom_reader import iter_dicoms


class FileListPanel(Widget):
    """Middle panel — scrollable list of DICOM files in the selected directory."""

    DEFAULT_CSS = """
    FileListPanel #scan-status {
        display: none;
        color: $warning;
        padding: 0 1;
    }
    """

    class FileSelected(Message):
        """Posted when the user highlights a different file."""
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(self) -> None:
        super().__init__()
        self._files: list[Path] = []
        self._scan_id: int = 0

    def compose(self) -> ComposeResult:
        yield Label("", id="scan-status")
        yield ListView()

    @property
    def files(self) -> list[Path]:
        """Current list of discovered DICOM files."""
        return list(self._files)

    def scan(self, path: Path, recursive: bool = False) -> None:
        """Start a background scan of `path`. Supersedes any in-flight scan."""
        self._scan_id += 1
        current_id = self._scan_id
        self._files = []

        list_view = self.query_one(ListView)
        list_view.clear()

        status = self.query_one("#scan-status", Label)
        status.update("Scanning\u2026 (0 found)")
        status.display = True

        def _do_scan() -> None:
            for dicom_path in iter_dicoms(path, recursive):
                self.app.call_from_thread(self._on_file_found, dicom_path, current_id)
            self.app.call_from_thread(self._on_scan_done, current_id)

        self.run_worker(_do_scan, thread=True, exit_on_error=False)

    def _on_file_found(self, path: Path, scan_id: int) -> None:
        if scan_id != self._scan_id:
            return
        self._files.append(path)
        self.query_one(ListView).append(ListItem(Label(path.name)))
        self.query_one("#scan-status", Label).update(
            f"Scanning\u2026 ({len(self._files)} found)"
        )

    def _on_scan_done(self, scan_id: int) -> None:
        if scan_id != self._scan_id:
            return
        status = self.query_one("#scan-status", Label)
        status.display = False
        if not self._files:
            self.query_one(ListView).append(ListItem(Label("No DICOM files found")))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._files):
            self.post_message(self.FileSelected(self._files[idx]))
