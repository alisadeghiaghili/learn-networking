"""Progress store: solved levels and command-golf scores."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LevelScore:
    """Best score for one level.

    Args:
        best_commands: Lowest mutating-command count (None if never solved).
        solved: Whether the level has been solved at least once.
    """

    best_commands: int | None = None
    solved: bool = False


@dataclass
class ProgressStore:
    """Persistent progress across sessions.

    Args:
        path: JSON file location. If None, progress is memory-only.
        scores: Level id -> score.
    """

    path: Path | None = None
    scores: dict[str, LevelScore] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None) -> "ProgressStore":
        """Load progress from disk.

        Args:
            path: JSON path (may not exist yet).

        Returns:
            Progress store (empty if the file is missing or corrupt).
        """
        store = cls(path=path)
        if path is None or not path.exists():
            return store
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return store
        for level_id, payload in raw.get("scores", {}).items():
            store.scores[level_id] = LevelScore(
                best_commands=payload.get("best_commands"),
                solved=bool(payload.get("solved", False)),
            )
        return store

    def save(self) -> None:
        """Write progress to disk if a path is configured."""
        if self.path is None:
            return
        payload = {
            "scores": {
                level_id: {
                    "best_commands": score.best_commands,
                    "solved": score.solved,
                }
                for level_id, score in sorted(self.scores.items())
            }
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def record(self, level_id: str, commands_used: int, *, best_possible: int) -> LevelScore:
        """Record a solve.

        Args:
            level_id: Level identifier.
            commands_used: Mutating commands the player used.
            best_possible: Par (reference solution length).

        Returns:
            Updated score.
        """
        score = self.scores.setdefault(level_id, LevelScore())
        score.solved = True
        if score.best_commands is None or commands_used < score.best_commands:
            score.best_commands = commands_used
        self.save()
        return score

    def is_solved(self, level_id: str) -> bool:
        """Return whether a level is marked solved.

        Args:
            level_id: Level identifier.

        Returns:
            True if solved.
        """
        score = self.scores.get(level_id)
        return bool(score and score.solved)

    def best(self, level_id: str) -> int | None:
        """Return best command count for a level.

        Args:
            level_id: Level identifier.

        Returns:
            Best count or None.
        """
        score = self.scores.get(level_id)
        return score.best_commands if score else None
