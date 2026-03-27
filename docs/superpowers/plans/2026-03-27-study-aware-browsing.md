# Study-Aware DICOM Browsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat per-file DICOM list with a study-aware browser that shows one entry per study (folder or single file), with inline patient/study metadata loaded progressively in the background.

**Architecture:** `dicom_reader.py` gains a `DicomStudy` dataclass, formatting helpers, and `find_representative()` for locating the first valid DICOM inside any folder regardless of nesting depth. `FileListPanel` is redesigned to scan immediate children of the selected directory and display two-line entries with background-loaded metadata. `exporter.py` and `ExportModal` are updated to work with `DicomStudy` lists instead of flat `Path` lists.

**Tech Stack:** Python 3.10+, pydicom, Textual, pytest, uv

---

## File Map

| File | Change |
|---|---|
| `src/dicom_reader.py` | Add `DicomStudy`, `INLINE_TAGS`, `format_patient_name`, `format_date`, `format_time`, `build_inline_summary`, `find_representative` |
| `src/exporter.py` | Update `export_csv`/`export_json` to accept `list[DicomStudy]`; update `_build_record` signature |
| `src/widgets/export_modal.py` | Update constructor/logic to use `DicomStudy`; rename "All files" label |
| `src/widgets/file_list.py` | Full redesign: two-line items, study-level scan, background worker with `_item_map` |
| `src/app.py` | Remove recursive mode; rename `_current_file`→`_current_study`; update event handlers |
| `tests/test_dicom_reader.py` | Add tests for new helpers and `find_representative` |
| `tests/test_exporter.py` | Update all calls from `list[Path]` to `list[DicomStudy]`; add display-name test |
| `tests/test_file_list.py` | Full rewrite for study-level assertions |

---

## Task 1: dicom_reader — DicomStudy dataclass and formatting helpers

**Files:**
- Modify: `src/dicom_reader.py`
- Test: `tests/test_dicom_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dicom_reader.py`:

```python
# --- DicomStudy, INLINE_TAGS, formatting helpers ---

from src.dicom_reader import (
    DicomStudy,
    INLINE_TAGS,
    format_patient_name,
    format_date,
    format_time,
    build_inline_summary,
)


def test_dicom_study_is_dataclass():
    study = DicomStudy(
        display_name="my_study",
        root_path=Path("/foo"),
        representative=Path("/foo/slice.dcm"),
        is_dir=True,
    )
    assert study.display_name == "my_study"
    assert study.representative == Path("/foo/slice.dcm")
    assert study.is_dir is True


def test_inline_tags_contains_required_fields():
    assert set(INLINE_TAGS) >= {
        "PatientName", "StudyDescription", "SeriesDescription",
        "StudyDate", "StudyTime",
    }


def test_format_patient_name_standard():
    assert format_patient_name("LEON^LUIS") == "Luis Leon"


def test_format_patient_name_middle_component_ignored():
    assert format_patient_name("DOE^JOHN^MIDDLE") == "John Doe"


def test_format_patient_name_single_component_returns_original():
    assert format_patient_name("SINGLETON") == "SINGLETON"


def test_format_patient_name_empty_given_returns_original():
    assert format_patient_name("FAMILY^") == "FAMILY^"


def test_format_date_standard():
    assert format_date("20260307") == "2026-03-07"


def test_format_date_short_returns_original():
    assert format_date("2026") == "2026"


def test_format_date_non_digits_returns_original():
    assert format_date("notadate") == "notadate"


def test_format_time_full():
    assert format_time("134109") == "13:41"


def test_format_time_with_fractional_seconds():
    assert format_time("134109.123456") == "13:41"


def test_format_time_too_short_returns_original():
    assert format_time("13") == "13"


def test_build_inline_summary_all_fields():
    tags = {
        "PatientName": "LEON^LUIS",
        "StudyDescription": "Jaw and teeth",
        "SeriesDescription": "3D CBCT Image",
        "StudyDate": "20260307",
        "StudyTime": "134109",
    }
    assert build_inline_summary(tags) == (
        "Luis Leon · Jaw and teeth · 3D CBCT Image · 2026-03-07 13:41"
    )


def test_build_inline_summary_no_series_description():
    tags = {
        "PatientName": "SCHEGAR^DAWN",
        "StudyDescription": "Denture scan #2",
        "StudyDate": "20260126",
    }
    assert build_inline_summary(tags) == "Dawn Schegar · Denture scan #2 · 2026-01-26"


def test_build_inline_summary_no_study_description_uses_series():
    tags = {
        "PatientName": "DAWSON^ROGER",
        "SeriesDescription": "Post-op CBCT",
        "StudyDate": "20260310",
        "StudyTime": "141758",
    }
    assert build_inline_summary(tags) == "Roger Dawson · Post-op CBCT · 2026-03-10 14:17"


def test_build_inline_summary_empty_tags_returns_empty_string():
    assert build_inline_summary({}) == ""
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --extra dev pytest tests/test_dicom_reader.py -k "dicom_study or inline_tags or format_patient or format_date or format_time or build_inline" -v
```

