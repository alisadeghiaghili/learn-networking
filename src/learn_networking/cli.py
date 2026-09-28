"""CLI entrypoint for learn-networking."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from learn_networking.progress import ProgressStore
from learn_networking.session import Session


def _progress_path() -> Path:
    """Return the default progress file path.

    Returns:
        Path under the user's home directory.
    """
    return Path.home() / ".learn-networking" / "progress.json"


def run_repl(session: Session) -> int:
    """Run the interactive loop.

    Args:
        session: Live session.

    Returns:
        Process exit code.
    """
    print("learn-networking — LGB-style lab for data & DevOps networking")
    print("Type 'help' for commands, 'levels' for challenges, 'topo' for the map.\n")
    if session.level:
        print(session.render_objective())
        print()
    else:
        print("Sandbox mode.\n")
        print(session.render_topology())
        print()

    while True:
        try:
            line = input(session.prompt() + " ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line.lower() in ("exit", "quit", "logout"):
            return 0
        result = session.execute(line)
        if result.output:
            print(result.output)
        if result.error:
            print(result.error, file=sys.stderr)
        if session.level and session.state.solved:
            # gentle notification once
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    """Program entrypoint.

    Args:
        argv: Optional argument vector (defaults to sys.argv[1:]).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(
        prog="learn-networking",
        description="Interactive networking lab inspired by learnGitBranching",
    )
    parser.add_argument("level", nargs="?", help="level id to load on start")
    parser.add_argument("--sandbox", action="store_true", help="start in sandbox mode")
    parser.add_argument("--cmd", "-c", action="append", default=[], help="run a command and exit (repeatable)")
    parser.add_argument("--no-save", action="store_true", help="do not persist progress")
    parser.add_argument("--list-levels", action="store_true", help="print levels and exit")
    args = parser.parse_args(argv)

    progress = ProgressStore() if args.no_save else ProgressStore.load(_progress_path())
    start_level = None if args.sandbox else args.level
    session = Session(progress=progress, start_level_id=start_level)

    if args.list_levels:
        print(session.render_levels())
        return 0

    if args.cmd:
        for line in args.cmd:
            result = session.execute(line)
            if result.output:
                print(result.output)
            if result.error:
                print(result.error, file=sys.stderr)
        return 0 if all(session.execute("") is not None for _ in [0]) else 1

    return run_repl(session)


if __name__ == "__main__":
    raise SystemExit(main())
