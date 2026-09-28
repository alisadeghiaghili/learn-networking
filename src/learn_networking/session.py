"""Game session: world + current host + level runtime + command loop."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from learn_networking.commands.linux import LINUX_HANDLERS
from learn_networking.commands.meta import META_HANDLERS
from learn_networking.commands.router import CommandContext, CommandResult, match_intent, tokenize
from learn_networking.commands.windows import WINDOWS_HANDLERS
from learn_networking.engine.addressing import parse_address
from learn_networking.engine.topology import Host, HostOS, Interface, LinkState, NetworkWorld
from learn_networking.levels import Level, SequenceInfo, SEQUENCES, load_catalog
from learn_networking.levels.loader import LevelError
from learn_networking.progress import ProgressStore
from learn_networking.viz import render_hosts, render_topology


@dataclass
class SessionState:
    """Mutable play state for one level/sandbox run.

    Attributes:
        world: Current lab world.
        current_host: Active hostname.
        undo_stack: Snapshot stack for ``undo``.
        commands_issued: Mutating command count since level start.
        command_log: All command lines since level start.
        solved: Whether the level has been solved.
        show_solution_used: Whether the player revealed the solution.
    """

    world: NetworkWorld
    current_host: str
    undo_stack: list[dict[str, Any]] = field(default_factory=list)
    commands_issued: int = 0
    command_log: list[str] = field(default_factory=list)
    solved: bool = False
    show_solution_used: bool = False


class Session:
    """Playable session (sandbox or level).

    Args:
        catalog: Level catalog.
        progress: Progress store.
        start_level_id: Optional level to load immediately.
    """

    def __init__(
        self,
        catalog: dict[str, Level] | None = None,
        progress: ProgressStore | None = None,
        start_level_id: str | None = None,
    ) -> None:
        self.catalog = catalog if catalog is not None else load_catalog()
        self.progress = progress if progress is not None else ProgressStore()
        self.level: Level | None = None
        self.state = self._default_sandbox_state()
        if start_level_id:
            self.load_level(start_level_id)

    # ------------------------------------------------------------------
    # world / host access
    # ------------------------------------------------------------------

    def current_host(self) -> Host:
        """Return the active host.

        Returns:
            Host the player is "logged into".
        """
        return self.state.world.get_host(self.state.current_host)

    def _default_sandbox_state(self) -> SessionState:
        """Build the default sandbox lab.

        Returns:
            Fresh sandbox SessionState.
        """
        world = NetworkWorld()
        world.add_network("lab", "10.0.0.0/24")
        world.add_network("db-net", "10.0.2.0/24")

        gw = Host(name="gw-01", os=HostOS.LINUX, role="router")
        world.add_host(gw)
        world.connect("gw-01", "eth0", "lab", ip="10.0.0.1", prefix=24)
        world.connect("gw-01", "eth1", "db-net", ip="10.0.2.1", prefix=24)

        web = Host(name="web-01", os=HostOS.LINUX, role="web")
        world.add_host(web)
        world.connect("web-01", "eth0", "lab", ip="10.0.0.10", prefix=24)
        web.default_gateway = parse_address("10.0.0.1")

        win = Host(name="ops-01", os=HostOS.WINDOWS, role="ops")
        world.add_host(win)
        world.connect("ops-01", "Ethernet0", "lab", ip="10.0.0.20", prefix=24)
        win.default_gateway = parse_address("10.0.0.1")

        db = Host(name="db-01", os=HostOS.LINUX, role="db")
        world.add_host(db)
        world.connect("db-01", "eth0", "db-net", ip="10.0.2.10", prefix=24)
        from learn_networking.engine.services import ServiceBinding

        db.services[5432] = ServiceBinding(proto="tcp", name="postgres", banner="pg", healthy=True)

        return SessionState(world=world, current_host="web-01")

    def _snapshot(self) -> dict[str, Any]:
        """Capture world + counters for undo.

        Returns:
            Opaque snapshot dict.
        """
        return {
            "world": copy.deepcopy(self.state.world),
            "commands_issued": self.state.commands_issued,
            "solved": self.state.solved,
        }

    def _restore(self, snap: dict[str, Any]) -> None:
        """Restore a snapshot.

        Args:
            snap: Snapshot from ``_snapshot``.
        """
        self.state.world = copy.deepcopy(snap["world"])
        self.state.commands_issued = snap["commands_issued"]
        self.state.solved = snap["solved"]

    def push_undo(self) -> None:
        """Push the current world onto the undo stack."""
        self.state.undo_stack.append(self._snapshot())
        if len(self.state.undo_stack) > 50:
            self.state.undo_stack.pop(0)

    # ------------------------------------------------------------------
    # command execution
    # ------------------------------------------------------------------

    def execute(self, line: str) -> CommandResult:
        """Parse and run one command line.

        Args:
            line: Raw input.

        Returns:
            Command result. Never raises for normal user errors.
        """
        line = line.strip()
        if not line:
            return CommandResult.out("")
        tokens = tokenize(line)
        if not tokens:
            return CommandResult.out("")

        # chained commands with ';'
        if line.count(";") and len(tokens) >= 1:
            # tokenize keeps ';'-separated as separate if user used shell-style;
            # support simple 'a; b' splitting on the raw line
            if ";" in line:
                results = []
                for part in line.split(";"):
                    part = part.strip()
                    if not part:
                        continue
                    results.append(self.execute(part))
                if not results:
                    return CommandResult.out("")
                merged_ok = all(r.ok for r in results)
                merged_out = "\n".join(r.output for r in results if r.output)
                merged_err = "\n".join(r.error for r in results if r.error)
                mutated = any(r.mutated for r in results)
                if not merged_ok:
                    return CommandResult(ok=False, output=merged_out, error=merged_err or "command failed", mutated=mutated)
                return CommandResult(ok=True, output=merged_out, mutated=mutated)

        ctx = CommandContext(session=self)

        intent_match = match_intent(tokens)
        if intent_match:
            intent, _src = intent_match
            handler = META_HANDLERS.get(intent)
            if handler:
                self.state.command_log.append(line)
                return handler(ctx, tokens)

        prog = tokens[0].lower()
        host = self.current_host()

        if self.level and self.level.disabled_commands:
            for blocked in self.level.disabled_commands:
                if line.lower().startswith(blocked.lower()):
                    return CommandResult.fail(f"command disabled in this level: {blocked}")

        # OS dialect selection: allow both if player wants, but surface errors
        # that teach the right tool for the host.
        handler = None
        source = host.os.value
        if source == "linux":
            handler = LINUX_HANDLERS.get(prog)
            if handler is None and prog in WINDOWS_HANDLERS:
                handler = WINDOWS_HANDLERS.get(prog)
        else:
            handler = WINDOWS_HANDLERS.get(prog)
            if handler is None and prog in LINUX_HANDLERS:
                handler = LINUX_HANDLERS.get(prog)

        # shared inspection
        if handler is None and prog in ("ping", "nslookup", "curl"):
            handler = LINUX_HANDLERS.get(prog) or WINDOWS_HANDLERS.get(prog)

        if handler is None:
            return CommandResult.fail(
                f"{prog}: command not found on {host.name} ({host.os.value}). Try 'help' or 'man'."
            )

        self.state.command_log.append(line)
        before = self.state.world.export_snapshot()
        self.push_undo()
        result = handler(ctx, tokens)
        if not result.ok:
            # pop undo for failed commands — they must not be undoable noise
            if self.state.undo_stack:
                self.state.undo_stack.pop()
            return result

        after = self.state.world.export_snapshot()
        if result.mutated or after != before:
            result.mutated = True
            self.state.commands_issued += 1
        else:
            # inspection — drop undo entry
            if self.state.undo_stack:
                self.state.undo_stack.pop()
            result.mutated = False

        self._maybe_solve()
        return result

    def _maybe_solve(self) -> None:
        """Mark level solved and record progress when goals pass."""
        if self.level is None or self.state.solved:
            return
        if not self.level.is_solved(self.state.world, self.state.current_host):
            return
        self.state.solved = True
        self.progress.record(
            self.level.id,
            self.state.commands_issued,
            best_possible=self.level.par or len(self.level.solution_commands),
        )

    # ------------------------------------------------------------------
    # meta renderers
    # ------------------------------------------------------------------

    def prompt(self) -> str:
        """Return the shell prompt string.

        Returns:
            e.g. ``you@web-01:~$`` or ``PS C:\\Users\\you>``.
        """
        host = self.current_host()
        if host.os == HostOS.WINDOWS:
            return "PS C:\\Users\\Administrator>"
        return f"you@{host.name}:~$"

    def render_levels(self) -> str:
        """Render the level browser.

        Returns:
            Sequences with solve marks.
        """
        lines = ["Levels", "======", ""]
        by_seq: dict[str, list[Level]] = {}
        for level in self.catalog.values():
            by_seq.setdefault(level.sequence, []).append(level)

        for seq_key in sorted(SEQUENCES, key=lambda k: SEQUENCES[k].order):
            info = SEQUENCES[seq_key]
            lines.append(f"[{seq_key}] {info.name}")
            lines.append(f"    {info.about}")
            for level in sorted(by_seq.get(seq_key, []), key=lambda lv: lv.id):
                mark = "x" if self.progress.is_solved(level.id) else " "
                best = self.progress.best(level.id)
                score = f"  best={best}" if best is not None else ""
                par = f"  par={level.par}" if level.par else ""
                lines.append(f"  ({mark}) {level.id:<22} {level.name}{par}{score}")
            lines.append("")
        lines.append("Load one with: level <id>")
        return "\n".join(lines)

    def render_hint(self) -> str:
        """Render the current hint.

        Returns:
            Hint text or a nudge to load a level.
        """
        if self.level is None:
            return "No level loaded. Type 'levels' then 'level <id>'. Sandbox is free-play."
        return self.level.hint or "No hint for this level."

    def render_objective(self) -> str:
        """Render the objective.

        Returns:
            Objective text.
        """
        if self.level is None:
            return "Sandbox mode — explore freely. Type 'levels' for challenges."
        focus = ", ".join(self.level.os_focus)
        return f"{self.level.name}\n\n{self.level.objective}\n\nOS focus: {focus}"

    def render_goal(self) -> str:
        """Render goal checks with pass/fail status.

        Returns:
            Checklist text.
        """
        if self.level is None:
            return "No level — no goal. Type 'levels'."
        lines = [f"Goal — {self.level.name}", "=======================", self.level.objective, ""]
        for ok, detail, check in self.level.check_goals(self.state.world, self.state.current_host):
            mark = "x" if ok else " "
            label = check.description or check.type
            lines.append(f"  [{mark}] {label}")
            lines.append(f"      {detail}")
        lines.append("")
        if self.state.solved:
            used = self.state.commands_issued
            par = self.level.par or len(self.level.solution_commands)
            extra = " (solution revealed — not a best)" if self.state.show_solution_used else ""
            lines.append(f"SOLVED in {used} mutating commands (par {par}){extra}")
        else:
            lines.append(
                f"Not solved yet. Mutating commands used: {self.state.commands_issued}"
            )
        return "\n".join(lines)

    def render_topology(self) -> str:
        """Render ASCII topology.

        Returns:
            Topology map.
        """
        return render_topology(self.state.world)

    def render_hosts(self) -> str:
        """Render host inventory.

        Returns:
            Host table.
        """
        return render_hosts(self.state.world)

    def render_hostinfo(self, name: str) -> str:
        """Render one host detail block.

        Args:
            name: Hostname.

        Returns:
            Detail text.
        """
        try:
            host = self.state.world.get_host(name)
        except KeyError as exc:
            return str(exc)
        lines = [
            f"Host {host.name}  os={host.os.value}  role={host.role}",
            "interfaces:",
        ]
        for iface in host.interfaces.values():
            lines.append("  " + iface.describe())
        lines.append(f"default gateway: {host.default_gateway or '-'}")
        lines.append("routes:")
        for dest, hop in sorted(host.routes.items()):
            lines.append(f"  {dest} via {hop}")
        lines.append(f"dns servers: {', '.join(host.dns_servers) or '-'}")
        lines.append(f"search: {', '.join(host.search_domains) or '-'}")
        lines.append(f"firewall: {'on' if host.firewall_enabled else 'off'}  rules={len(host.firewall_rules)}")
        for r in host.firewall_rules:
            lines.append(f"  {r}")
        if host.services:
            lines.append("services:")
            for port, svc in sorted(host.services.items()):
                lines.append(f"  {port}/{svc.proto} {svc.name} healthy={svc.healthy}")
        if host.host_aliases:
            lines.append("hosts file:")
            for k, v in sorted(host.host_aliases.items()):
                lines.append(f"  {k} -> {v}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # meta actions
    # ------------------------------------------------------------------

    def load_level(self, level_id: str) -> CommandResult:
        """Load a level by id.

        Args:
            level_id: Level identifier.

        Returns:
            Result with objective text, or failure.
        """
        level = self.catalog.get(level_id)
        if level is None:
            known = ", ".join(sorted(self.catalog))
            return CommandResult.fail(f"unknown level {level_id!r}. Try: {known}")
        try:
            world = level.build_world()
        except LevelError as exc:
            return CommandResult.fail(f"broken level {level_id}: {exc}")
        # pick a sensible start host: first linux client-ish, else first host
        start_host = _pick_start_host(world)
        self.level = level
        self.state = SessionState(world=world, current_host=start_host)
        return CommandResult.out(
            self.render_objective()
            + "\n\n"
            + self.render_goal()
            + "\n\nCommands: hint | goal | topo | hosts | ssh <host> | help"
        )

    def enter_sandbox(self) -> CommandResult:
        """Reset to free-play sandbox.

        Returns:
            Confirmation.
        """
        self.level = None
        self.state = self._default_sandbox_state()
        return CommandResult.out("Sandbox mode. Type 'topo' for the map, 'levels' for challenges.")

    def reset(self) -> CommandResult:
        """Restore the start world.

        Returns:
            Confirmation.
        """
        if self.level is not None:
            try:
                world = self.level.build_world()
            except LevelError as exc:
                return CommandResult.fail(str(exc))
            start_host = _pick_start_host(world)
            self.state = SessionState(world=world, current_host=start_host)
        else:
            self.state = self._default_sandbox_state()
        return CommandResult.out("Reset.", mutated=True)

    def undo(self) -> CommandResult:
        """Undo the last mutating command.

        Returns:
            Confirmation or failure if the stack is empty.
        """
        if not self.state.undo_stack:
            return CommandResult.fail("nothing to undo")
        snap = self.state.undo_stack.pop()
        self._restore(snap)
        return CommandResult.out("undone", mutated=True)

    def ssh(self, hostname: str) -> CommandResult:
        """Switch the active host.

        Args:
            hostname: Target host.

        Returns:
            Confirmation or failure.
        """
        if hostname not in self.state.world.hosts:
            return CommandResult.fail(f"ssh: Could not resolve hostname {hostname}")
        self.state.current_host = hostname
        host = self.current_host()
        return CommandResult.out(f"connected to {host.name} ({host.os.value})")

    def set_os(self, os_name: str) -> CommandResult:
        """Switch the command dialect (and host OS flavor).

        Args:
            os_name: ``linux`` or ``windows``.

        Returns:
            Confirmation.
        """
        host = self.current_host()
        host.os = HostOS(os_name)
        return CommandResult.out(f"{host.name} now speaks {os_name}")

    def show_solution(self, *, run: bool = False) -> CommandResult:
        """Print or run the reference solution.

        Args:
            run: If True, execute solution commands (non-best).

        Returns:
            Solution text or run transcript.
        """
        if self.level is None:
            return CommandResult.fail("no level loaded")
        cmds = self.level.solution_commands
        if not cmds:
            return CommandResult.fail("this level has no recorded solution")
        self.state.show_solution_used = True
        if not run:
            return CommandResult.out(
                "Reference solution (revealing this forfeits a best score):\n  "
                + "\n  ".join(cmds)
            )
        outputs = []
        for line in cmds:
            r = self.execute(line)
            outputs.append(f"$ {line}\n{r.output or r.error}")
        self._maybe_solve()
        return CommandResult.out("\n".join(outputs), mutated=True)


def _pick_start_host(world: NetworkWorld) -> str:
    """Choose a default login host for a freshly built world.

    Prefers a non-router host.

    Args:
        world: Lab world.

    Returns:
        Hostname.
    """
    for host in world.hosts.values():
        if host.role not in ("router", "gw", "firewall"):
            return host.name
    return next(iter(world.hosts)) if world.hosts else ""