Expected: multiple `ImportError` or `AttributeError` failures — the symbols don't exist yet.

- [ ] **Step 3: Add the dataclass, constant, and helpers to `src/dicom_reader.py`**

Insert `from dataclasses import dataclass` into the stdlib imports block (after `from functools import lru_cache`). Then insert the following block **directly before the `_DICOM_MAGIC` line**:

```python
@dataclass
class DicomStudy:
    display_name: str    # folder name or .dcm filename shown in the list
    root_path: Path      # the directory or .dcm file (for export labeling)
    representative: Path # first valid DICOM found inside (for metadata loading)
    is_dir: bool         # True = multi-file study, False = single-file


INLINE_TAGS: list[str] = [
    "PatientName", "StudyDescription", "SeriesDescription", "StudyDate", "StudyTime"
]


def format_patient_name(value: str) -> str:
    """Convert DICOM PersonName 'FAMILY^GIVEN^...' to 'Given Family' (title-cased)."""
    parts = value.split("^")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return value
    return f"{parts[1].title()} {parts[0].title()}"


def format_date(value: str) -> str:
    """Convert 'YYYYMMDD' to 'YYYY-MM-DD'. Returns original string on bad input."""
    if len(value) != 8 or not value.isdigit():
        return value
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def format_time(value: str) -> str:
    """Convert 'HHMMSS[.frac]' to 'HH:MM'. Returns original string if too short."""
    if len(value) < 4:
        return value
    base = value.split(".")[0]
    return f"{base[:2]}:{base[2:4]}"


def build_inline_summary(tags: dict[str, str]) -> str:
    """Build the subtitle line for a study list entry from pre-filtered INLINE_TAGS."""
    parts: list[str] = []
    if pn := tags.get("PatientName"):
        parts.append(format_patient_name(pn))
    if sd := tags.get("StudyDescription"):
        parts.append(sd)
    if srd := tags.get("SeriesDescription"):
        parts.append(srd)
    date_str = format_date(tags["StudyDate"]) if "StudyDate" in tags else ""
    time_str = format_time(tags["StudyTime"]) if "StudyTime" in tags else ""
    dt = f"{date_str} {time_str}".strip()
    if dt:
        parts.append(dt)
    return " · ".join(parts)
```

- [ ] **Step 4: Run tests to confirm they pass**

```
uv run --extra dev pytest tests/test_dicom_reader.py -k "dicom_study or inline_tags or format_patient or format_date or format_time or build_inline" -v
```

Expected: all new tests PASS, existing tests still PASS.

- [ ] **Step 5: Run the full test suite to confirm nothing is broken**

```
uv run --extra dev pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dicom_reader.py tests/test_dicom_reader.py
git commit -m "feat: add DicomStudy dataclass and formatting helpers to dicom_reader"
```

---

## Task 2: dicom_reader — find_representative

**Files:**
- Modify: `src/dicom_reader.py`
- Test: `tests/test_dicom_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dicom_reader.py`:

```python
# --- find_representative ---

from src.dicom_reader import find_representative


def test_find_representative_dicom_file_returns_itself(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    assert find_representative(p) == p


def test_find_representative_non_dicom_file_returns_none(tmp_path):
    p = tmp_path / "readme.txt"
    p.write_text("not a dicom")
    assert find_representative(p) is None


def test_find_representative_flat_directory(tmp_path):
    study_dir = tmp_path / "study"
    study_dir.mkdir()
    p = make_minimal_dicom(study_dir / "Slice0001")
    assert find_representative(study_dir) == p


def test_find_representative_nested_directory(tmp_path):
    study_dir = tmp_path / "study"
    deep = study_dir / "a" / "b" / "c"
    deep.mkdir(parents=True)
    p = make_minimal_dicom(deep / "00001DCM")
    result = find_representative(study_dir)
    assert result == p


def test_find_representative_empty_directory_returns_none(tmp_path):
    study_dir = tmp_path / "study"
    study_dir.mkdir()
    assert find_representative(study_dir) is None


def test_find_representative_directory_no_dicoms_returns_none(tmp_path):
    study_dir = tmp_path / "study"
    study_dir.mkdir()
    (study_dir / "readme.txt").write_text("not a dicom")
    assert find_representative(study_dir) is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --extra dev pytest tests/test_dicom_reader.py -k "find_representative" -v
```

