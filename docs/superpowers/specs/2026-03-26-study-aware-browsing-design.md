# Study-Aware DICOM Browsing — Design Spec

**Date:** 2026-03-26
**Status:** Approved

---

## Overview

Replace the current flat file-per-DICOM list with a study-aware browser. The app now shows one entry per DICOM study in the selected directory — where a study is either a subdirectory containing DICOM slices or a standalone `.dcm` file. Each entry displays inline patient and study metadata loaded in the background. This eliminates the problem of multi-file DICOM studies (often 500+ slices) flooding the list with identical-metadata entries, and makes it fast to identify which study belongs to which patient.

---

## Problem

Multi-file DICOMs are directories of 400–600 individual slice files, all sharing the same metadata. The current app lists every slice file individually, requiring the user to click into each file to see patient/study info. Navigating to a parent directory that contains multiple studies shows nothing (no `.dcm` files at the root level). The user must navigate into each subfolder separately.

The primary use case is quick identification: given 5–7 incoming DICOM studies with inscrutable folder names, determine which study belongs to which patient and what scan it is, before importing into dental planning software.

---

## Key Decisions

- **One entry per immediate child** of the selected directory: subdirectories that contain DICOMs become one study entry; standalone `.dcm` files become one study entry.
- **Deep nesting handled transparently**: the app always recursively scans within a study folder to find the first valid DICOM, regardless of nesting depth. No user action required.
- **Progressive background loading**: entries appear immediately with a "loading…" subtitle; metadata fills in as each representative DICOM is read.
- **`r` recursive key removed**: the old "show all files recursively" mode is no longer needed and is removed.

---

## Inline Summary Fields

Each study list entry shows a two-line layout:

```
📂 LEON LUIS-001-2026.03.07-13.41.09
   Leon Luis · Jaw and teeth · 3D CBCT Image · 2026-03-07 13:41
```

The subtitle line joins the following fields with ` · `, omitting any that are absent in the file:

| Field | Formatting |
|---|---|
| `PatientName` | `LAST^FIRST^…` → `First Last` |
| `StudyDescription` | raw string |
| `SeriesDescription` | raw string |
| `StudyDate` + `StudyTime` | `20260307` + `134109` → `2026-03-07 13:41` |

The metadata panel (right pane) continues to show raw DICOM values, unchanged.

---

## Changes by File

### `src/dicom_reader.py`

**New dataclass:**

```python
@dataclass
class DicomStudy:
    display_name: str    # folder name or .dcm filename shown in the list
    root_path: Path      # the directory or .dcm file (used for export labeling)
    representative: Path # first valid DICOM found inside (used for metadata loading)
    is_dir: bool         # True = multi-file study, False = single-file
```

**New functions:**

- `find_representative(path: Path) -> Path | None`
  - If `path` is a file: returns `path` if `is_dicom(path)`, else `None`.
  - If `path` is a directory: returns the first result from `iter_dicoms(path, recursive=True)`, or `None`.
  - Reads only 132 bytes per candidate file until a DICOM is found — fast even for deeply nested structures.

- `format_patient_name(value: str) -> str`
  - Splits on `^`. DICOM PersonName convention is `FAMILY^GIVEN^MIDDLE^PREFIX^SUFFIX`.
  - Returns `f"{parts[1].title()} {parts[0].title()}"` (given then family, title-cased).
  - Example: `"LEON^LUIS"` → `"Luis Leon"`.
  - Returns original string if the value has fewer than 2 `^`-separated components or if the result would be empty.

- `format_date(value: str) -> str`
  - `"20260307"` → `"2026-03-07"`. Returns original string if not 8 digits.

- `format_time(value: str) -> str`
  - `"134109"` or `"134109.123456"` → `"13:41"` (HH:MM only, for inline display). Returns original string if shorter than 4 chars.

- `build_inline_summary(tags: dict[str, str]) -> str`
  - Builds the subtitle line from `PatientName`, `StudyDescription`, `SeriesDescription`, `StudyDate`+`StudyTime`.
  - Joins non-empty parts with `" · "`.
  - PatientName is formatted via `format_patient_name`; date/time are formatted and combined into one part.

**Constant:**

```python
INLINE_TAGS: list[str] = [
    "PatientName", "StudyDescription", "SeriesDescription", "StudyDate", "StudyTime"
]
```

Used by the background worker to read only the needed fields via `filter_tags()`.

---

### `src/widgets/file_list.py` — `FileListPanel`

