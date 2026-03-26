from __future__ import annotations
import csv
import json
from datetime import datetime
from pathlib import Path

from .dicom_reader import load_tags, filter_tags


def default_output_path(ext: str) -> Path:
    return Path.cwd() / f"dicom_export_{datetime.now():%Y%m%d_%H%M%S}.{ext}"


def _build_record(path: Path, tags: list[str]) -> dict[str, str]:
    filtered = filter_tags(load_tags(path), tags)
    return {"file": path.name, **{tag: filtered.get(tag, "") for tag in tags}}


def export_csv(files: list[Path], tags: list[str], output: Path) -> None:
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file"] + tags, extrasaction="ignore")
        writer.writeheader()
        for path in files:
            writer.writerow(_build_record(path, tags))


def export_json(files: list[Path], tags: list[str], output: Path) -> None:
    records = [_build_record(path, tags) for path in files]
    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
