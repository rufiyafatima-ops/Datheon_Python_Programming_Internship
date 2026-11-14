#!/usr/bin/env python3
"""
Automated File Organizer & Cleanup Utility
------------------------------------------
Sorts the files in a cluttered folder (e.g. Downloads) into category
sub-folders (Documents, Images, Videos, Audio, Archives, Code, Others) based on
each file's extension.

Safety features:
  * never overwrites: if a file with the same name already exists in the target
    folder, the moved file is renamed  report.pdf -> report (1).pdf
  * handles PermissionError, FileExistsError and other OS errors per file, so
    one bad file never stops the run
  * skips sub-folders, hidden files, unfinished downloads (.crdownload, .part,
    .tmp) and this script itself
  * --dry-run previews what would happen without moving anything
  * asks for confirmation before moving (use --yes to skip the question)
  * writes a log file (organizer.log) next to the script

Usage:
    python organizer.py                      # organizes your Downloads folder (asks first)
    python organizer.py "C:\\Users\\me\\Desktop"
    python organizer.py ~/Downloads --dry-run
    python organizer.py ~/Downloads --yes
"""

import argparse
import logging
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
LOG_FILE = SCRIPT_PATH.with_name("organizer.log")

# Category -> file extensions
CATEGORIES = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx",
                  ".ppt", ".pptx", ".csv", ".md", ".epub"},
    "Images":    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff",
                  ".ico", ".heic"},
    "Videos":    {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm"},
    "Audio":     {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Code":      {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h",
                  ".cs", ".php", ".json", ".xml", ".sql", ".sh", ".ipynb"},
}
OTHER_CATEGORY = "Others"

# Extension -> category lookup dictionary, e.g. {'.pdf': 'Documents', '.jpg': 'Images'}
EXTENSION_MAP = {ext: category for category, exts in CATEGORIES.items() for ext in exts}

# Files we never touch
SKIP_SUFFIXES = {".crdownload", ".part", ".tmp", ".download", ".partial"}


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def setup_logging():
    logger = logging.getLogger("organizer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
        logger.addHandler(file_handler)
    except OSError as err:
        print(f"[warning] Could not create log file: {err}")
    return logger


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def categorize(filename):
    """Return the category folder name for a file, based on its extension."""
    return EXTENSION_MAP.get(Path(filename).suffix.lower(), OTHER_CATEGORY)


def unique_destination(destination):
    """If 'destination' exists, return 'name (1).ext', 'name (2).ext', ... instead."""
    if not destination.exists():
        return destination
    counter = 1
    while True:
        candidate = destination.with_name(f"{destination.stem} ({counter}){destination.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def should_skip(entry):
    """Return a reason string if the entry must not be moved, otherwise None."""
    if entry.is_dir(follow_symlinks=False):
        return "folder - left untouched"
    if not entry.is_file(follow_symlinks=False):
        return "not a regular file"
    if entry.name.startswith("."):
        return "hidden file"
    if Path(entry.path).suffix.lower() in SKIP_SUFFIXES:
        return "unfinished download"
    if Path(entry.path).resolve() in (SCRIPT_PATH, LOG_FILE):
        return "organizer's own file"
    return None


def is_unsafe_folder(folder):
    """Refuse to run on a drive root or the home directory itself."""
    return folder == Path(folder.anchor) or folder == Path.home()


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #
def organize(folder, dry_run, logger):
    stats = {"scanned": 0, "moved": 0, "skipped": 0, "failed": 0, "renamed": 0}
    per_category = Counter()
    action = "Would move" if dry_run else "Moved"

    try:
        with os.scandir(folder) as iterator:
            entries = list(iterator)       # snapshot first: we change the folder while working
    except PermissionError:
        logger.error(f"Permission denied: cannot read folder '{folder}'")
        return stats, per_category
    except OSError as err:
        logger.error(f"Cannot read folder '{folder}': {err}")
        return stats, per_category

    for entry in sorted(entries, key=lambda e: e.name.lower()):
        stats["scanned"] += 1
        reason = should_skip(entry)
        if reason:
            stats["skipped"] += 1
            logger.info(f"SKIPPED  {entry.name}  ({reason})")
            continue

        category = categorize(entry.name)
        target_dir = folder / category
        source = Path(entry.path)

        try:
            if not dry_run:
                target_dir.mkdir(exist_ok=True)
            destination = unique_destination(target_dir / entry.name)
            was_renamed = destination.name != entry.name

            if dry_run:
                logger.info(f"{action}  {entry.name}  ->  {category}/{destination.name}")
            else:
                try:
                    shutil.move(str(source), str(destination))
                except FileExistsError:
                    # Another file appeared with that name a moment ago: pick a new name
                    destination = unique_destination(target_dir / entry.name)
                    was_renamed = True
                    shutil.move(str(source), str(destination))
                logger.info(f"{action}  {entry.name}  ->  {category}/{destination.name}"
                            + ("  (renamed: name already existed)" if was_renamed else ""))

            stats["moved"] += 1
            per_category[category] += 1
            if was_renamed:
                stats["renamed"] += 1

        except PermissionError:
            stats["failed"] += 1
            logger.error(f"FAILED   {entry.name}  (permission denied - file may be open or protected)")
        except FileExistsError:
            stats["failed"] += 1
            logger.error(f"FAILED   {entry.name}  (a file with that name already exists)")
        except OSError as err:
            stats["failed"] += 1
            logger.error(f"FAILED   {entry.name}  ({err})")

    return stats, per_category


def print_summary(folder, stats, per_category, dry_run, seconds):
    title = "DRY RUN SUMMARY (nothing was moved)" if dry_run else "EXECUTION SUMMARY"
    lines = [
        "",
        "=" * 52,
        f"  {title}",
        "=" * 52,
        f"  Folder             : {folder}",
        f"  Items scanned      : {stats['scanned']}",
        f"  {'Files to move' if dry_run else 'Files relocated':<19}: {stats['moved']}",
        f"  Renamed (collision): {stats['renamed']}",
        f"  Skipped            : {stats['skipped']}",
        f"  Failed             : {stats['failed']}",
        f"  Time taken         : {seconds:.2f}s",
    ]
    if per_category:
        lines.append("-" * 52)
        lines.append("  Files per category:")
        for category, count in per_category.most_common():
            lines.append(f"    {category:<12} {count}")
    lines.append("=" * 52)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Automated File Organizer & Cleanup Utility")
    parser.add_argument("folder", nargs="?", default=str(Path.home() / "Downloads"),
                        help="folder to organize (default: your Downloads folder)")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would happen without moving any files")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="do not ask for confirmation")
    args = parser.parse_args()

    logger = setup_logging()
    folder = Path(args.folder).expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        logger.error(f"Folder not found: {folder}")
        sys.exit(1)
    if is_unsafe_folder(folder):
        logger.error(f"Refusing to organize '{folder}'. Choose a specific folder such as Downloads.")
        sys.exit(1)

    print(f"Target folder: {folder}")
    if not args.dry_run and not args.yes:
        try:
            answer = input("Move files into category sub-folders? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        if answer not in ("y", "yes"):
            print("Cancelled. No files were moved.")
            return

    logger.info(f"--- Run started{' (dry run)' if args.dry_run else ''}: {folder} ---")
    start = time.perf_counter()
    stats, per_category = organize(folder, args.dry_run, logger)
    elapsed = time.perf_counter() - start

    summary = print_summary(folder, stats, per_category, args.dry_run, elapsed)
    logger.info(summary)
    print(f"\nLog saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()
