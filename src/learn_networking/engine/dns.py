"""DNS zones and resolution used by the simulated lab."""

from __future__ import annotations

from learn_networking.engine.addressing import IPv4, parse_address
from learn_networking.engine.topology import Host, NetworkWorld


class DNSFailure(Exception):
    """Raised when a name cannot be resolved."""


def add_record(world: NetworkWorld, zone: str, name: str, ip: str) -> str:
    """Add or replace an A record.

    Args:
        world: Lab world.
        zone: Zone name, e.g. ``internal`` or ``cluster.local``.
        name: Relative name (``api``) or FQDN under the zone.
        ip: IPv4 dotted-quad.

    Returns:
        The stored IP string.

    Raises:
        ValueError: If ``ip`` is not a valid IPv4 address.

    Examples:
        >>> from learn_networking.engine.topology import NetworkWorld
        >>> w = NetworkWorld()
        >>> add_record(w, "internal", "api", "10.0.2.10")
        '10.0.2.10'
    """
    parse_address(ip)  # validate
    records = world.dns_zones.setdefault(zone, {})
    key = _normalize_name(name, zone)
    records[key] = ip
    return ip


def delete_record(world: NetworkWorld, zone: str, name: str) -> bool:
    """Delete an A record if present.

    Args:
        world: Lab world.
        zone: Zone name.
        name: Record name.

    Returns:
        True if a record was removed.
    """
    records = world.dns_zones.get(zone, {})
    key = _normalize_name(name, zone)
    return records.pop(key, None) is not None


def _normalize_name(name: str, zone: str) -> str:
    """Normalize a record name to its FQDN under ``zone``.

    Args:
        name: Relative or absolute name.
        zone: Zone name.

    Returns:
        Fully-qualified name without trailing dot.
    """
    name = name.rstrip(".").lower()
    zone = zone.rstrip(".").lower()
    if name == zone or name.endswith("." + zone):
        return name
    return f"{name}.{zone}"


def resolve(
    world: NetworkWorld,
    host: Host | None,
    name: str,
) -> IPv4:
    """Resolve a DNS name from the perspective of ``host``.

    Resolution order:
        1. Host aliases (``/etc/hosts``, ``hosts`` file)
        2. Exact FQDN in any zone
        3. Search-domain expansion for short names

    Args:
        world: Lab world.
        host: Resolving host (for search domains / aliases), or None.
        name: Name to resolve (short or FQDN).

    Returns:
        Resolved IPv4 address.

    Raises:
        DNSFailure: If the name does not resolve.

    Examples:
        >>> from learn_networking.engine.topology import NetworkWorld, Host
        >>> w = NetworkWorld()
        >>> add_record(w, "internal", "api", "10.0.2.10")
        '10.0.2.10'
        >>> str(resolve(w, Host(name="c1"), "api.internal"))
        '10.0.2.10'
    """
    qname = name.rstrip(".").lower()

    # bare IPv4 short-circuit
    try:
        return parse_address(qname)
    except Exception:  # noqa: BLE001
        pass

    # inventory hostname (lab hostnames resolve without DNS)
    if world is not None:
        host_obj = world.hosts.get(qname)
        if host_obj is not None:
            ip = host_obj.primary_ip()
            if ip is not None:
                return ip

    if host is not None:
        alias = host.host_aliases.get(qname)
        if alias:
            return parse_address(alias)

    # exact FQDN across zones
    for zone, records in world.dns_zones.items():
        if qname in records:
            return parse_address(records[qname])
        # also allow bare relative match when query is short and zone matches
        fqdn = _normalize_name(qname, zone)
        if fqdn in records:
            return parse_address(records[fqdn])

    # search domains
    if host is not None:
        for domain in host.search_domains:
            fqdn = _normalize_name(qname, domain)
            for zone, records in world.dns_zones.items():
                if fqdn in records:
                    return parse_address(records[fqdn])
                if zone == domain.rstrip(".").lower() and fqdn in records:
                    return parse_address(records[fqdn])

    # last pass: any zone key ending with the query (wildcard-ish service names)
    for records in world.dns_zones.values():
        for key, ip in records.items():
            if key == qname or key.endswith("." + qname):
                return parse_address(ip)

    raise DNSFailure(f"NXDOMAIN: {name}")


def list_records(world: NetworkWorld) -> dict[str, dict[str, str]]:
    """Return all DNS records.

    Args:
        world: Lab world.

    Returns:
        Mapping of zone -> fqdn -> ip.
    """
    return {zone: dict(records) for zone, records in world.dns_zones.items()}
