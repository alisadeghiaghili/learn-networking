"""Level schema, goal checks, and catalog loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from learn_networking.engine import dns as dns_mod
from learn_networking.engine import firewall as fw
from learn_networking.engine import reachability
from learn_networking.engine.addressing import parse_address, parse_cidr
from learn_networking.engine.topology import HostOS, Interface, LinkState, NetworkWorld
from learn_networking.engine.routing import set_default_gateway


class LevelError(ValueError):
    """Raised when a level definition is invalid or cannot be loaded."""


@dataclass(frozen=True, slots=True)
class GoalCheck:
    """One declarative win condition.

    Args:
        type: Predicate name (see ``evaluate_check``).
        params: Predicate parameters.
        description: Human label shown in ``goal``.
    """

    type: str
    params: dict[str, Any]
    description: str = ""

    def evaluate(self, world: NetworkWorld, current_host: str) -> tuple[bool, str]:
        """Evaluate this check against a world.

        Args:
            world: Current lab world.
            current_host: Name of the active host (for check scoping).

        Returns:
            Tuple of (passed, detail).
        """
        return evaluate_check(self, world, current_host)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the check.

        Returns:
            JSON-friendly mapping.
        """
        return {"type": self.type, "params": self.params, "description": self.description}


@dataclass
class Level:
    """A tutorial level.

    Args:
        id: Stable identifier.
        sequence: Sequence key (``link``, ``dns``, ...).
        name: Display title.
        objective: One-sentence goal.
        hint: Hint text.
        start: World builder payload (see ``build_world``).
        goal_checks: Win conditions (all must pass).
        solution_commands: Reference solution lines.
        par: Command-golf par (mutating commands only).
        os_focus: Which OS dialects the level emphasizes.
        disabled_commands: Prefixes blocked while solving.
    """

    id: str
    sequence: str
    name: str
    objective: str
    hint: str
    start: dict[str, Any]
    goal_checks: list[GoalCheck] = field(default_factory=list)
    solution_commands: list[str] = field(default_factory=list)
    solution_commands_linux: list[str] | None = None
    solution_commands_windows: list[str] | None = None
    par: int = 0
    os_focus: tuple[str, ...] = ("linux", "windows")
    disabled_commands: tuple[str, ...] = ()
    track: str = "both"
    steps: dict[str, list] = field(default_factory=dict)

    def build_world(self) -> NetworkWorld:
        """Materialize the starting world.

        Returns:
            A fresh NetworkWorld.

        Raises:
            LevelError: If the start payload is malformed.
        """
        return build_world(self.start)

    def check_goals(self, world: NetworkWorld, current_host: str) -> list[tuple[bool, str, GoalCheck]]:
        """Evaluate all goal checks.

        Args:
            world: Candidate world.
            current_host: Active host name.

        Returns:
            List of (passed, detail, check).
        """
        results = []
        for check in self.goal_checks:
            ok, detail = check.evaluate(world, current_host)
            results.append((ok, detail, check))
        return results

    def is_solved(self, world: NetworkWorld, current_host: str) -> bool:
        """Return whether every goal check passes.

        Args:
            world: Candidate world.
            current_host: Active host name.

        Returns:
            True if the level is solved.
        """
        return all(ok for ok, _, _ in self.check_goals(world, current_host))


