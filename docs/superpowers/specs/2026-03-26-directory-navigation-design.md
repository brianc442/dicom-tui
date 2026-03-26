# Directory Navigation & Recursive Scan — Design Spec

**Date:** 2026-03-26
**Status:** Approved

---

## Overview

Adds a persistent directory tree pane to the TUI, subdirectory navigation, a recursive scan mode, and background scanning with streaming results. The tree pane is collapsible. A hotkey-triggered modal allows navigating to an arbitrary path by typing or pasting it.

---

## Use Cases

1. **Directory tree navigation** — browse the filesystem tree to select a directory; the file list populates with DICOMs from that directory.
2. **Recursive scan mode** — toggle recursive mode to expand all tree nodes and show DICOMs from the selected directory and all its descendants.
3. **Teleport to path** — open a modal, type or paste a path, and the tree navigates to that root.
4. **Collapsible tree** — hide the tree pane to reclaim horizontal space when not needed.
5. **Non-blocking scans** — large multi-file DICOM directories (500+ files) scan in the background; files stream into the list as found.

---

## Layout

### Tree visible (default)

```
┌─ DICOM Metadata Extractor ──────────────────────────────────────────────────┐
│ Directories (25%)    │ Files (25%)          │ Metadata (50%)                │
│──────────────────────│──────────────────────│───────────────────────────────│
│ ▼ /path/to/dicoms    │ Scanning... (3 found)│ Tag Name    Tag ID    Value   │
│   ▶ subdirA          │   scan001.dcm        │ PatientName (0010,..) John Do │
│   ▼ subdirB          │   scan002.dcm        │ ...                           │
│     ▶ sub-sub        │   scan003.dcm        │                               │
│──────────────────────┴──────────────────────┴───────────────────────────────│
│ [\] Tree  [R] Recurse  [E] Export  [F] Filter  [D] Directory  [Q] Quit      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tree collapsed (`\` toggles)

```
┌─ DICOM Metadata Extractor ──────────────────────────────────────────────────┐
│ Files (35%)               │ Metadata (65%)                                  │
│───────────────────────────│─────────────────────────────────────────────────│
│ > scan001.dcm             │ Tag Name    Tag ID    Value                     │
│   scan002.dcm             │ ...                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Keyboard Bindings

| Key | Action |
|---|---|
| `\` | Toggle directory tree pane |
| `R` | Toggle recursive mode (expands all tree nodes; file list shows DICOMs in selected dir + all descendants) |
| `D` | Open directory modal — navigate tree root to typed/pasted path |
| `E` | Open Export modal (unchanged) |
| `F` | Open Filter modal (unchanged) |
| `Q` | Quit (unchanged) |

---

## Project Structure Changes

```
src/
├── widgets/
│   ├── directory_tree_panel.py   # NEW — DirectoryTreePanel widget
│   ├── file_list.py              # MODIFIED — background worker, streaming
│   └── ...                       # other widgets unchanged
├── dicom_reader.py               # MODIFIED — add iter_dicoms()
└── app.py                        # MODIFIED — three-pane layout, new bindings/state
```

---

## Components

### `src/dicom_reader.py` — changes

**Add:**

```python
def iter_dicoms(directory: Path, recursive: bool = False) -> Iterator[Path]:
    """Yield DICOM file paths as they are confirmed, in filesystem order."""
