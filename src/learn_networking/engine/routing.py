"""Routing decisions for the simulated lab."""

from __future__ import annotations

from learn_networking.engine.addressing import CIDR, IPv4, parse_address, parse_cidr
from learn_networking.engine.topology import Host, NetworkWorld


def add_route(host: Host, destination: str, next_hop: str) -> tuple[str, str]:
    """Install a static route on a host.

    Args:
        host: Target host.
        destination: Destination CIDR (e.g. ``"10.0.3.0/24"``).
        next_hop: Next-hop IPv4.

    Returns:
        The (destination, next_hop) pair as stored.

    Raises:
        AddressError: If destination or next hop is invalid.

    Examples:
        >>> from learn_networking.engine.topology import Host
        >>> h = Host(name="r1")
        >>> add_route(h, "10.0.3.0/24", "10.0.0.1")
        ('10.0.3.0/24', '10.0.0.1')
    """
    if destination in ("default", "0.0.0.0/0"):
        return set_default_gateway(host, next_hop), "0.0.0.0/0"  # type: ignore[return-value]
    if destination in ("default", "0.0.0.0/0"):
        return set_default_gateway(host, next_hop)
    dest = str(parse_cidr(destination))
    hop = str(parse_address(next_hop))
    host.routes[dest] = hop
    return dest, hop


def delete_route(host: Host, destination: str) -> bool:
    """Remove a static route.

    Args:
        host: Target host.
        destination: Destination CIDR string.

    Returns:
        True if a route was removed.
    """
    dest = str(parse_cidr(destination))
    return host.routes.pop(dest, None) is not None


def set_default_gateway(host: Host, gateway: str) -> tuple[str, str]:
    """Set the default gateway (0.0.0.0/0 next hop).

    Args:
        host: Target host.
        gateway: Next-hop IPv4.

    Returns:
        The (destination, next_hop) pair as stored.

    Raises:
        AddressError: If gateway is not a valid IPv4 address.
    """
    gw = str(parse_address(gateway))
    host.default_gateway = parse_address(gw)
    host.routes["0.0.0.0/0"] = gw
    return ("0.0.0.0/0", gw)


def lookup_route(host: Host, destination: IPv4) -> str | None:
    """Find the next hop for a destination.

    Preference order:
        1. Connected interfaces (on-link, returns ``"on-link"``)
        2. Longest-prefix static route
        3. Default gateway

    Args:
        host: Source host.
        destination: Destination address.

    Returns:
        Next-hop IP string, ``"on-link"`` for directly connected, or None.
    """
    best_connected: tuple[int, str] | None = None
    for iface in host.interfaces.values():
        if iface.ip is None or iface.cidr is None:
            continue
        if iface.cidr.is_host_in(destination):
            if best_connected is None or iface.prefix > best_connected[0]:
                best_connected = (iface.prefix, "on-link")
    if best_connected is not None:
        return best_connected[1]

    best: tuple[int, str] | None = None
    for dest, hop in host.routes.items():
        net = parse_cidr(dest)
        if net.is_host_in(destination):
            if best is None or net.prefixlen > best[0]:
                best = (net.prefixlen, hop)
    if best is not None:
        return best[1]
    if host.default_gateway is not None:
        return str(host.default_gateway)
    return None


def route_table(host: Host) -> list[tuple[str, str, str]]:
    """Return the host routing table as rows.

    Args:
        host: Target host.

    Returns:
        List of (destination, next_hop, source) where source is
        ``iface``, ``static``, or ``default``.
    """
    rows: list[tuple[str, str, str]] = []
    for iface in host.interfaces.values():
        if iface.ip is not None and iface.cidr is not None:
            rows.append((str(iface.cidr), "0.0.0.0", f"iface:{iface.name}"))
    for dest, hop in sorted(host.routes.items()):
        if dest == "0.0.0.0/0":
            continue
        rows.append((dest, hop, "static"))
    if host.default_gateway is not None:
        rows.append(("0.0.0.0/0", str(host.default_gateway), "default"))
    return rows


def connected_networks(world: NetworkWorld, host: Host) -> list[tuple[str, CIDR]]:
    """Return directly connected networks for a host.

    Args:
        world: Lab world (for named segments).
        host: Target host.

    Returns:
        List of (network_name, cidr).
    """
    result: list[tuple[str, CIDR]] = []
    for iface in host.interfaces.values():
        if iface.ip is None or iface.cidr is None:
            continue
        if iface.network_name and iface.network_name in world.networks:
            result.append((iface.network_name, world.networks[iface.network_name]))
        else:
            result.append((iface.name, iface.cidr))
    return result
