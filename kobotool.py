#!/usr/bin/env python
#
import argparse
import base64
import os
import re
import shutil
import sqlite3
import sys
from typing import List, Set, Tuple

# --- Shared Utilities ---


def regex_match(expr: str, item: str) -> bool:
    if item is None:
        return False
    return bool(re.search(expr, item, re.IGNORECASE))


def get_kobo_cache_name(content_id: str) -> str:
    encoded = base64.b64encode(content_id.encode("utf-8")).decode("utf-8")
    return encoded.replace("/", "_").replace("+", "-").rstrip("=")


def get_db_connection(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.create_function("REGEXP", 2, regex_match)
    return conn


# --- Subcommand Logic ---


def do_search(args):
    db_path = os.path.join(args.path, ".kobo", "KoboReader.sqlite")
    print(f"[*] Searching for '{args.regex}' in {db_path}...")

    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        query = """
            SELECT ContentID, Title, Attribution
            FROM content
            WHERE ContentType = 6 AND (Title REGEXP ? OR Attribution REGEXP ?)
            ORDER BY Title ASC
        """
        cursor.execute(query, (args.regex, args.regex))
        matches = cursor.fetchall()

        if not matches:
            print("[-] No matches found.")
        else:
            print(f"[+] Found {len(matches)} matches:\n")
            header = f"{'ID':<40} | {'Title':<40} | {'Author':<25}"
            print(header + "\n" + "-" * len(header))
            for cid, title, author in matches:
                display_id = str(cid).replace("file:///mnt/onboard/", "")
                print(
                    f"{display_id[:38]:<40} | {str(title)[:38]:<40} | {str(author)[:25]:<25}"
                )
        conn.close()
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)


def do_purge(args):
    db_path = os.path.join(args.path, ".kobo", "KoboReader.sqlite")
    cache_base = os.path.join(args.path, ".kobo-images")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ContentID, Title FROM content WHERE ContentType = 6 AND (Title REGEXP ? OR Attribution REGEXP ?)",
        (args.regex, args.regex),
    )
    targets = cursor.fetchall()
    conn.close()

    if not targets:
        print("[-] No matching books found.")
        return

    deleted_count = 0
    for cid, title in targets:
        b64_cid = get_kobo_cache_name(cid)
        for foldername in os.listdir(cache_base):
            folder_path = os.path.join(cache_base, foldername)
            if os.path.isdir(folder_path) and (
                foldername == b64_cid or foldername in cid
            ):
                if args.dry_run:
                    print(f" [DRY-RUN] Would delete cache for: {title} ({foldername})")
                else:
                    shutil.rmtree(folder_path)
                    print(f" [DELETED] Cache for: {title}")
                    deleted_count += 1
    print(f"\n[!] Finished. Purged {deleted_count} directories.")


def do_clean(args):
    db_path = os.path.join(args.path, ".kobo", "KoboReader.sqlite")
    cache_path = os.path.join(args.path, ".kobo-images")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ContentID FROM content")
    active_ids = {row[0] for row in cursor.fetchall() if row[0]}
    conn.close()

    valid_names = {aid for aid in active_ids} | {
        get_kobo_cache_name(aid) for aid in active_ids
    }
    orphans = [
        os.path.join(cache_path, f)
        for f in os.listdir(cache_path)
        if os.path.isdir(os.path.join(cache_path, f))
        and f not in valid_names
        and not any(f in aid for aid in active_ids)
    ]

    if not orphans:
        print("[+] Cache is already clean.")
        return

    print(f"[!] Found {len(orphans)} orphans.")
    for p in orphans:
        if args.dry_run:
            print(f" [DRY-RUN] Would delete: {p}")
        else:
            shutil.rmtree(p)
            print(f" [DELETED] {p}")


# --- CLI Setup ---


def main():
    parser = argparse.ArgumentParser(description="Kobo Elipsa Maintenance Toolkit")
    parser.add_argument(
        "--path", default="/Volumes/KOBOeReader", help="Kobo mount point"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search
    s_parser = subparsers.add_parser("search", help="Search library using regex")
    s_parser.add_argument("regex", help="Pattern for Title or Author")

    # Purge
    p_parser = subparsers.add_parser(
        "purge", help="Delete specific book caches via regex"
    )
    p_parser.add_argument("regex", help="Pattern for Title or Author")
    p_parser.add_argument("--dry-run", action="store_true")

    # Clean
    c_parser = subparsers.add_parser("clean", help="Remove all orphaned cache folders")
    c_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    # Map commands to functions
    cmds = {"search": do_search, "purge": do_purge, "clean": do_clean}
    cmds[args.command](args)


if __name__ == "__main__":
    main()
