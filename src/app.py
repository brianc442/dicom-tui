from __future__ import annotations
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from .config import Config
from .dicom_reader import load_tags
from .widgets.directory_modal import DirectoryModal
from .widgets.export_modal import ExportModal
from .widgets.file_list import FileListPanel
from .widgets.filter_modal import FilterModal
from .widgets.metadata_panel import MetadataPanel


class DicomTuiApp(App):
    """DICOM Metadata Extractor — split-pane TUI."""

    TITLE = "DICOM Metadata Extractor"
    BINDINGS = [
        ("e", "export", "Export"),
        ("f", "filter", "Filter"),
        ("d", "directory", "Directory"),
        ("q", "quit", "Quit"),
    ]
    CSS = """
    FileListPanel {
        width: 35%;
        border-right: solid $primary;
    }
    MetadataPanel {
        width: 65%;
    }
    .error {
        color: $error;
    }
    """

    def __init__(self, directory: Path, config: Config) -> None:
        super().__init__()
        self._current_dir = Path(directory).resolve()
        self._config = config
        self._all_files: list[Path] = []
        self._current_file: Path | None = None
        self._all_tags: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield FileListPanel()
            yield MetadataPanel(include=self._config.include)
        yield Footer()

    def on_mount(self) -> None:
        self._all_files = self.query_one(FileListPanel).load_directory(self._current_dir)
        if self._config.warning:
            self.notify(self._config.warning, severity="warning")

    def on_file_list_panel_file_selected(
        self, event: FileListPanel.FileSelected
    ) -> None:
        self._current_file = event.path
        full_tags = load_tags(event.path)
        self._all_tags = list(full_tags.keys())
        self.query_one(MetadataPanel).load_file(full_tags)

    def action_export(self) -> None:
        self.push_screen(
            ExportModal(
                all_files=self._all_files,
                current_file=self._current_file,
                active_tags=self._config.include,
            )
        )

    def action_filter(self) -> None:
        self.push_screen(
            FilterModal(
                all_tags=self._all_tags,
                active_include=self._config.include,
                config_path=self._config.source_path,
            ),
            callback=self._on_filter_result,
        )

    def _on_filter_result(self, include: list[str] | None) -> None:
        if include is None:
            return
        self._config.include = include
        self.query_one(MetadataPanel).update_filter(include)

    def action_directory(self) -> None:
        self.push_screen(
            DirectoryModal(self._current_dir),
            callback=self._on_directory_result,
        )

    def _on_directory_result(self, path: Path | None) -> None:
        if path:
            self._current_dir = path
            self._current_file = None
            self._all_tags = []
            self.query_one(MetadataPanel).load_file({})
            self._all_files = self.query_one(FileListPanel).load_directory(path)
