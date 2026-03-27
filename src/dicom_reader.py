from __future__ import annotations
import os
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pydicom
import pydicom.multival
import pydicom.sequence
from pydicom.errors import InvalidDicomError
from pydicom.datadict import keyword_for_tag, tag_for_keyword
from pydicom.tag import Tag

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


_DICOM_MAGIC = b"DICM"
_MAGIC_OFFSET = 128


def is_dicom(path: Path) -> bool:
    """Return True if path is a file with the DICOM magic bytes at offset 128."""
    if not path.is_file():
        return False
    try:
        with open(path, "rb") as f:
            f.seek(_MAGIC_OFFSET)
            return f.read(4) == _DICOM_MAGIC
    except OSError:
        return False


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


def _serialize_value(value) -> str:
    if isinstance(value, bytes):
        return f"<binary: {len(value)} bytes>"
    if isinstance(value, pydicom.sequence.Sequence):
        return f"<Sequence: {len(value)} items>"
    if isinstance(value, pydicom.multival.MultiValue):
        return " \\ ".join(str(v) for v in value)
    return str(value)


def load_tags(path: Path) -> dict[str, str]:
    """Load all tags from a DICOM file. Returns {} on invalid or unreadable file."""
    try:
        ds = pydicom.dcmread(str(path), stop_before_pixels=True)
    except (InvalidDicomError, OSError):
        return {}
    return {
        elem.keyword: _serialize_value(elem.value)
        for elem in ds
        if elem.keyword  # skip tags without a keyword (private tags, etc.)
    }


def _resolve_to_keyword(tag_ref: str) -> str | None:
    """Convert a tag ID string '(GGGG,EEEE)' or keyword to a keyword."""
    if tag_ref.startswith("("):
        try:
            clean = tag_ref.strip("()").replace(",", "")
            tag = Tag(int(clean[:4], 16), int(clean[4:], 16))
            kw = keyword_for_tag(tag)
            return kw if kw else None
        except (ValueError, IndexError):
            return None
    return tag_ref


def filter_tags(tags: dict[str, str], include: list[str]) -> dict[str, str]:
    """Return the subset of tags matching the include list (keywords or tag IDs)."""
    result: dict[str, str] = {}
    for ref in include:
        kw = _resolve_to_keyword(ref)
        if kw and kw in tags:
            result[kw] = tags[kw]
    return result


@lru_cache(maxsize=512)
def get_tag_id(keyword: str) -> str:
    """Return the '(gggg,eeee)' string for a DICOM keyword, or '' if unknown."""
    tag_int = tag_for_keyword(keyword)
    if tag_int is not None:
        t = Tag(tag_int)
        return f"({t.group:04x},{t.element:04x})"
    return ""