def build_world(spec: dict[str, Any]) -> NetworkWorld:
    """Build a NetworkWorld from a level start spec.

    Spec shape::

        {
          "networks": {"lan-a": "10.0.0.0/24"},
          "hosts": {
            "web-01": {
              "os": "linux", "role": "web",
              "interfaces": {"eth0": {"network": "lan-a", "ip": "10.0.0.10", "prefix": 24, "state": "up"}},
              "default_gateway": "10.0.0.1",
              "routes": {"10.0.3.0/24": "10.0.0.1"},
              "dns_servers": ["10.0.0.53"],
              "search_domains": ["internal"],
              "firewall_enabled": true,
              "firewall_rules": [{"action": "allow", "proto": "tcp", "port": 22, "src": "any"}],
              "host_aliases": {"api.local": "10.0.0.10"},
              "vars": {"ip_forward": "0"},
              "services": {"80": {"proto": "tcp", "name": "http", "banner": "hi", "healthy": true}}
            }
          },
          "dns_zones": {"internal": {"api": "10.0.2.10"}}
        }

    Args:
        spec: Level start payload.

    Returns:
        Populated NetworkWorld.

    Raises:
        LevelError: If required keys are missing or values are invalid.
    """
    world = NetworkWorld()
    for name, cidr in (spec.get("networks") or {}).items():
        try:
            world.add_network(name, cidr)
        except Exception as exc:  # noqa: BLE001
            raise LevelError(f"bad network {name!r}: {exc}") from exc

    for hname, hspec in (spec.get("hosts") or {}).items():
        os_raw = str(hspec.get("os", "linux")).lower()
        try:
            host_os = HostOS(os_raw)
        except ValueError as exc:
            raise LevelError(f"bad os for {hname}: {os_raw}") from exc
        from learn_networking.engine.topology import Host

        host = Host(name=hname, os=host_os, role=hspec.get("role", "generic"))
        host.firewall_enabled = bool(hspec.get("firewall_enabled", True))
        host.host_aliases = dict(hspec.get("host_aliases") or {})
        host.vars = dict(hspec.get("vars") or {})
        host.dns_servers = list(hspec.get("dns_servers") or [])
        host.search_domains = list(hspec.get("search_domains") or [])
        host.routes = dict(hspec.get("routes") or {})
        for rule in hspec.get("firewall_rules") or []:
            host.firewall_rules.append(dict(rule))
        for iname, ispec in (hspec.get("interfaces") or {}).items():
            iface = Interface(name=iname)
            state = str(ispec.get("state", "up")).lower()
            iface.state = LinkState.UP if state == "up" else LinkState.DOWN
            iface.mac = ispec.get("mac", iface.mac)
            iface.network_name = ispec.get("network")
            if ispec.get("ip"):
                iface.ip = parse_address(str(ispec["ip"]))
                iface.prefix = int(ispec.get("prefix", 24))
            host.interfaces[iname] = iface
            if iface.network_name and iface.network_name not in world.networks and iface.ip:
                world.add_network(iface.network_name, f"{iface.ip}/{iface.prefix}")
            if iface.network_name:
                world.links.append(
                    __import__(
                        "learn_networking.engine.topology", fromlist=["Link"]
                    ).Link(host=hname, interface=iname, network_name=iface.network_name)
                )
        if hspec.get("default_gateway"):
            set_default_gateway(host, str(hspec["default_gateway"]))
        for port, sspec in (hspec.get("services") or {}).items():
            from learn_networking.engine.services import ServiceBinding

            svc = ServiceBinding(
                proto=sspec.get("proto", "tcp"),
                name=sspec.get("name", "svc"),
                banner=sspec.get("banner", "ok"),
                healthy=bool(sspec.get("healthy", True)),
                port=int(port),
            )
            host.services[int(port)] = svc
        world.add_host(host)

    for zone, records in (spec.get("dns_zones") or {}).items():
        for rname, rip in records.items():
            dns_mod.add_record(world, zone, rname, str(rip))

    return world


def evaluate_check(check: GoalCheck, world: NetworkWorld, current_host: str) -> tuple[bool, str]:
    """Evaluate a single goal predicate.

    Supported types:
        - ``dns_resolves``: {host, name, ip}
        - ``has_ip``: {host, iface, ip, prefix?}
        - ``iface_up``: {host, iface}
        - ``route_exists``: {host, dest, via}
        - ``default_gateway``: {host, gateway}
        - ``listening``: {host, port, proto?=tcp}
        - ``firewall_allows``: {host, proto, port, src}
        - ``firewall_denies``: {host, proto, port, src}
        - ``ping_ok``: {source, target}
        - ``ping_fail``: {source, target}
        - ``tcp_ok``: {source, target, port}
        - ``tcp_fail``: {source, target, port}
        - ``http_status``: {source, target, port?, path?, status}
        - ``http_body_contains``: {source, target, port?, path?, text}
        - ``host_var``: {host, key, value}
        - ``os_is``: {host, os}

    Args:
        check: The goal check.
        world: Candidate world.
        current_host: Active host name (fallback when check omits host).

    Returns:
        Tuple of (passed, detail).
    """
    p = check.params
    t = check.type

    def h(key: str = "host"):
        name = p.get(key) or current_host
        return world.get_host(name)

    try:
        if t == "dns_resolves":
            ip = dns_mod.resolve(world, h(), str(p["name"]))
            want = str(p["ip"])
            ok = str(ip) == want
            return ok, f"dns {p['name']} -> {ip} (want {want})"

        if t == "has_ip":
            iface = h().interfaces.get(str(p.get("iface", "")))
            if not iface and p.get("iface"):
                return False, f"no iface {p['iface']}"
            target_iface = iface or h().primary_interface()
            if target_iface is None or target_iface.ip is None:
                return False, "no address on interface"
            want = parse_address(str(p["ip"]))
            ok = target_iface.ip == want
            if ok and p.get("prefix") is not None:
                ok = target_iface.prefix == int(p["prefix"])
            return ok, f"iface addr {target_iface.ip}/{target_iface.prefix} (want {want})"

        if t == "iface_up":
            iface = h().interfaces.get(str(p["iface"]))
            if iface is None:
                return False, f"missing iface {p['iface']}"
            ok = iface.state == LinkState.UP
            return ok, f"{iface.name} is {iface.state.value}"

        if t == "route_exists":
            dest = str(p["dest"])
            via = str(p["via"])
            host = h()
            stored = host.routes.get(dest) or host.routes.get(str(parse_cidr(dest)))
            ok = stored == via
            return ok, f"route {dest} via {stored} (want {via})"

        if t == "default_gateway":
            host = h()
            want = str(p["gateway"])
            got = str(host.default_gateway) if host.default_gateway else None
            return got == want, f"default gw {got} (want {want})"

        if t == "listening":
            host = h()
            port = int(p["port"])
            svc = host.services.get(port)
            ok = svc is not None and svc.proto == p.get("proto", "tcp")
            return ok, f"{host.name}:{port} {'listening' if ok else 'not listening'}"

        if t == "firewall_allows":
            allowed, reason = fw.evaluate(h(), str(p.get("proto", "tcp")), p.get("port"), parse_address(str(p.get("src", "0.0.0.0"))))
            return allowed, reason

        if t == "firewall_denies":
            allowed, reason = fw.evaluate(h(), str(p.get("proto", "tcp")), p.get("port"), parse_address(str(p.get("src", "0.0.0.0"))))
            return (not allowed), reason

        if t == "ping_ok":
            res = reachability.ping(world, world.get_host(str(p["source"])), _ip_of(world, str(p["target"])))
            return res.ok, res.describe()

        if t == "ping_fail":
            res = reachability.ping(world, world.get_host(str(p["source"])), _ip_of(world, str(p["target"])))
            return (not res.ok), res.describe()

        if t == "tcp_ok":
            res = reachability.tcp_connect(world, world.get_host(str(p["source"])), str(p["target"]), int(p["port"]))
            return res.ok, res.describe()

        if t == "tcp_fail":
            res = reachability.tcp_connect(world, world.get_host(str(p["source"])), str(p["target"]), int(p["port"]))
            return (not res.ok), res.describe()

        if t == "http_status":
            _, status, _body = reachability.http_get(
                world,
                world.get_host(str(p["source"])),
                str(p["target"]),
                port=int(p.get("port", 80)),
                path=str(p.get("path", "/")),
            )
            want = int(p["status"])
            return status == want, f"HTTP {status} (want {want})"

        if t == "http_body_contains":
            _res, _status, body = reachability.http_get(
                world,
                world.get_host(str(p["source"])),
                str(p["target"]),
                port=int(p.get("port", 80)),
                path=str(p.get("path", "/")),
            )
            text = str(p["text"])
            return text in body, f"body={body!r} contains {text!r}={text in body}"

        if t == "host_var":
            host = h()
            got = host.vars.get(str(p["key"]))
            want = str(p["value"])
            return got == want, f"var {p['key']}={got!r} (want {want!r})"

        if t == "os_is":
            host = h()
            want = str(p["os"]).lower()
            return host.os.value == want, f"os={host.os.value} (want {want})"

        return False, f"unknown check type: {t}"
    except Exception as exc:  # noqa: BLE001
        return False, f"check error: {exc}"


