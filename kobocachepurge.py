#!/usr/bin/env python
#
import argparse
import os
import re
import shutil
import sqlite3
import sys
from typing import List, Tuple


def regex_match(expr: str, item: str) -> bool:
    """The bridge between SQLite and Python's re module."""
    if item is None:
        return False
    return bool(re.search(expr, item, re.IGNORECASE))


def get_target_cache_ids(db_path: str, pattern: str) -> List[Tuple[str, str]]:
    """Returns a list of (ContentID, Title) for books matching the regex."""
    results = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.create_function("REGEXP", 2, regex_match)
        cursor = conn.cursor()

        # We need ImageID or ContentID to find the folder in .kobo-images
        query = """
            SELECT ContentID, Title
            FROM content
            WHERE ContentType = 6
            AND (Title REGEXP ? OR Attribution REGEXP ?)
        """
        cursor.execute(query, (pattern, pattern))
        results = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    return results


def main(prg_name: str) -> None:
    parser = argparse.ArgumentParser(
        description="Remove cached covers for books matching a regex."
    )
    parser.add_argument("path", help="Path to the Kobo mount point")
    parser.add_argument("regex", help="Regex to match book titles or authors")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be deleted"
    )

    args = parser.parse_args()

    db_path = os.path.join(args.path, ".kobo", "KoboReader.sqlite")
    cache_base = os.path.join(args.path, ".kobo-images")

    print(f"[*] {prg_name}: Searching for matches to '{args.regex}'...")
    targets = get_target_cache_ids(db_path, args.regex)

    if not targets:
        print(f"[-] {prg_name}: No matching books found.", file=sys.stderr)
        return

    print(f"[+] {prg_name}: Found {len(targets)} matching books. Checking cache...")

    deleted_count = 0
    for cid, title in targets:
        # Kobo creates a folder in .kobo-images based on a transformed version of the ID
        # For sideloaded books, it's often a simplified string.
        # We search for a directory name that exists within the ContentID string.

        found_in_cache = False
        for foldername in os.listdir(cache_base):
            folder_path = os.path.join(cache_base, foldername)

            # Logic: If the cache folder name is part of the book's unique ID
            if os.path.isdir(folder_path) and foldername in cid:
                found_in_cache = True
                if args.dry_run:
                    print(
                        f" {prg_name}: [DRY-RUN] Would delete cache for: {title} ({foldername})"
                    )
                else:
                    try:
                        shutil.rmtree(folder_path)
                        print(
                            f" {prg_name}: [DELETED] Cache for: {title}",
                            file=sys.stderr,
                        )
                        deleted_count += 1
                    except OSError as e:
                        print(
                            f" {prg_name}: [ERROR] Could not delete {foldername}: {e}",
                            file=sys.stderr,
                        )

        if not found_in_cache:
            print(f" {prg_name}: [SKIP] No cache folder found for: {title}")

    if not args.dry_run:
        print(
            f"\n[!] {prg_name} Finished. Removed {deleted_count} cache directories.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    prg_name = "KoboCachePurge"
    main(prg_name=prg_name)
