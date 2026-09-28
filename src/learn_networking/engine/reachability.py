"""Path evaluation: can a host reach another host/service?

Layered checks mirror how a DevOps engineer debugs:

1. Addressing / same segment or routed path (L3)
2. Host is up / interface up
3. Firewall on the receiver (and optionally sender)
4. Listening service (L4)
5. Application health (L7)
"""

from __future__ import annotations

from dataclasses import dataclass

from learn_networking.engine import firewall as fw
from learn_networking.engine import routing
from learn_networking.engine.addressing import IPv4, parse_address
from learn_networking.engine.dns import DNSFailure, resolve
from learn_networking.engine.topology import Host, LinkState, NetworkWorld


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Outcome of a connectivity probe.

    Args:
        ok: Whether the probe succeeded.
        layer: OSI-ish layer name where it succeeded/failed.
        reason: Human explanation.
        path: Optional hop list (hostnames).
    """

    ok: bool
    layer: str
    reason: str
    path: tuple[str, ...] = ()

    def describe(self) -> str:
        """Return a one-line description.

        Returns:
            e.g. ``"FAIL@L4: connection refused"``
        """
        status = "OK" if self.ok else "FAIL"
        path = " -> ".join(self.path) if self.path else ""
        suffix = f" [{path}]" if path else ""
        return f"{status}@{self.layer}: {self.reason}{suffix}"


def _interface_up_toward(host: Host, dest: IPv4) -> bool:
    """Return whether some interface with an IP can send toward dest.

    Args:
        host: Source host.
        dest: Destination address.

    Returns:
        True if an up interface exists with a route or connected net.
    """
    for iface in host.interfaces.values():
        if iface.state != LinkState.UP or iface.ip is None:
            continue
        if iface.cidr is not None and iface.cidr.is_host_in(dest):
            return True
        if host.default_gateway is not None or host.routes:
            return True
    return False


def ping(
    world: NetworkWorld,
    source: Host,
    target_ip: str,
    count: int = 3,
) -> ProbeResult:
    """Simulate ICMP echo.

    Args:
        world: Lab world.
        source: Pinging host.
        target_ip: Destination IPv4.
        count: Echo count (cosmetic; result is aggregated).

    Returns:
        Probe result at L3 (ICMP).

    Raises:
        ValueError: If ``target_ip`` is invalid.

    Examples:
        >>> # see tests for full lab fixtures
        >>> ProbeResult(True, "L3", "ok").ok
        True
    """
    dest = parse_address(target_ip)
    dest_host = world.find_host_by_ip(dest)

    if dest_host is None:
        return ProbeResult(False, "L3", f"no host owns {dest}", (source.name,))

    if not _interface_up_toward(source, dest):
        return ProbeResult(False, "L3", f"{source.name} has no up interface toward {dest}", (source.name,))

    hop = routing.lookup_route(source, dest)
    if hop is None:
        return ProbeResult(False, "L3", f"no route from {source.name} to {dest}", (source.name,))

    # if next hop is not local and not the dest, require that hop to exist
    if hop != "on-link":
        hop_ip = parse_address(hop)
        if not dest_host.has_ip(hop_ip) and not source.has_ip(hop_ip):
            hop_host = world.find_host_by_ip(hop_ip)
            if hop_host is None:
                return ProbeResult(False, "L3", f"next hop {hop} unreachable", (source.name,))
            # hop must have a route to dest too (simple one-hop model + recursive)
            nested = ping(world, hop_host, str(dest))
            if not nested.ok:
                return nested

    # L2 same segment shortcut: both on a shared network name
    same_segment = _share_network(world, source, dest_host)
    if not same_segment and hop is not None:
        # routed: accept if we got a hop and dest exists
        pass

    allowed, reason = fw.evaluate(dest_host, "icmp", None, source.primary_ip() or dest)
    if not allowed:
        return ProbeResult(False, "L3", f"icmp blocked: {reason}", (source.name, dest_host.name))

    return ProbeResult(True, "L3", f"echo reply from {dest}", (source.name, dest_host.name))


def _share_network(world: NetworkWorld, a: Host, b: Host) -> bool:
    """Return whether two hosts share at least one named segment.

    Args:
        world: Lab world.
        a: First host.
        b: Second host.

    Returns:
        True if they share a network name.
    """
    a_nets = {i.network_name for i in a.interfaces.values() if i.network_name}
    b_nets = {i.network_name for i in b.interfaces.values() if i.network_name}
    return bool(a_nets & b_nets)


def tcp_connect(
    world: NetworkWorld,
    source: Host,
    target: str,
    port: int,
) -> ProbeResult:
    """Simulate a TCP connect to host-or-ip:port.

    Args:
        world: Lab world.
        source: Connecting host.
        target: Hostname or IPv4 of the destination.
        port: Destination port.

    Returns:
        Probe result at L4 (or earlier layer on failure).
    """
    try:
        dest_ip = resolve(world, source, target)
    except DNSFailure as exc:
        return ProbeResult(False, "DNS", str(exc), (source.name,))

    ping_res = ping(world, source, str(dest_ip))
    if not ping_res.ok:
        # TCP can still work if only ICMP is blocked; do L3 route check without ICMP
        dest = parse_address(str(dest_ip))
        dest_host = world.find_host_by_ip(dest)
        if dest_host is None:
            return ping_res
        hop = routing.lookup_route(source, dest)
        if hop is None:
            return ProbeResult(False, "L3", f"no route from {source.name} to {dest}", (source.name,))
    else:
        dest_host = world.find_host_by_ip(dest_ip)

    if dest_host is None:
        return ProbeResult(False, "L3", f"no host owns {dest_ip}", (source.name,))

    allowed, reason = fw.evaluate(dest_host, "tcp", port, source.primary_ip() or dest_ip)
    if not allowed:
        return ProbeResult(False, "L4", f"filtered: {reason}", (source.name, dest_host.name))

    svc = dest_host.services.get(port)
    if svc is None or svc.proto != "tcp":
        return ProbeResult(
            False,
            "L4",
            f"connection refused — nothing listening on {dest_host.name}:{port}",
            (source.name, dest_host.name),
        )

    return ProbeResult(True, "L4", f"connected to {dest_host.name}:{port} ({svc.name})", (source.name, dest_host.name))


def http_get(
    world: NetworkWorld,
    source: Host,
    target: str,
    port: int = 80,
    path: str = "/",
) -> tuple[ProbeResult, int | None, str]:
    """Simulate an HTTP GET.

    Args:
        world: Lab world.
        source: Client host.
        target: Hostname or IP.
        port: TCP port.
        path: Request path.

    Returns:
        Tuple of (probe, status_code or None, body or reason).
    """
    conn = tcp_connect(world, source, target, port)
    if not conn.ok:
        return conn, None, conn.reason
    dest_ip = resolve(world, source, target)
    dest_host = world.find_host_by_ip(dest_ip)
    if dest_host is None:
        return conn, None, "lost host"
    svc = dest_host.services.get(port)
    if svc is None:
        return conn, None, "no service"
    status, body = svc.respond_http(path)
    ok = 200 <= status < 400
    return (
        ProbeResult(ok, "L7", f"HTTP {status} from {dest_host.name}{path}", conn.path),
        status,
        body,
    )
