from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

DEFAULT_TAGS: list[str] = [
    "PatientName",
    "PatientID",
    "Modality",
    "StudyDate",
    "StudyDescription",
    "SeriesDescription",
    "SOPInstanceUID",
    "Rows",
    "Columns",
    "BitsAllocated",
]


@dataclass
class Config:
    include: list[str]
    source_path: Path | None
    warning: str | None = None


def _config_candidates(explicit: Path | None) -> list[Path]:
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.append(Path.cwd() / "config.toml")
    candidates.append(Path.home() / ".dicom-tui" / "config.toml")
    return candidates


def load_config(path: Path | None = None) -> Config:
    for candidate in _config_candidates(path):
        try:
            with open(candidate, "rb") as f:
                data = tomllib.load(f)
            include = data.get("tags", {}).get("include", DEFAULT_TAGS[:])
            return Config(include=include, source_path=candidate)
        except FileNotFoundError:
            continue
        except tomllib.TOMLDecodeError as e:
            return Config(
                include=DEFAULT_TAGS[:],
                source_path=None,
                warning=f"Config error in {candidate}: {e}. Using defaults.",
            )
    return Config(include=DEFAULT_TAGS[:], source_path=None)


def save_config(path: Path, include: list[str]) -> None:
    existing: dict = {}
    try:
        with open(path, "rb") as f:
            existing = tomllib.load(f)
    except FileNotFoundError:
        pass
    existing.setdefault("tags", {})["include"] = include
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(existing, f)