Expected: `ImportError` — `find_representative` not defined yet.

- [ ] **Step 3: Add `find_representative` to `src/dicom_reader.py`**

Add after `find_dicoms`:

```python
def find_representative(path: Path) -> Path | None:
    """Return the first valid DICOM inside path (recursing into dirs), or None.

    If path is a file, returns it directly if it passes is_dicom(), else None.
    If path is a directory, returns the first result from iter_dicoms(recursive=True).
    """
    if path.is_file():
        return path if is_dicom(path) else None
    if path.is_dir():
        return next(iter_dicoms(path, recursive=True), None)
    return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```
uv run --extra dev pytest tests/test_dicom_reader.py -k "find_representative" -v
```

Expected: all 6 new tests PASS.

- [ ] **Step 5: Run the full test suite**

```
uv run --extra dev pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dicom_reader.py tests/test_dicom_reader.py
git commit -m "feat: add find_representative to dicom_reader"
```

---

## Task 3: exporter — accept list[DicomStudy]

**Files:**
- Modify: `src/exporter.py`
- Modify: `src/widgets/export_modal.py`
- Test: `tests/test_exporter.py`

- [ ] **Step 1: Update `tests/test_exporter.py`**

Replace the entire file with the following (all existing tests preserved but updated to use `DicomStudy`; one new test added):

```python
import csv
import json
import re
from pathlib import Path

import pytest
from tests.conftest import make_minimal_dicom
from src.dicom_reader import DicomStudy
from src.exporter import export_csv, export_json, default_output_path


TAGS = ["PatientName", "Modality", "StudyDate"]


def _make_study(path: Path) -> DicomStudy:
    """Wrap a single DICOM file path as a DicomStudy for testing."""
    return DicomStudy(
        display_name=path.name,
        root_path=path,
        representative=path,
        is_dir=False,
    )


def test_export_csv_creates_file(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], TAGS, out)
    assert out.exists()


def test_export_csv_header_row(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], TAGS, out)
    with open(out, newline="") as f:
        reader = csv.DictReader(f)
        assert set(reader.fieldnames) == {"file", "PatientName", "Modality", "StudyDate"}


