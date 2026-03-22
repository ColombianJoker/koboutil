#!/usr/bin/env python
#
import argparse
import os
import shutil
import sqlite3
import sys
from typing import List, Set


def get_active_book_ids(prg_name: str, db_path: str) -> Set[str]:
    """Extracts all ContentIDs from the Kobo database."""
    ids: Set[str] = set()

    if not os.path.exists(db_path):
        print(f"{prg_name}: Error, database not found at '{db_path}'", file=sys.stderr)
        return set()

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ContentID FROM content")
        ids = {row[0] for row in cursor.fetchall() if row[0]}
        conn.close()
        return ids
    except sqlite3.Error as e:
        print(f"{prg_name}: Database error: {e}", file=sys.stderr)
        return set()


def find_orphans(prg_name: str, cache_path: str, active_ids: Set[str]) -> List[str]:
    """Returns cached images without id in the database."""
    orphans: List[str] = []
    if not os.path.exists(cache_path):
        print(
            f"{prg_name}: Cache directory not found at '{cache_path}'", file=sys.stderr
        )
        return []

    # Iterate through the hex-named subdirectories in .kobo-images
    for item in os.listdir(cache_path):
        item_path = os.path.join(cache_path, item)
        if os.path.isdir(item_path):
            # If the folder name isn't associated with an active ContentID
            if not any(item in aid for aid in active_ids):
                orphans.append(item_path)
    return orphans


def main(prg_name: str) -> None:
    parser = argparse.ArgumentParser(
        description="Identify and remove orphaned cover images from a Kobo eReader."
    )
    parser.add_argument(
        "path",
        default="/Volumes/KOBOeReader",
        help="Path to the mounted Kobo device (e.g., /Volumes/KOBOeReader or /mnt/kobo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List orphaned folders without deleting them",
    )

    args = parser.parse_args()

    # Define internal Kobo paths based on the provided mount point
    db_path = os.path.join(args.path, ".kobo", "KoboReader.sqlite")
    cache_path = os.path.join(args.path, ".kobo-images")

    if not os.path.isdir(args.path):
        print(
            f"{prg_name}: Error, '{args.path}' is not a valid directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[*] {prg_name}: Reading database '{db_path}'")
    active_ids = get_active_book_ids(prg_name, db_path)

    if not active_ids:
        print(
            f"[-] {prg_name}: Could not retrieve book IDs. Aborting.", file=sys.stderr
        )
        sys.exit(1)
    else:
        print(f"[+] {prg_name}: {len(active_ids)} ids found.")

    print(f"[*] {prg_name}: Scanning cache '{cache_path}'")
    orphan_list = find_orphans(prg_name, cache_path, active_ids)

    if not orphan_list:
        print(f"[+] {prg_name}: No orphaned covers found. Your Elipsa is clean!")
        return

    print(f"[!] Found {len(orphan_list)} orphaned cover directories.")

    if args.dry_run:
        for p in orphan_list:
            print(f"  (Dry-run) Would delete: {p}")
    else:
        confirm = input("Confirm deletion? (y/N): ")
        if confirm.lower() == "y":
            for p in orphan_list:
                shutil.rmtree(p)
            print("[+] Cleanup complete.")
        else:
            print("[#] Operation cancelled.")


if __name__ == "__main__":
    prg_name = "CoverClean"
    main(prg_name=prg_name)
