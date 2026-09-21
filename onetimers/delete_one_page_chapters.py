#!/usr/bin/env python3
"""Delete selected chapter archives and soft-delete their active database rows."""

import argparse
import configparser
import sqlite3
import sys
from pathlib import Path


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


def get_ids(values: list[str], ids_file: Path | None) -> list[int]:
    ids = []
    for value in values:
        try:
            ids.append(int(value))
        except ValueError as error:
            raise ValueError(f"Invalid chapter ID: {value}") from error

    if ids_file:
        for line in ids_file.read_text().splitlines():
            first_field = line.split("\t", 1)[0].strip()
            if not first_field or first_field == "id":
                continue
            try:
                ids.append(int(first_field))
            except ValueError as error:
                raise ValueError(f"Invalid chapter ID in {ids_file}: {first_field}") from error

    return list(dict.fromkeys(ids))


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", metavar="ID", nargs="*", help="Chapter database IDs to delete")
    parser.add_argument(
        "--ids-file",
        type=Path,
        help="Scanner output file containing tab-separated chapter rows",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=project_root / "settings.ini",
        help="Path to settings.ini (default: project settings.ini)",
    )
    parser.add_argument("--apply", action="store_true", help="Perform deletion; otherwise only print actions")
    args = parser.parse_args()

    try:
        ids = get_ids(args.ids, args.ids_file)
        database_path, quarantine_folder = get_paths(args.config)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    if not ids:
        parser.error("provide at least one ID or --ids-file")

    failures = 0
    with sqlite3.connect(database_path) as connection:
        for row_id in ids:
            row = connection.execute(
                "SELECT id, series, chapter, archive FROM manga WHERE id = ? AND active = 1",
                (row_id,),
            ).fetchone()
            if row is None:
                print(f"Skipping id {row_id}: not found or already inactive", file=sys.stderr)
                failures += 1
                continue

            _, series, chapter, archive = row
            archive_path = locate_archive(Path(archive), quarantine_folder)
            action = f"id {row_id}: {series} chapter {chapter} ({archive_path})"
            if not archive_path.is_file():
                print(f"Skipping {action}: archive file does not exist", file=sys.stderr)
                failures += 1
                continue

            if not args.apply:
                print(f"Would delete {action}")
                continue

            try:
                archive_path.unlink()
                connection.execute(
                    "UPDATE manga SET active = 0, last_active = datetime('now') WHERE id = ?",
                    (row_id,),
                )
                connection.commit()
                print(f"Deleted {action}")
            except OSError as error:
                print(f"Failed to delete {action}: {error}", file=sys.stderr)
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
