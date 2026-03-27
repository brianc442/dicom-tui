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
