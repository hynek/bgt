# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "bgt",
#     "watchfiles",
# ]
# ///
"""
Print the changes in a directory until you press Ctrl-C.

Usage: uv run watch_dir.py DIRECTORY
"""

import argparse
import threading
import time

from collections.abc import Generator
from pathlib import Path

import structlog
import watchfiles

import bgt


logger = structlog.get_logger()


def watch_dir(path: Path, stop: threading.Event) -> Generator[None]:
    """
    Print the changes in *path* until *stop* is set.
    """
    # Don't yield before the watcher runs. If it can't start, the supervisor
    # would see a completed work unit, reset its backoff, and restart the
    # stream in a tight loop.
    #
    # watchfiles checks *stop* every 50 ms, so a stop takes effect quickly.
    # With *yield_on_timeout*, it also yields an empty set after 5 seconds
    # without changes. So a quiet but healthy stream doesn't look stuck.
    for changes in watchfiles.watch(
        path, stop_event=stop, yield_on_timeout=True
    ):
        for change, changed_path in sorted(changes):
            print(f"{change.name:>8}: {changed_path}")

        yield


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print the changes in a directory until you press Ctrl-C."
    )
    parser.add_argument("directory", type=Path, help="The directory to watch.")
    args = parser.parse_args()

    if not args.directory.is_dir():
        parser.error(f"not a directory: {args.directory}")

    with bgt.SupervisedService.start_stream(
        lambda stop: watch_dir(args.directory, stop), name="watch-dir"
    ):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("shutting down")


if __name__ == "__main__":
    main()