def _ip_of(world: NetworkWorld, target: str) -> str:
    """Resolve a target to an IP string for reachability checks.

    Args:
        world: Lab world.
        target: Hostname or IP.

    Returns:
        IP string.

    Raises:
        dns_mod.DNSFailure: If the name does not resolve.
        Exception: If the IP is invalid.
    """
    try:
        return str(parse_address(target))
    except Exception:  # noqa: BLE001
        return str(dns_mod.resolve(world, None, target))


def load_level(path: Path) -> Level:
    """Load a level from a JSON file.

    Args:
        path: Path to ``.json`` level file.

    Returns:
        Parsed Level.

    Raises:
        LevelError: If the file is invalid.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LevelError(f"cannot load level {path}: {exc}") from exc
    return level_from_dict(data)


def level_from_dict(data: dict[str, Any]) -> Level:
    """Construct a Level from a mapping.

    Args:
        data: Level payload.

    Returns:
        Parsed Level.

    Raises:
        LevelError: If required fields are missing.
    """
    required = ("id", "sequence", "name", "objective", "start")
    for key in required:
        if key not in data:
            raise LevelError(f"level missing field: {key}")
    checks = [
        GoalCheck(
            type=c["type"],
            params=dict(c.get("params") or {}),
            description=c.get("description", ""),
        )
        for c in data.get("goal_checks") or []
    ]
    return Level(
        id=str(data["id"]),
        sequence=str(data["sequence"]),
        name=str(data["name"]),
        objective=str(data["objective"]),
        hint=str(data.get("hint", "")),
        start=dict(data["start"]),
        goal_checks=checks,
        solution_commands=list(data.get("solution_commands") or []),
        solution_commands_linux=list(data["solution_commands_linux"])
        if data.get("solution_commands_linux")
        else None,
        solution_commands_windows=list(data["solution_commands_windows"])
        if data.get("solution_commands_windows")
        else None,
        par=int(data.get("par", 0)),
        os_focus=tuple(data.get("os_focus") or ("linux", "windows")),
        disabled_commands=tuple(data.get("disabled_commands") or ()),
        track=str(data.get("track") or "both"),
        steps=dict(data.get("steps") or {}),
    )


def load_catalog(directory: Path | None = None) -> dict[str, Level]:
    """Load every level JSON from the data directory.

    Args:
        directory: Defaults to ``.../levels/data``.

    Returns:
        Mapping of level id -> Level.

    Raises:
        LevelError: If any file is invalid.
    """
    if directory is None:
        directory = Path(__file__).resolve().parent / "data"
    catalog: dict[str, Level] = {}
    for path in sorted(directory.glob("*.json")):
        level = load_level(path)
        catalog[level.id] = level
    return catalog
