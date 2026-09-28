"""Command surface package."""

from learn_networking.commands.linux import LINUX_HANDLERS
from learn_networking.commands.meta import META_HANDLERS
from learn_networking.commands.router import CommandContext, CommandRequest, CommandResult, match_intent, tokenize
from learn_networking.commands.windows import WINDOWS_HANDLERS

__all__ = [
    "CommandContext",
    "CommandRequest",
    "CommandResult",
    "LINUX_HANDLERS",
    "META_HANDLERS",
    "WINDOWS_HANDLERS",
    "match_intent",
    "tokenize",
]
