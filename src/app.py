from __future__ import annotations
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DirectoryTree, Footer, Header

from .config import Config
from .dicom_reader import DicomStudy, load_tags
from .widgets.directory_modal import DirectoryModal
from .widgets.directory_tree_panel import DirectoryTreePanel
from .widgets.export_modal import ExportModal
from .widgets.file_list import FileListPanel
from .widgets.filter_modal import FilterModal
from .widgets.metadata_panel import MetadataPanel


class DicomTuiApp(App):
    """DICOM Metadata Extractor — three-pane TUI."""

    TITLE = "DICOM Metadata Extractor"
    BINDINGS = [
        ("backslash", "toggle_tree", "Tree"),
        ("e", "export", "Export"),
        ("f", "filter", "Filter"),
        ("d", "directory", "Directory"),
        ("q", "quit", "Quit"),
    ]
    CSS = """
    DirectoryTreePanel {
        width: 25%;
        border-right: solid $primary;
    }
    FileListPanel {
        width: 25%;
        border-right: solid $primary;
    }
    MetadataPanel {
        width: 50%;
    }
    Horizontal.tree-hidden DirectoryTreePanel {
        display: none;
    }
    Horizontal.tree-hidden FileListPanel {
        width: 35%;
    }
    Horizontal.tree-hidden MetadataPanel {
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
        self._current_study: DicomStudy | None = None
        self._all_tags: list[str] = []
        self._selected_tree_dir: Path = self._current_dir

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DirectoryTreePanel(self._current_dir)
            yield FileListPanel()
            yield MetadataPanel(include=self._config.include)
        yield Footer()

    def on_mount(self) -> None:
        self._selected_tree_dir = self._current_dir
        self.query_one(FileListPanel).scan(self._current_dir)
        if self._config.warning:
            self.notify(self._config.warning, severity="warning")

    def on_file_list_panel_file_selected(
        self, event: FileListPanel.FileSelected
    ) -> None:
        self._current_study = event.study
        full_tags = load_tags(event.study.representative)
        self._all_tags = list(full_tags.keys())
        self.query_one(MetadataPanel).load_file(full_tags)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected_tree_dir = event.path
        self._current_study = None
        self._all_tags = []
        self.query_one(MetadataPanel).load_file({})
        self.query_one(FileListPanel).scan(event.path)

    def action_toggle_tree(self) -> None:
        self.query_one(Horizontal).toggle_class("tree-hidden")

    def action_export(self) -> None:
        self.push_screen(
            ExportModal(
                all_studies=self.query_one(FileListPanel).studies,
                current_study=self._current_study,
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
            self._selected_tree_dir = path
            self._current_study = None
            self._all_tags = []
            self.query_one(MetadataPanel).load_file({})
            self.query_one(DirectoryTreePanel).load_directory(path)
            self.query_one(FileListPanel).scan(path)
