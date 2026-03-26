# DICOM Metadata Extractor

A terminal UI for browsing and exporting DICOM file metadata.

## Install

```bash
uv sync
```

## Usage

```bash
uv run dicom-tui /path/to/dicoms
uv run dicom-tui --config ~/.dicom-tui/config.toml /path/to/dicoms
```

## Key Bindings

| Key | Action |
|-----|--------|
| ↑/↓ | Navigate file list |
| E | Export metadata (CSV or JSON) |
| F | Filter visible tags |
| D | Change directory |
| Q | Quit |

## Configuration

Create `~/.dicom-tui/config.toml` (or a local `config.toml`) to control which tags are displayed:

```toml
[tags]
include = [
  "PatientName",
  "PatientID",
  "Modality",
  "StudyDate",
]
```

Tag entries can be keyword names (`"PatientName"`) or tag IDs (`"(0010,0010)"`).

## Dev

```bash
uv run --extra dev pytest tests/ -v
```
