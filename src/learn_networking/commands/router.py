"""Command dispatch: parse a line into a structured request.

Both Linux and Windows syntaxes map onto a small set of intents so the
engine stays dialect-agnostic.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """A parsed command line.

    Args:
        raw: Original line.
        argv: Tokenized arguments.
        intent: Canonical verb (``ifconfig``, ``route_add``, ``dns_query``...).
        source: Which layer produced the intent (``linux``, ``windows``, ``meta``).
    """

    raw: str
    argv: tuple[str, ...]
    intent: str
    source: str


@dataclass
class CommandResult:
    """Result of executing a command.

    Args:
        ok: Whether the command succeeded.
        output: Stdout-like text.
        error: Stderr-like text (empty on success).
        mutated: True if world state changed (counts toward command golf).
    """

    ok: bool = True
    output: str = ""
    error: str = ""
    mutated: bool = False

    @classmethod
    def out(cls, text: str, *, mutated: bool = False) -> "CommandResult":
        """Build a successful result.

        Args:
            text: Output text.
            mutated: Whether state changed.

        Returns:
            Successful result.
        """
        return cls(ok=True, output=text, mutated=mutated)

    @classmethod
    def fail(cls, text: str) -> "CommandResult":
        """Build a failed result.

        Args:
            text: Error text.

        Returns:
            Failed result.
        """
        return cls(ok=False, error=text)


def tokenize(line: str) -> list[str]:
    """Tokenize a command line with shell-like quoting.

    Args:
        line: Raw command line.

    Returns:
        Tokens (possibly empty list for blank input).

    Examples:
        >>> tokenize("ip addr add 10.0.0.5/24 dev eth0")
        ['ip', 'addr', 'add', '10.0.0.5/24', 'dev', 'eth0']
    """
    line = line.strip()
    if not line:
        return []
    try:
        return shlex.split(line, posix=True)
    except ValueError:
        return line.split()


Handler = Callable[[list[str], "CommandContext"], CommandResult]  # noqa: F821


@dataclass
class CommandContext:
    """Execution context passed to handlers.

    Attributes:
        session: Live game session (world + current host).
    """

    session: "object"  # Session; avoided circular import at type time


# intent resolution tables are built in linux.py / windows.py / meta.py
_INTENT_ALIASES: list[tuple[tuple[str, ...], str]] = [
    (("levels",), "meta_levels"),
    (("level",), "meta_level"),
    (("hint",), "meta_hint"),
    (("show", "goal"), "meta_goal"),
    (("goal",), "meta_goal"),
    (("show", "objective"), "meta_objective"),
    (("objective",), "meta_objective"),
    (("reset",), "meta_reset"),
    (("undo",), "meta_undo"),
    (("topo",), "meta_topo"),
    (("topology",), "meta_topo"),
    (("hosts",), "meta_hosts"),
    (("hostinfo",), "meta_hostinfo"),
    (("ssh",), "meta_ssh"),
    (("os",), "meta_os"),
    (("solution",), "meta_solution"),
    (("help",), "meta_help"),
    (("sandbox",), "meta_sandbox"),
    (("clear",), "meta_clear"),
    (("whoami",), "meta_whoami"),
    (("man",), "meta_man"),
]


def match_intent(argv: list[str]) -> tuple[str, str] | None:
    """Match argv against known multi-word prefixes.

    Args:
        argv: Tokenized command.

    Returns:
        ``(intent, source)`` or None if unknown.

    Examples:
        >>> match_intent(["show", "goal"])
        ('meta_goal', 'meta')
    """
    if not argv:
        return None
    joined = tuple(a.lower() for a in argv)
    for prefix, intent in _INTENT_ALIASES:
        n = len(prefix)
        if joined[:n] == prefix:
            return intent, "meta"
    return None
