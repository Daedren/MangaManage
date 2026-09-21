#!/usr/bin/env python3
"""List active CBZ chapters created recently that contain exactly one image."""

import argparse
import configparser
import sqlite3
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path


IMAGE_SUFFIXES = {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def get_paths(config_path: Path) -> tuple[Path, Path]:
    config = configparser.ConfigParser()
    if not config.read(config_path):
        raise FileNotFoundError(f"Could not read configuration file: {config_path}")
    try:
        return (
            Path(config["database"]["sqlitelocation"]).expanduser(),
            Path(config["manga"]["quarantinefolder"]).expanduser(),
        )
    except KeyError as error:
        raise ValueError(
            "Configuration is missing [database] sqlitelocation or [manga] quarantinefolder"
        ) from error


def locate_archive(archive_path: Path, quarantine_folder: Path) -> Path:
    if archive_path.is_file():
        return archive_path
    return quarantine_folder / archive_path.parent.name / archive_path.name


def count_images(archive_path: Path) -> int:
    with zipfile.ZipFile(archive_path) as archive:
        return sum(
            1
            for entry in archive.infolist()
            if not entry.is_dir()
            and not Path(entry.filename).name.startswith(".")
            and Path(entry.filename).suffix.lower() in IMAGE_SUFFIXES
        )


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=project_root / "settings.ini",
        help="Path to settings.ini (default: project settings.ini)",
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Look back this many days (default: 30)"
    )
    args = parser.parse_args()

    if args.days < 1:
        parser.error("--days must be at least 1")

    try:
        database_path, quarantine_folder = get_paths(args.config)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    cutoff = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, series, chapter, creation_date, archive
            FROM manga
            WHERE active = 1 AND creation_date >= ?
            ORDER BY datetime(creation_date) DESC, id DESC
            """,
            (cutoff,),
        )

        print("id\tseries\tchapter\tcreation_date\tarchive")
        for row_id, series, chapter, creation_date, archive in rows:
            archive_path = locate_archive(Path(archive), quarantine_folder)
            try:
                page_count = count_images(archive_path)
            except (FileNotFoundError, PermissionError, zipfile.BadZipFile) as error:
                print(f"Skipping id {row_id} ({archive_path}): {error}", file=sys.stderr)
                continue

            if page_count == 1:
                print(f"{row_id}\t{series}\t{chapter}\t{creation_date}\t{archive}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
