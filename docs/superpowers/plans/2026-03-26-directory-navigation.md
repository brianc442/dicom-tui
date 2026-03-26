# Directory Navigation & Recursive Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible directory tree pane, subdirectory navigation, background file scanning with streaming results, and recursive scan mode to the TUI.

**Architecture:** Replace the synchronous flat file scan with a `@work(thread=True)` background worker that streams DICOM paths into the file list as found. Add a new `DirectoryTreePanel` widget (wrapping Textual's `DirectoryTree` filtered to dirs only) as the leftmost of three panes. A scan-ID mechanism handles mid-scan cancellation without thread interruption.

**Tech Stack:** `textual` (DirectoryTree, work decorator, Worker), `pydicom`, `os.walk` for recursive filesystem traversal.

---

## File Map

| File | Status | Change |
|---|---|---|
| `src/dicom_reader.py` | modify | Add `iter_dicoms()`, update `find_dicoms()` to use it (no longer sorted) |
| `src/widgets/directory_tree_panel.py` | create | `DirOnlyTree` subclass + `DirectoryTreePanel` wrapper widget |
| `src/widgets/file_list.py` | modify | Replace `load_directory()` with `scan()` + worker; add `files` property; add scan-status label |
| `src/app.py` | modify | Three-pane layout; new `\` and `R` bindings; remove `_all_files` state; new tree handlers |
| `tests/test_dicom_reader.py` | modify | Delete `test_find_dicoms_sorted_by_name`; add `iter_dicoms` tests |
| `tests/test_file_list.py` | create | Tests for `scan()` behaviour using Textual test harness |

---

## Task 1: `iter_dicoms()` in `dicom_reader.py`

**Files:**
- Modify: `src/dicom_reader.py`
- Modify: `tests/test_dicom_reader.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_dicom_reader.py` (keep all existing tests, including their imports):

```python
from src.dicom_reader import iter_dicoms


# --- iter_dicoms ---

def test_iter_dicoms_flat_yields_dicoms(tmp_path):
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(tmp_path / "IM000002")
    (tmp_path / "notes.txt").write_text("not a dicom")
    result = list(iter_dicoms(tmp_path))
    assert len(result) == 2
    names = {p.name for p in result}
    assert names == {"IM000001", "IM000002"}


def test_iter_dicoms_flat_skips_subdirectories(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    make_minimal_dicom(tmp_path / "IM000001")
    result = list(iter_dicoms(tmp_path))
    assert len(result) == 1
    assert result[0].name == "IM000001"


def test_iter_dicoms_recursive_descends_subdirs(tmp_path):
    sub = tmp_path / "series1"
    sub.mkdir()
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(sub / "IM000002")
    result = list(iter_dicoms(tmp_path, recursive=True))
    names = {p.name for p in result}
    assert names == {"IM000001", "IM000002"}


def test_iter_dicoms_recursive_deeply_nested(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    make_minimal_dicom(deep / "IM000001")
    result = list(iter_dicoms(tmp_path, recursive=True))
    assert len(result) == 1
    assert result[0].name == "IM000001"


def test_iter_dicoms_empty_directory(tmp_path):
    assert list(iter_dicoms(tmp_path)) == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --extra dev pytest tests/test_dicom_reader.py::test_iter_dicoms_flat_yields_dicoms -v
```

Expected: `FAILED` with `ImportError: cannot import name 'iter_dicoms'`

- [ ] **Step 3: Implement `iter_dicoms()` and update `find_dicoms()`**

In `src/dicom_reader.py`, add `import os` and `from collections.abc import Iterator` to the imports block (after the existing imports), then:

Replace the existing `find_dicoms` function with:

```python
def iter_dicoms(directory: Path, recursive: bool = False) -> Iterator[Path]:
    """Yield DICOM file paths as confirmed by magic-byte check, in filesystem order."""
    if recursive:
        for root, _dirs, files in os.walk(directory):
            for name in files:
                p = Path(root) / name
                if is_dicom(p):
                    yield p
    else:
        for p in directory.iterdir():
            if is_dicom(p):
                yield p


def find_dicoms(directory: Path) -> list[Path]:
    """Return all DICOM files in directory (non-recursive), in filesystem order."""
    return list(iter_dicoms(directory))
```

- [ ] **Step 4: Delete the sorted-order test**

In `tests/test_dicom_reader.py`, delete this entire test (it asserts alphabetical order, which we no longer guarantee):

```python
def test_find_dicoms_sorted_by_name(tmp_path):
    make_minimal_dicom(tmp_path / "IM000003")
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(tmp_path / "IM000002")
    result = find_dicoms(tmp_path)
    assert [p.name for p in result] == ["IM000001", "IM000002", "IM000003"]
```

- [ ] **Step 5: Run all dicom_reader tests**

```
uv run --extra dev pytest tests/test_dicom_reader.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dicom_reader.py tests/test_dicom_reader.py
git commit -m "feat: add iter_dicoms() generator; find_dicoms() no longer sorts"
```

---

## Task 2: `DirectoryTreePanel` widget

**Files:**
- Create: `src/widgets/directory_tree_panel.py`

No unit tests — this is a pure Textual UI widget. It is integration-tested implicitly when the app runs.

- [ ] **Step 1: Create the widget**

Create `src/widgets/directory_tree_panel.py` with this content:

```python
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
```

- [ ] **Step 2: Verify the module imports cleanly**

```
uv run python -c "from src.widgets.directory_tree_panel import DirectoryTreePanel; print('ok')"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/widgets/directory_tree_panel.py
git commit -m "feat: add DirectoryTreePanel widget with directory-only tree"
```

---

## Task 3: Rewrite `FileListPanel` with background scanning

**Files:**
- Modify: `src/widgets/file_list.py`
- Create: `tests/test_file_list.py`

- [ ] **Step 1: Add `asyncio_mode = "auto"` to `pyproject.toml`**

`textual[dev]` includes `pytest-asyncio`, but pytest needs to know to run async test functions automatically. Add this section to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Verify the existing tests still pass:

```
uv run --extra dev pytest tests/ -v
```

Expected: all existing tests PASS.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_file_list.py`:

```python
from __future__ import annotations
import pytest
from pathlib import Path
from textual.app import App, ComposeResult
from tests.conftest import make_minimal_dicom
from src.widgets.file_list import FileListPanel


class ScanTestApp(App):
    def compose(self) -> ComposeResult:
        yield FileListPanel()


@pytest.mark.asyncio
async def test_scan_populates_files(tmp_path):
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(tmp_path / "IM000002")
    (tmp_path / "notes.txt").write_text("not a dicom")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.files) == 2
        names = {p.name for p in panel.files}
        assert names == {"IM000001", "IM000002"}


@pytest.mark.asyncio
async def test_scan_empty_directory(tmp_path):
    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert panel.files == []


@pytest.mark.asyncio
async def test_scan_second_call_supersedes_first(tmp_path):
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    make_minimal_dicom(dir1 / "scan_a")
    make_minimal_dicom(dir2 / "scan_b")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(dir1)
        panel.scan(dir2)   # immediately supersedes dir1 scan via scan_id
        await pilot.pause(1.0)
        names = {p.name for p in panel.files}
        assert "scan_b" in names
        assert "scan_a" not in names


@pytest.mark.asyncio
async def test_scan_recursive_finds_nested_dicoms(tmp_path):
    sub = tmp_path / "series"
    sub.mkdir()
    make_minimal_dicom(tmp_path / "root_scan")
    make_minimal_dicom(sub / "nested_scan")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path, recursive=True)
        await pilot.pause(1.0)
        names = {p.name for p in panel.files}
        assert "root_scan" in names
        assert "nested_scan" in names
```

- [ ] **Step 3: Run tests to confirm they fail**

```
uv run --extra dev pytest tests/test_file_list.py -v
```

Expected: `FAILED` — `FileListPanel` has no `scan()` method or `files` property yet.

- [ ] **Step 4: Rewrite `src/widgets/file_list.py`**

Replace the entire file with:

```python
from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView
from textual.worker import work

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

        self._do_scan(path, recursive, current_id)

    @work(thread=True)
    def _do_scan(self, path: Path, recursive: bool, scan_id: int) -> None:
        for dicom_path in iter_dicoms(path, recursive):
            self.app.call_from_thread(self._on_file_found, dicom_path, scan_id)
        self.app.call_from_thread(self._on_scan_done, scan_id)

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
```

- [ ] **Step 5: Run the file_list tests**

```
uv run --extra dev pytest tests/test_file_list.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

```
uv run --extra dev pytest tests/ -v
```

Expected: all tests PASS. (The exporter and config tests call `find_dicoms()` via the wrapper — those still work.)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/widgets/file_list.py tests/test_file_list.py
git commit -m "feat: rewrite FileListPanel with background worker and streaming scan"
```

---

## Task 4: Update `app.py` for three-pane layout

**Files:**
- Modify: `src/app.py`

No new tests — `app.py` wires together widgets already tested individually.

- [ ] **Step 1: Replace `src/app.py`**

Replace the entire file with:

```python
from __future__ import annotations
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DirectoryTree, Footer, Header

from .config import Config
from .dicom_reader import load_tags
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
        ("r", "recursive", "Recurse"),
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
        self._current_file: Path | None = None
        self._all_tags: list[str] = []
        self._recursive_mode: bool = False
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
        self._current_file = event.path
        full_tags = load_tags(event.path)
        self._all_tags = list(full_tags.keys())
        self.query_one(MetadataPanel).load_file(full_tags)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected_tree_dir = event.path
        self._current_file = None
        self._all_tags = []
        self.query_one(MetadataPanel).load_file({})
        self.query_one(FileListPanel).scan(event.path, recursive=self._recursive_mode)

    def action_toggle_tree(self) -> None:
        self.query_one(Horizontal).toggle_class("tree-hidden")

    def action_recursive(self) -> None:
        self._recursive_mode = not self._recursive_mode
        if self._recursive_mode:
            self.query_one(DirectoryTreePanel).expand_all()
        self.query_one(FileListPanel).scan(
            self._selected_tree_dir, recursive=self._recursive_mode
        )

    def action_export(self) -> None:
        self.push_screen(
            ExportModal(
                all_files=self.query_one(FileListPanel).files,
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
            self._selected_tree_dir = path
            self._current_file = None
            self._all_tags = []
            self.query_one(MetadataPanel).load_file({})
            self.query_one(DirectoryTreePanel).load_directory(path)
            self.query_one(FileListPanel).scan(path, recursive=self._recursive_mode)
```

- [ ] **Step 2: Run the full test suite**

```
uv run --extra dev pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Smoke-test the running app**

```
uv run python -m src .
```

Verify:
- Three panes visible (tree left, files middle, metadata right)
- Selecting a directory in the tree populates the file list
- `\` collapses/restores the tree pane
- `R` toggles recursive mode (expands tree nodes, rescans)
- `D` opens the directory modal; typing a valid path navigates the tree
- Files stream in with "Scanning…" counter visible during scan

- [ ] **Step 4: Commit**

```bash
git add src/app.py
git commit -m "feat: three-pane layout with collapsible tree and recursive scan mode"
```
