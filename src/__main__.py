from __future__ import annotations
import argparse
from pathlib import Path

from .app import DicomTuiApp
from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dicom-tui",
        description="Interactive DICOM metadata browser and exporter.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        type=Path,
        help="Directory containing DICOM files (default: current directory)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to config.toml (overrides default lookup chain)",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    DicomTuiApp(directory=args.directory, config=config).run()


if __name__ == "__main__":
    main()
