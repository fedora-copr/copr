#!/usr/bin/python3

"""
Remove RPMs that are moved to PULP.
"""
import argparse
from collections import defaultdict
import logging
import os
import pwd
import sys

from copr_common.log import setup_script_logger

log = logging.getLogger(__name__)

def find_and_remove_unique_rpms(start_dir, dry_run=True):
    """
    Traverses a directory, counts occurrences of each unique RPM filename,
    and removes files that are only present once (unique).

    :param start_dir: The path to the root directory to start searching.
    :param dry_run: If True, only prints actions without deleting files.
    """
    if not os.path.isdir(start_dir):
        # Using %s for string insertion
        log.error("Directory not found at %s", start_dir)
        return

    # --- CONFIRMATION STEP ---
    # input() must still use standard string formatting for the prompt
    confirmation = input(
        "WARNING: This script will scan and potentially delete files in '%s'.\n"
        "Do you want to proceed? (yes/no): " % start_dir
    ).lower()

    if confirmation not in ('yes', 'y'):
        log.info("Operation cancelled by user.")
        return
    # --- END CONFIRMATION STEP ---

    # Using %s for string insertion
    log.info("--- Starting traversal in: %s (Dry Run: %s) ---", start_dir, dry_run)

    # Dictionary to store {filename: [list of full paths]}
    rpm_files = defaultdict(list)

    # 1. Traverse the directory and collect all RPM paths
    for root, _, files in os.walk(start_dir):
        for filename in files:
            if filename.endswith('.rpm'):
                full_path = os.path.join(root, filename)
                rpm_files[filename].append(full_path)

    total_files_found = sum(len(paths) for paths in rpm_files.values())
    # Using %d for integer insertion
    log.info("Found %d total RPM files.", total_files_found)

    files_to_remove = []

    # 2. Identify files that are unique (occur only once)
    for filename, paths in rpm_files.items():
        if len(paths) == 1:
            # This RPM file is unique. Add its single path to the list for removal.
            files_to_remove.extend(paths)

    # 3. Perform removal (or print actions if dry_run)
    if not files_to_remove:
        log.info("No unique RPM files found to remove.")
        return

    # Using %d for integer insertion
    log.info("\n--- Processing %d unique files for removal ---", len(files_to_remove))

    for file_path in files_to_remove:
        if dry_run:
            # Using %s for string insertion
            log.info("[DRY RUN] Will remove: %s", file_path)
        else:
            try:
                os.remove(file_path)
                # Using %s for string insertion
                log.info("REMOVED: %s", file_path)
            except OSError as e:
                # log.error supports the same %s formatting
                log.error("ERROR removing %s: %s", file_path, e)

    if dry_run:
        log.info("\n*** Dry run finished. Rerun with --execute to perform actual deletion. ***")
    else:
        log.info("\n*** Deletion finished. ***")


if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    setup_script_logger(log, "/var/log/copr-backend/change-storage-delete.log")
    parser = argparse.ArgumentParser(
        description="Finds and removes RPM files that are unique (occur only once) across all subdirectories."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="The root directory to traverse."
    )
    parser.add_argument(
        "-e", "--execute",
        action="store_true",
        help="Perform the actual deletion (default is a dry run)."
    )

    args = parser.parse_args()

    # Pass the argument and dry_run status to the main function
    find_and_remove_unique_rpms(args.directory, dry_run=not args.execute)
