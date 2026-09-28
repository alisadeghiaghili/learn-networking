"""Tests for the session command loop and level solving."""

from __future__ import annotations

from learn_networking.levels import load_catalog
from learn_networking.session import Session


def test_sandbox_prompt(session: Session) -> None:
    assert "@" in session.prompt() or session.prompt().startswith("PS")


def test_sandbox_ip_addr(session: Session) -> None:
    result = session.execute("ip a")
    assert result.ok
    assert "web-01" in result.output


def test_ssh_switch(session: Session) -> None:
    result = session.execute("ssh ops-01")
    assert result.ok
    assert session.current_host().name == "ops-01"
    assert session.prompt().startswith("PS")


def test_windows_ipconfig(session: Session) -> None:
    session.execute("ssh ops-01")
    result = session.execute("ipconfig")
    assert result.ok
    assert "Windows IP Configuration" in result.output


def test_meta_levels_lists_catalog(session: Session) -> None:
    result = session.execute("levels")
    assert result.ok
    assert "link-01-address" in result.output


def test_level_solve_address() -> None:
    session = Session()
    load = session.load_level("link-01-address")
    assert load.ok
    assert not session.state.solved
    result = session.execute("ip addr add 10.0.0.30/24 dev eth0")
    assert result.ok
    assert session.state.solved
    assert session.progress.is_solved("link-01-address")


def test_level_windows_solution() -> None:
    session = Session()
    session.load_level("link-01-address")
    session.execute("os windows")
    result = session.execute(
        "New-NetIPAddress -InterfaceAlias eth0 -IPAddress 10.0.0.30 -PrefixLength 24"
    )
    assert result.ok
    assert session.state.solved


def test_command_golf_counts_mutating_only() -> None:
    session = Session()
    session.load_level("link-01-address")
    session.execute("ip a")
    session.execute("topo")
    session.execute("ip addr add 10.0.0.30/24 dev eth0")
    assert session.state.commands_issued == 1


def test_undo_restores() -> None:
    session = Session()
    session.load_level("link-01-address")
    session.execute("ip addr add 10.0.0.30/24 dev eth0")
    assert session.state.solved
    session.execute("undo")
    assert not session.state.solved


def test_reset_works() -> None:
    session = Session()
    session.load_level("link-01-address")
    session.execute("ip addr add 10.0.0.30/24 dev eth0")
    session.execute("reset")
    assert not session.state.solved


def test_solution_disables_best() -> None:
    session = Session()
    session.load_level("link-01-address")
    result = session.execute("solution")
    assert result.ok
    assert session.state.show_solution_used


def test_dns_level() -> None:
    session = Session()
    session.load_level("dns-01-a-record")
    session.execute("nsupdate add A internal api 10.0.2.10")
    assert session.state.solved


def test_firewall_level() -> None:
    session = Session()
    session.load_level("firewall-01-open-port")
    session.execute("ssh web-01")
    session.execute("iptables -A INPUT -p tcp --dport 80 -j ACCEPT")
    assert session.state.solved


def test_troubleshoot_level_full_solution() -> None:
    session = Session()
    session.load_level("troubleshoot-01-etl-postgres")
    session.execute("solution --run")
    assert session.state.solved


def test_all_levels_have_unique_ids() -> None:
    catalog = load_catalog()
    assert catalog
    assert len(catalog) == len(set(catalog))


def test_all_levels_buildable() -> None:
    catalog = load_catalog()
    for level in catalog.values():
        world = level.build_world()
        assert world.hosts
        assert level.goal_checks


def test_goal_render(session: Session) -> None:
    session.load_level("link-01-address")
    text = session.render_goal()
    assert "client-01 eth0 has 10.0.0.30/24" in text
    assert "[ ]" in text or "[x]" in text
