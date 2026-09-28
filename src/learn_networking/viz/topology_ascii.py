"""ASCII topology visualization for the lab."""

from __future__ import annotations

from learn_networking.engine.topology import LinkState, NetworkWorld


def render_topology(world: NetworkWorld) -> str:
    """Render hosts grouped by network segment.

    Args:
        world: Lab world.

    Returns:
        Multi-line ASCII map.

    Examples:
        >>> from learn_networking.engine.topology import NetworkWorld, Host
        >>> w = NetworkWorld()
        >>> print(render_topology(w)).splitlines()[0]
        'Network topology'
    """
    lines: list[str] = ["Network topology", "================", ""]

    # named segments
    for net_name, cidr in sorted(world.networks.items()):
        hosts = world.hosts_on_network(net_name)
        lines.append(f"[{net_name}]  {cidr}")
        if not hosts:
            lines.append("    (empty)")
            lines.append("")
            continue
        for host in hosts:
            addrs = []
            for iface in host.interfaces.values():
                if iface.network_name == net_name and iface.ip is not None:
                    state = "up" if iface.state == LinkState.UP else "down"
                    addrs.append(f"{iface.ip}/{iface.prefix}:{state}")
            mark = "W" if host.os.value == "windows" else "L"
            lines.append(f"    {mark}  {host.name:<16} {' '.join(addrs) or '-':<28} ({host.role})")
        lines.append("")

    # hosts with no network attachment
    orphans = [
        h
        for h in world.hosts.values()
        if not any(i.network_name for i in h.interfaces.values())
    ]
    if orphans:
        lines.append("[detached]")
        for host in orphans:
            mark = "W" if host.os.value == "windows" else "L"
            lines.append(f"    {mark}  {host.name:<16} ({host.role})")
        lines.append("")

    lines.append("Legend: L=linux  W=windows  ip/prefix:up|down")
    return "\n".join(lines)


def render_hosts(world: NetworkWorld) -> str:
    """Render a compact host inventory.

    Args:
        world: Lab world.

    Returns:
        Table-like text.
    """
    lines = ["HOST              OS        ROLE            PRIMARY IP"]
    lines.append("-" * 58)
    for name in sorted(world.hosts):
        host = world.hosts[name]
        ip = host.primary_ip() or "-"
        lines.append(f"{name:<17} {host.os.value:<9} {host.role:<15} {ip}")
    return "\n".join(lines)
