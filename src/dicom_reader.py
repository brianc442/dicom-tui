from __future__ import annotations
from functools import lru_cache
from pathlib import Path

import pydicom
import pydicom.multival
import pydicom.sequence
from pydicom.errors import InvalidDicomError
from pydicom.datadict import keyword_for_tag, tag_for_keyword
from pydicom.tag import Tag

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


def find_dicoms(directory: Path) -> list[Path]:
    """Return all DICOM files in directory (non-recursive), sorted by name."""
    return sorted(
        (p for p in directory.iterdir() if is_dicom(p)),
        key=lambda p: p.name,
    )


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
