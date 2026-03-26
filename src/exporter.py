from __future__ import annotations
import csv
import json
from datetime import datetime
from pathlib import Path

from .dicom_reader import load_tags, filter_tags


def default_output_path(ext: str) -> Path:
    return Path.cwd() / f"dicom_export_{datetime.now():%Y%m%d_%H%M%S}.{ext}"


def export_csv(files: list[Path], tags: list[str], output: Path) -> None:
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file"] + tags, extrasaction="ignore")
        writer.writeheader()
        for path in files:
            all_tags = load_tags(path)
            filtered = filter_tags(all_tags, tags)
            row = {"file": path.name}
            for tag in tags:
                row[tag] = filtered.get(tag, "")
            writer.writerow(row)


def export_json(files: list[Path], tags: list[str], output: Path) -> None:
    records = []
    for path in files:
        all_tags = load_tags(path)
        filtered = filter_tags(all_tags, tags)
        record = {"file": path.name}
        for tag in tags:
            record[tag] = filtered.get(tag, "")
        records.append(record)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