**List item structure:** Each `ListItem` contains two `Label` widgets:
- `.study-name` — folder/file icon + display name
- `.study-meta` — inline summary subtitle (initially `"loading…"`, updated when metadata arrives)

**State:**
- `_studies: list[DicomStudy]` — replaces `_files: list[Path]`

**`FileSelected` message:**

```python
class FileSelected(Message):
    def __init__(self, representative: Path, study_root: Path) -> None:
        super().__init__()
        self.representative = representative  # actual DICOM file for metadata panel
        self.study_root = study_root          # folder/file path for export labeling
```

**`scan(path: Path) -> None`** (signature simplified — `recursive` parameter removed):
1. Increments `_scan_id`, clears `_studies`, clears the `ListView`.
2. Shows `"Scanning… (0 found)"` status label.
3. Spawns a background thread that:
   a. Iterates `path.iterdir()` for immediate children.
   b. For each child, assigns a stable integer `candidate_id` (monotonically incrementing per scan). Calls `self.app.call_from_thread(self._on_candidate_found, candidate_id, child, scan_id)` to add a placeholder `ListItem` keyed by `candidate_id`.
   c. Calls `find_representative(child)` — returns `None` if child has no DICOMs.
   d. If `None`: calls `self.app.call_from_thread(self._on_candidate_no_dicom, candidate_id, scan_id)` to remove the placeholder item.
   e. If found: reads `INLINE_TAGS` via `filter_tags(load_tags(representative), INLINE_TAGS)`, builds summary via `build_inline_summary`, calls `self.app.call_from_thread(self._on_study_ready, candidate_id, study, summary, scan_id)` to update the placeholder's subtitle label.
   f. When done: calls `self.app.call_from_thread(self._on_scan_done, scan_id)`.

**State additions:** `_item_map: dict[int, ListItem]` — maps `candidate_id` to its `ListItem` so placeholder items can be updated or removed by ID without relying on list position (which shifts as items are removed).

**CSS additions:**

```css
FileListPanel .study-name {
    color: $text;
}
FileListPanel .study-meta {
    color: $text-muted;
    padding-left: 2;
    text-style: dim;
}
```

---

### `src/app.py`

**Removed:**
- `action_recursive` method
- `_recursive_mode` state
- `("r", "recursive", "Recurse")` binding

**Renamed:** `_current_file` → `_current_representative`

**Updated:**
- `on_file_list_panel_file_selected`: uses `event.representative` for `load_tags()` and metadata panel update.
- `action_export`: passes `self.query_one(FileListPanel).studies` (a `list[DicomStudy]`) to `ExportModal`.
- `on_mount` and `_on_directory_result`: call `FileListPanel.scan(path)` without the `recursive` argument.
- `on_directory_tree_directory_selected`: same — no `recursive` argument.

---

### `src/exporter.py`

`export_csv` and `export_json` updated to accept `list[DicomStudy]` instead of `list[Path]`:
- Row label uses `study.display_name` (the folder/file name the user sees in the list).
- Tags are read from `study.representative`.
- Interface change is internal — `ExportModal` is the only caller.

---

## What Is Not Changing

| Component | Status |
|---|---|
| `MetadataPanel` | Unchanged — still shows raw DICOM tags |
| `FilterModal` | Unchanged |
| `DirectoryModal` | Unchanged |
| `DirectoryTreePanel` | Unchanged |
| `Config` / `config.toml` | Unchanged |
| `is_dicom()`, `iter_dicoms()`, `load_tags()`, `filter_tags()` | Unchanged |

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Child directory has no DICOMs | Placeholder item is removed silently; not counted in "N found" |
| Representative DICOM has no inline tags | Subtitle shows empty string (no `·` separators) |
| Representative DICOM is unreadable | `load_tags()` returns `{}`; subtitle stays empty; item remains in list |
| Directory is empty | "No DICOM studies found" empty state, same as current |

---

## Testing

Existing tests for `is_dicom`, `iter_dicoms`, `load_tags`, `filter_tags`, `export_csv`, `export_json` continue to pass unchanged.

New tests:

| Test | Coverage |
|---|---|
| `test_dicom_reader.py` | `find_representative` — file path, directory path, nested directory, no DICOM found; `format_patient_name`, `format_date`, `format_time`; `build_inline_summary` with full fields, missing fields, empty dict |
| `test_exporter.py` | `export_csv` and `export_json` with `DicomStudy` list — display name used as row label, representative path read for tags |
