"""Windows track coverage tests."""

from __future__ import annotations

from learn_networking.levels import load_catalog
from learn_networking.session import Session


def test_windows_only_levels_exist() -> None:
    catalog = load_catalog()
    win = [lv for lv in catalog.values() if lv.track == "windows"]
    assert len(win) >= 5
    for level in win:
        assert level.solution_commands_windows or level.solution_commands
        assert "windows" in level.steps or level.steps.get("windows")


def test_windows_solution_solves_level() -> None:
    session = Session()
    session.load_level("win-01-ipconfig")
    session.execute("os windows")
    session.execute(
        "New-NetIPAddress -InterfaceAlias Ethernet0 -IPAddress 10.0.0.30 -PrefixLength 24"
    )
    assert session.state.solved


def test_solution_windows_dialect() -> None:
    session = Session()
    session.load_level("win-04-route-print")
    session.execute("os windows")
    result = session.execute("solution --windows --run")
    assert result.ok
    assert session.state.solved


def test_dual_levels_have_windows_solution() -> None:
    catalog = load_catalog()
    for level in catalog.values():
        if level.track in ("both", "windows"):
            assert (
                level.solution_commands_windows or level.solution_commands
            ), f"{level.id} missing windows solution"