def test_export_csv_data_row(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["file"] == "scan.dcm"
    assert rows[0]["PatientName"] == "Test^Patient"
    assert rows[0]["Modality"] == "CT"


def test_export_csv_missing_tag_is_empty(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], ["PatientName", "NonExistentTag"], out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["NonExistentTag"] == ""


def test_export_csv_multiple_studies(tmp_path):
    files = [make_minimal_dicom(tmp_path / f"scan{i}.dcm") for i in range(3)]
    out = tmp_path / "out.csv"
    export_csv([_make_study(p) for p in files], TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3


def test_export_csv_uses_display_name_as_file_column(tmp_path):
    p = make_minimal_dicom(tmp_path / "slice001")
    study = DicomStudy(
        display_name="PCH0053_20260203_125047",
        root_path=tmp_path / "PCH0053_20260203_125047",
        representative=p,
        is_dir=True,
    )
    out = tmp_path / "out.csv"
    export_csv([study], TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["file"] == "PCH0053_20260203_125047"


def test_export_json_creates_file(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([_make_study(p)], TAGS, out)
    assert out.exists()


def test_export_json_structure(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([_make_study(p)], TAGS, out)
    records = json.loads(out.read_text())
    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["file"] == "scan.dcm"
    assert records[0]["PatientName"] == "Test^Patient"
    assert records[0]["Modality"] == "CT"


def test_export_json_missing_tag_is_empty_string(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([_make_study(p)], ["PatientName", "NonExistentTag"], out)
    records = json.loads(out.read_text())
    assert records[0]["NonExistentTag"] == ""


def test_export_json_uses_display_name_as_file_column(tmp_path):
    p = make_minimal_dicom(tmp_path / "slice001")
    study = DicomStudy(
        display_name="LEON LUIS-001-2026.03.07",
        root_path=tmp_path / "LEON LUIS-001",
        representative=p,
        is_dir=True,
    )
    out = tmp_path / "out.json"
    export_json([study], TAGS, out)
    records = json.loads(out.read_text())
    assert records[0]["file"] == "LEON LUIS-001-2026.03.07"


def test_default_output_path_csv():
    path = default_output_path("csv")
    assert path.suffix == ".csv"
    assert re.match(r"dicom_export_\d{8}_\d{6}\.csv", path.name)


def test_default_output_path_json():
    path = default_output_path("json")
    assert path.suffix == ".json"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --extra dev pytest tests/test_exporter.py -v
```

Expected: `TypeError` on calls that now pass `list[DicomStudy]` to functions still expecting `list[Path]`.

- [ ] **Step 3: Update `src/exporter.py`**

Replace the entire file:

```python
from __future__ import annotations
import csv
import json
from datetime import datetime
from pathlib import Path

from .dicom_reader import DicomStudy, load_tags, filter_tags


def default_output_path(ext: str) -> Path:
    return Path.cwd() / f"dicom_export_{datetime.now():%Y%m%d_%H%M%S}.{ext}"


def _build_record(label: str, path: Path, tags: list[str]) -> dict[str, str]:
    filtered = filter_tags(load_tags(path), tags)
    return {"file": label, **{tag: filtered.get(tag, "") for tag in tags}}


def export_csv(studies: list[DicomStudy], tags: list[str], output: Path) -> None:
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file"] + tags, extrasaction="ignore")
        writer.writeheader()
        for study in studies:
            writer.writerow(_build_record(study.display_name, study.representative, tags))


def export_json(studies: list[DicomStudy], tags: list[str], output: Path) -> None:
    records = [
        _build_record(study.display_name, study.representative, tags)
        for study in studies
    ]
    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
```

- [ ] **Step 4: Run tests to confirm they pass**

```
uv run --extra dev pytest tests/test_exporter.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Update `src/widgets/export_modal.py`**

Replace the entire file:

```python
from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from ..dicom_reader import DicomStudy
from ..exporter import default_output_path, export_csv, export_json
from ._base_modal import EscapeModal


class ExportModal(EscapeModal[None]):
    """Modal for configuring and triggering a metadata export."""

    DEFAULT_CSS = EscapeModal.DEFAULT_CSS + """
    ExportModal > Vertical {
        width: 60;
        height: auto;
    }
    """

    def __init__(
        self,
        all_studies: list[DicomStudy],
        current_study: DicomStudy | None,
        active_tags: list[str],
    ) -> None:
        super().__init__()
        self._all_studies = all_studies
        self._current_study = current_study
        self._active_tags = active_tags

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Export scope:")
            with RadioSet(id="scope"):
                yield RadioButton("Current study", value=True, id="scope-current")
                yield RadioButton("All studies in directory", id="scope-all")
            yield Label("Format:")
            with RadioSet(id="format"):
                yield RadioButton("CSV", value=True, id="fmt-csv")
                yield RadioButton("JSON", id="fmt-json")
            yield Label("Output path:")
            yield Input(
                value=str(default_output_path("csv")),
                id="output-path",
            )
            yield Label("", id="error-label", classes="error")
            yield Button("Export", variant="primary", id="confirm")
            yield Button("Cancel", id="cancel")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "format":
            ext = "json" if event.index == 1 else "csv"
            current = self.query_one("#output-path", Input).value
            self.query_one("#output-path", Input).value = str(
                Path(current).with_suffix(f".{ext}")
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "confirm":
            self._do_export()

    def _do_export(self) -> None:
        scope_radio = self.query_one("#scope", RadioSet)
        fmt_radio = self.query_one("#format", RadioSet)
        output = Path(self.query_one("#output-path", Input).value.strip())

        use_all = scope_radio.pressed_index == 1
        use_json = fmt_radio.pressed_index == 1

        studies = self._all_studies if use_all else (
            [self._current_study] if self._current_study else []
        )
        if not studies:
            self.query_one("#error-label", Label).update("No study selected.")
            return

        try:
            if use_json:
                export_json(studies, self._active_tags, output)
            else:
                export_csv(studies, self._active_tags, output)
            self.app.notify(f"Export saved to {output}")
            self.dismiss(None)
        except Exception as exc:
            self.query_one("#error-label", Label).update(f"Export failed: {exc}")
```

- [ ] **Step 6: Run the full test suite**

```
uv run --extra dev pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/exporter.py src/widgets/export_modal.py tests/test_exporter.py
git commit -m "feat: update exporter and ExportModal to work with DicomStudy list"
```

---

## Task 4: FileListPanel — study-aware redesign

**Files:**
- Modify: `src/widgets/file_list.py`
- Modify: `tests/test_file_list.py`

- [ ] **Step 1: Replace `tests/test_file_list.py`**

Replace the entire file:

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
async def test_scan_shows_one_entry_per_folder_study(tmp_path):
    study_dir = tmp_path / "study1"
    study_dir.mkdir()
    make_minimal_dicom(study_dir / "Slice0001")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 1
        assert panel.studies[0].display_name == "study1"
        assert panel.studies[0].is_dir is True


@pytest.mark.asyncio
async def test_scan_shows_one_entry_per_standalone_dcm(tmp_path):
    make_minimal_dicom(tmp_path / "export.dcm")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 1
        assert panel.studies[0].display_name == "export.dcm"
        assert panel.studies[0].is_dir is False


@pytest.mark.asyncio
async def test_scan_handles_deeply_nested_study(tmp_path):
    study_dir = tmp_path / "study1"
    deep = study_dir / "a" / "b" / "c"
    deep.mkdir(parents=True)
    make_minimal_dicom(deep / "00001DCM")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 1
        assert panel.studies[0].display_name == "study1"


@pytest.mark.asyncio
async def test_scan_skips_non_dicom_folders(tmp_path):
    not_a_study = tmp_path / "not_a_study"
    not_a_study.mkdir()
    (not_a_study / "readme.txt").write_text("hello")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert panel.studies == []


@pytest.mark.asyncio
async def test_scan_empty_directory(tmp_path):
    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert panel.studies == []


@pytest.mark.asyncio
async def test_scan_mixed_folders_and_files(tmp_path):
    # One folder study + one standalone file study
    folder_study = tmp_path / "folder_study"
    folder_study.mkdir()
    make_minimal_dicom(folder_study / "Slice0001")
    make_minimal_dicom(tmp_path / "standalone.dcm")
    # One non-DICOM folder (should be excluded)
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 2
        names = {s.display_name for s in panel.studies}
        assert names == {"folder_study", "standalone.dcm"}


@pytest.mark.asyncio
async def test_scan_second_call_supersedes_first(tmp_path):
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    study_a = dir1 / "study_a"
    study_a.mkdir()
    make_minimal_dicom(study_a / "Slice0001")
    study_b = dir2 / "study_b"
    study_b.mkdir()
    make_minimal_dicom(study_b / "Slice0001")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(dir1)
        panel.scan(dir2)
        await pilot.pause(1.0)
        names = {s.display_name for s in panel.studies}
        assert "study_b" in names
        assert "study_a" not in names
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --extra dev pytest tests/test_file_list.py -v
```

Expected: `AttributeError` — `panel.studies` doesn't exist yet; old `panel.files` still present.

- [ ] **Step 3: Replace `src/widgets/file_list.py`**

Replace the entire file:

```python
from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..dicom_reader import (
    DicomStudy,
    INLINE_TAGS,
    build_inline_summary,
    filter_tags,
    find_representative,
    load_tags,
)


class FileListPanel(Widget):
    """Middle panel — scrollable list of DICOM studies in the selected directory."""

    DEFAULT_CSS = """
    FileListPanel #scan-status {
        display: none;
        color: $warning;
        padding: 0 1;
    }
    FileListPanel .study-name {
        color: $text;
    }
    FileListPanel .study-meta {
        color: $text-muted;
        padding-left: 2;
        text-style: dim;
    }
    """

    class FileSelected(Message):
        """Posted when the user highlights a different study."""

        def __init__(self, study: DicomStudy) -> None:
            super().__init__()
            self.study = study

    def __init__(self) -> None:
        super().__init__()
        self._studies: list[DicomStudy] = []
        self._scan_id: int = 0
        self._item_map: dict[int, ListItem] = {}

    def compose(self) -> ComposeResult:
        yield Label("", id="scan-status")
        yield ListView()

    @property
    def studies(self) -> list[DicomStudy]:
        """Current list of confirmed DICOM studies."""
        return list(self._studies)

    def scan(self, path: Path) -> None:
        """Start a background scan of immediate children of `path`.

        Each immediate child that contains at least one DICOM file (anywhere
        in its subtree) becomes one study entry. Supersedes any in-flight scan.
        """
        self._scan_id += 1
        current_id = self._scan_id
        self._studies = []
        self._item_map = {}

        list_view = self.query_one(ListView)
        list_view.clear()

        status = self.query_one("#scan-status", Label)
        status.update("Scanning\u2026 (0 found)")
        status.display = True

        def _do_scan() -> None:
            candidate_id = 0
            try:
                children = sorted(path.iterdir(), key=lambda p: p.name.lower())
            except OSError:
                self.app.call_from_thread(self._on_scan_done, current_id)
                return

            for child in children:
                cid = candidate_id
                candidate_id += 1
                self.app.call_from_thread(
                    self._on_candidate_found, cid, child, current_id
                )
                representative = find_representative(child)
                if representative is None:
                    self.app.call_from_thread(
                        self._on_candidate_no_dicom, cid, current_id
                    )
                    continue
                study = DicomStudy(
                    display_name=child.name,
                    root_path=child,
                    representative=representative,
                    is_dir=child.is_dir(),
                )
                inline_tags = filter_tags(load_tags(representative), INLINE_TAGS)
                summary = build_inline_summary(inline_tags)
                self.app.call_from_thread(
                    self._on_study_ready, cid, study, summary, current_id
                )
            self.app.call_from_thread(self._on_scan_done, current_id)

        self.run_worker(_do_scan, thread=True, exit_on_error=False)

    def _on_candidate_found(
        self, candidate_id: int, child: Path, scan_id: int
    ) -> None:
        if scan_id != self._scan_id:
            return
        icon = "\U0001f4c2" if child.is_dir() else "\U0001f4c4"
        item = ListItem(
            Label(f"{icon} {child.name}", classes="study-name"),
            Label("loading\u2026", classes="study-meta"),
        )
        self._item_map[candidate_id] = item
        self.query_one(ListView).append(item)
        self.query_one("#scan-status", Label).update(
            f"Scanning\u2026 ({len(self._item_map)} found)"
        )

    def _on_candidate_no_dicom(self, candidate_id: int, scan_id: int) -> None:
        if scan_id != self._scan_id:
            return
        item = self._item_map.pop(candidate_id, None)
        if item is not None:
            item.remove()

    def _on_study_ready(
        self,
        candidate_id: int,
        study: DicomStudy,
        summary: str,
        scan_id: int,
    ) -> None:
        if scan_id != self._scan_id:
            return
        self._studies.append(study)
        item = self._item_map.get(candidate_id)
        if item is not None:
            item.query_one(".study-meta", Label).update(summary)

    def _on_scan_done(self, scan_id: int) -> None:
        if scan_id != self._scan_id:
            return
        status = self.query_one("#scan-status", Label)
        status.display = False
        if not self._studies:
            self.query_one(ListView).append(
                ListItem(Label("No DICOM studies found"))
            )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._studies):
            self.post_message(self.FileSelected(self._studies[idx]))
```

- [ ] **Step 4: Run tests to confirm they pass**

```
uv run --extra dev pytest tests/test_file_list.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Run the full test suite**

```
uv run --extra dev pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/widgets/file_list.py tests/test_file_list.py
git commit -m "feat: redesign FileListPanel as study-aware browser with two-line entries"
```

---

## Task 5: app.py — remove recursive mode, update event handlers

**Files:**
- Modify: `src/app.py`

No new tests — changes are mechanical wiring updates covered by the existing and updated widget tests. Manual smoke-test with `uv run python -m src samples/` at the end.

- [ ] **Step 1: Replace `src/app.py`**

Replace the entire file:

```python
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
```

- [ ] **Step 2: Run the full test suite**

```
uv run --extra dev pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Smoke-test the app manually**

```
uv run python -m src samples/
```

Verify:
- Navigating to `samples/` in the directory tree shows 7 study entries (5 folders + 2 .dcm files)
- Each entry shows a two-line format with name and metadata subtitle
- Clicking/highlighting an entry loads full metadata in the right panel
- `[E]` export opens the modal with "Current study" / "All studies" options
- `[F]` filter still works
- `[D]` directory change still works
- The `[r]` key binding is gone from the footer

- [ ] **Step 4: Commit**

```bash
git add src/app.py
git commit -m "feat: update app to use study-aware FileListPanel; remove recursive mode"
```
