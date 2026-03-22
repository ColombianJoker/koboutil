#!/usr/bin/env python
#
import argparse
import os
import re
import sqlite3
import sys
from typing import List, Tuple


def regex_match(expr: str, item: str) -> bool:
    """The bridge between SQLite and Python's re module."""
    if item is None:
        return False
    return bool(re.search(expr, item, re.IGNORECASE))


def search_kobo(db_path: str, pattern: str) -> List[Tuple[str, str]]:
    """Connects to Kobo DB and searches Title and Attribution (Author)."""
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    results = []
    try:
        # Open as read-only for safety
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

        # Register the 'REGEXP' function so SQL understands the keyword
        conn.create_function("REGEXP", 2, regex_match)

        cursor = conn.cursor()

        # ContentType 6 is usually the main entry for a book (not chapters)
        query = """
            SELECT Title, Attribution
            FROM content
            WHERE ContentType = 6
            AND (Title REGEXP ? OR Attribution REGEXP ?)
            ORDER BY Title ASC
        """

        cursor.execute(query, (pattern, pattern))
        results = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

    return results


def main(prg_name: str) -> None:
    parser = argparse.ArgumentParser(
        description="Regex search the Kobo library database."
    )
    parser.add_argument("path", help="Path to the Kobo mount point")
    parser.add_argument(
        "regex", help="Regular expression to search for (titles or authors)"
    )

    args = parser.parse_args()

    # Construct the standard Kobo DB path
    db_path = os.path.join(args.path, ".kobo", "KoboReader.sqlite")

    print(f"[*] {prg_name}: Searching for '{args.regex}' in {db_path}...")

    matches = search_kobo(db_path, args.regex)

    if not matches:
        print(f"[-] {prg_name}: No matches found.")
    else:
        print(f"[+] {prg_name}: Found {len(matches)} matches:\n")
        # Print results in a clean format
        header = f"{'Title':<50} | {'Author':<30}"
        print(header)
        print("-" * len(header))
        for title, author in matches:
            print(f"{str(title)[:48]:<50} | {str(author)[:30]:<30}")


if __name__ == "__main__":
    prg_name = "KoboSearch"
    main(prg_name=prg_name)
