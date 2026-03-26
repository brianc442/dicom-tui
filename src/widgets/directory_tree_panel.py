from __future__ import annotations
from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DirectoryTree


class DirOnlyTree(DirectoryTree):
    """DirectoryTree subclass that shows only directories, never files."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [p for p in paths if p.is_dir()]


class DirectoryTreePanel(Widget):
    """Left panel — directory tree for navigating to a folder."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._initial_path = path

    def compose(self) -> ComposeResult:
        yield DirOnlyTree(self._initial_path)

    def load_directory(self, path: Path) -> None:
        """Navigate the tree to a new root path."""
        self.query_one(DirOnlyTree).path = path

    def expand_all(self) -> None:
        """Recursively expand all nodes in the tree."""
        self.query_one(DirOnlyTree).root.expand_all()