```

- Non-recursive: iterates `directory.iterdir()`, calls `is_dicom()` on each entry, yields matching paths.
- Recursive: uses `os.walk(directory)` to descend into all subdirectories, calling `is_dicom()` on each file, yielding as confirmed.
- `is_dicom()` is unchanged — reads 132 bytes (the minimal magic-byte check). Per-file I/O cost is already minimal; the main performance win comes from running the iteration in a background thread rather than optimising the per-file check further.

**Keep unchanged:**

- `is_dicom()`, `load_tags()`, `filter_tags()`, `get_tag_id()`
- `find_dicoms()` becomes a thin wrapper: `return list(iter_dicoms(directory))` — results are in filesystem order (no sorting). All existing callers (exporter, tests) are unaffected; any tests that assert on ordering should be updated to not depend on sort order.

---

### `src/widgets/directory_tree_panel.py` — new widget `DirectoryTreePanel`

Textual `Widget` wrapping a `DirectoryTree` instance stored as `self._tree: DirectoryTree`.

**`filter_paths` override:** returns `True` only for directories — files are never shown in the tree.

**Methods:**

- `load_directory(path: Path) -> None` — sets `self._tree.path = path` and resets the tree to the new root. Called by `app.py` when the directory modal resolves.
- `expand_all() -> None` — calls `self._tree.root.expand_all()` to recursively open all tree nodes. Called by `app.py` when recursive mode is toggled on.

**Messages:** relies on Textual's built-in `DirectoryTree.DirectorySelected` — no custom messages needed. `app.py` handles `on_directory_tree_directory_selected`.

---

### `src/widgets/file_list.py` — `FileListPanel` changes

Replace the synchronous `load_directory(path)` method with a single `scan(path: Path, recursive: bool = False) -> None` method.

**`scan()` behaviour:**

`FileListPanel` stores `self._current_worker: Worker | None = None` to track the active scan.

1. If `self._current_worker` is not `None`, calls `self._current_worker.cancel()`.
2. Clears the `ListView`.
3. Appends a `Label("Scanning… (0 found)")` counter item with id `"scan-counter"`.
4. Resets `self._files: list[Path] = []`.
5. Starts a `@work(thread=True)` worker that iterates `iter_dicoms(path, recursive)`; stores the returned `Worker` in `self._current_worker`.
6. For each path yielded: calls `self.app.call_from_thread(self._on_file_found, path)`.
7. On worker completion (detected via `on_worker_state_changed` or within the worker function after the loop): calls `self.app.call_from_thread(self._on_scan_done)`.

**`_on_file_found(path: Path) -> None`** (called on UI thread):
- Appends `path` to `self._files`.
- Appends a `ListItem(Label(path.name))` to the `ListView`.
- Updates the counter label: `"Scanning… (N found)"`.

**`_on_scan_done() -> None`** (called on UI thread):
- Removes the counter label.
- If `self._files` is empty, shows `"No DICOM files found"`.

**`FileSelected` message and `on_list_view_highlighted` handler:** unchanged — still index into `self._files`.

**`load_directory()` removed** — all callers in `app.py` updated to call `scan()`.

---

### `src/widgets/directory_modal.py` — `DirectoryModal`

No changes to the widget itself. `app.py` changes how the result is used: instead of just reloading the file list, it also calls `DirectoryTreePanel.load_directory(path)` to navigate the tree to the new root.

---

### `src/app.py` — changes

**New state:**

```python
_recursive_mode: bool = False
_selected_tree_dir: Path  # set to _current_dir on mount, updated on tree selection
```

**Layout:**

```python
def compose(self) -> ComposeResult:
    yield Header()
    with Horizontal():
        yield DirectoryTreePanel()
        yield FileListPanel()
        yield MetadataPanel(include=self._config.include)
    yield Footer()
```

**CSS width assignments:**

```css
DirectoryTreePanel {
    width: 25%;
}
FileListPanel {
    width: 25%;
    border-right: solid $primary;
}
MetadataPanel {
    width: 50%;
}
```

When tree is hidden (`.tree-hidden` class on `Horizontal`):

```css
.tree-hidden FileListPanel {
    width: 35%;
}
.tree-hidden MetadataPanel {
    width: 65%;
}
```

**New bindings:**

```python
BINDINGS = [
    ("backslash", "toggle_tree", "Tree"),
    ("r", "recursive", "Recurse"),
    ("e", "export", "Export"),
    ("f", "filter", "Filter"),
    ("d", "directory", "Directory"),
    ("q", "quit", "Quit"),
]
```

**New action methods:**

- `action_toggle_tree()` — toggles `DirectoryTreePanel.display`; toggles `.tree-hidden` class on the `Horizontal` container.
- `action_recursive()` — flips `_recursive_mode`. If now `True`: calls `DirectoryTreePanel.expand_all()`, then `FileListPanel.scan(_selected_tree_dir, recursive=True)`. If now `False`: calls `FileListPanel.scan(_selected_tree_dir, recursive=False)`.

**Updated `on_mount()`:**

```python
def on_mount(self) -> None:
    self._selected_tree_dir = self._current_dir
    self.query_one(DirectoryTreePanel).load_directory(self._current_dir)
    self.query_one(FileListPanel).scan(self._current_dir)
    if self._config.warning:
        self.notify(self._config.warning, severity="warning")
```

**New handler:**

```python
def on_directory_tree_directory_selected(
    self, event: DirectoryTree.DirectorySelected
) -> None:
    self._selected_tree_dir = event.path
    self._current_file = None
    self._all_tags = []
    self.query_one(MetadataPanel).load_file({})
    self.query_one(FileListPanel).scan(event.path, recursive=self._recursive_mode)
```

**Updated `_on_directory_result()`:**

```python
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

**`_all_files` in export:** `ExportModal` currently receives `all_files=self._all_files`. This now comes from `FileListPanel._files` instead of being tracked separately in `app.py`. Add a `files` property to `FileListPanel` that returns `self._files`.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Directory selected in tree has no DICOMs | File list shows "No DICOM files found" (existing behaviour) |
| New directory selected while scan in progress | In-flight worker cancelled before new scan starts |
| `DirectoryTreePanel.expand_all()` called on large tree | Runs synchronously on the tree widget; Textual handles this via its own async rendering — no additional threading needed |
| Path typed in modal does not exist | Existing inline error in `DirectoryModal` (unchanged) |

---

## Testing

Existing tests (`test_dicom_reader.py`, `test_exporter.py`, `test_config.py`) are unaffected — `find_dicoms()` wrapper preserves the existing interface.

**New tests to add:**

| File | Coverage |
|---|---|
| `test_dicom_reader.py` | `iter_dicoms()` flat mode — yields DICOMs, skips non-DICOMs; `iter_dicoms()` recursive mode — descends subdirectories, yields DICOMs from all levels |
| `test_file_list.py` | `scan()` populates `_files`; cancels in-flight worker on second call |
