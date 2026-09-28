"""Network topology model: hosts, interfaces, links, and the world container.

The world is an explicit mutable aggregate. Callers mutate through documented
methods; there is no hidden global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from learn_networking.engine.addressing import CIDR, IPv4, AddressError, parse_address, parse_cidr

if TYPE_CHECKING:
    from learn_networking.engine.services import ServiceBinding


class HostOS(str, Enum):
    """Operating-system flavor of a simulated host."""

    LINUX = "linux"
    WINDOWS = "windows"


class LinkState(str, Enum):
    """Administrative / operational state of an interface."""

    DOWN = "down"
    UP = "up"


@dataclass
class Interface:
    """A network interface on a host.

    Args:
        name: Interface name (``eth0``, ``Ethernet0``).
        mac: Optional MAC string.
        state: Administrative state.

    Examples:
        >>> iface = Interface(name="eth0")
        >>> iface.ip is None
        True
    """

    name: str
    mac: str = "02:00:00:00:00:01"
    state: LinkState = LinkState.DOWN
    ip: IPv4 | None = None
    prefix: int = 24
    network_name: str | None = None

    @property
    def cidr(self) -> CIDR | None:
        """Return the interface network derived from IP + prefix, if any."""
        if self.ip is None:
            return None
        return CIDR(f"{self.ip}/{self.prefix}")

    def describe(self) -> str:
        """Return a one-line human description.

        Returns:
            Compact interface summary used by ``ip a`` / ``ipconfig``.
        """
        addr = f"{self.ip}/{self.prefix}" if self.ip else "no address"
        net = self.network_name or "-"
        return f"{self.name}: <{self.state.value}> {addr} net={net} mac={self.mac}"


@dataclass
class Host:
    """A simulated machine.

    Args:
        name: Hostname (unique in the world).
        os: Command dialect / platform flavor.
        role: Optional free-text role (``web``, ``db``, ``client``).

    Examples:
        >>> h = Host(name="web-01", os=HostOS.LINUX)
        >>> h.default_gateway is None
        True
    """

    name: str
    os: HostOS = HostOS.LINUX
    role: str = "generic"
    interfaces: dict[str, Interface] = field(default_factory=dict)
    default_gateway: IPv4 | None = None
    routes: dict[str, str] = field(default_factory=dict)  # cidr -> next-hop IP
    dns_servers: list[str] = field(default_factory=list)
    search_domains: list[str] = field(default_factory=list)
    firewall_enabled: bool = True
    # list of rule dicts: {action: allow|deny, proto: tcp|udp|icmp|any, port: int|None, src: cidr|any}
    firewall_rules: list[dict] = field(default_factory=list)
    services: dict[int, ServiceBinding] = field(default_factory=dict)  # port -> service
    host_aliases: dict[str, str] = field(default_factory=dict)  # /etc/hosts style
    vars: dict[str, str] = field(default_factory=dict)  # free-form (docker, k8s, etc.)

    def add_interface(self, iface: Interface) -> Interface:
        """Attach an interface to this host.

        Args:
            iface: Interface to store (keyed by name).

        Returns:
            The stored interface.

        Raises:
            ValueError: If an interface with the same name already exists.
        """
        if iface.name in self.interfaces:
            raise ValueError(f"interface already exists: {iface.name}")
        self.interfaces[iface.name] = iface
        return iface

    def primary_interface(self) -> Interface | None:
        """Return the first interface, preferring one with an IP.

        Returns:
            An interface, or None if the host has none.
        """
        if not self.interfaces:
            return None
        for iface in self.interfaces.values():
            if iface.ip is not None:
                return iface
        return next(iter(self.interfaces.values()))

    def primary_ip(self) -> IPv4 | None:
        """Return the primary IPv4 address if any.

        Returns:
            Primary address or None.
        """
        iface = self.primary_interface()
        return iface.ip if iface else None

    def has_ip(self, ip: IPv4 | str) -> bool:
        """Return whether this host owns the given address.

        Args:
            ip: Address to test.

        Returns:
            True if any interface holds the address.
        """
        target = ip if isinstance(ip, IPv4) else parse_address(str(ip))
        return any(i.ip == target for i in self.interfaces.values())


@dataclass
class Link:
    """An L2 attachment of an interface to a named network segment."""

    host: str
    interface: str
    network_name: str


@dataclass
class NetworkWorld:
    """The complete simulated lab.

    Args:
        hosts: Mapping of hostname to Host.
        links: L2 attachments.
        dns_zones: DNS zone store keyed by zone name.
        networks: Named L2/L3 segments (name -> CIDR).
    """

    hosts: dict[str, Host] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    dns_zones: dict[str, dict[str, str]] = field(default_factory=dict)  # zone -> name -> ip
    networks: dict[str, CIDR] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)

    def add_network(self, name: str, cidr: str | CIDR) -> CIDR:
        """Register a named network segment.

        Args:
            name: Segment name (``lan-a``, ``k8s-pods``).
            cidr: Network in CIDR form.

        Returns:
            The stored network.

        Raises:
            AddressError: If ``cidr`` is invalid.
            ValueError: If the name is already registered with a different CIDR.
        """
        net = cidr if isinstance(cidr, CIDR) else parse_cidr(cidr)
        existing = self.networks.get(name)
        if existing is not None and existing != net:
            raise ValueError(f"network {name!r} already defined as {existing}")
        self.networks[name] = net
        return net

    def add_host(self, host: Host) -> Host:
        """Add a host to the world.

        Args:
            host: Host to insert.

        Returns:
            The inserted host.

        Raises:
            ValueError: If the hostname is taken.
        """
        if host.name in self.hosts:
            raise ValueError(f"host already exists: {host.name}")
        self.hosts[host.name] = host
        return host

    def get_host(self, name: str) -> Host:
        """Look up a host by name.

        Args:
            name: Hostname.

        Returns:
            The host.

        Raises:
            KeyError: If no such host exists.
        """
        if name not in self.hosts:
            raise KeyError(f"unknown host: {name}")
        return self.hosts[name]

    def connect(
        self,
        host_name: str,
        interface_name: str,
        network_name: str,
        ip: str | None = None,
        prefix: int = 24,
        state: LinkState = LinkState.UP,
    ) -> Interface:
        """Attach a host interface to a named network and optionally address it.

        Args:
            host_name: Target host.
            interface_name: Interface to create or update.
            network_name: Segment name (must exist or is created if ``ip`` given).
            ip: Optional IPv4 to assign.
            prefix: Prefix length when assigning an address.
            state: Interface admin state.

        Returns:
            The connected interface.

        Raises:
            KeyError: If the host does not exist.
            AddressError: If ``ip`` is invalid.
        """
        host = self.get_host(host_name)
        if network_name not in self.networks:
            if ip is None:
                raise KeyError(f"unknown network: {network_name}")
            # derive a /prefix around the given ip as a convenience
            addr = parse_address(ip)
            self.add_network(network_name, f"{addr}/{prefix}")
        iface = host.interfaces.get(interface_name)
        if iface is None:
            iface = host.add_interface(Interface(name=interface_name))
        iface.network_name = network_name
        iface.state = state
        if ip is not None:
            iface.ip = parse_address(ip)
            iface.prefix = prefix
        # replace existing link for this iface
        self.links = [
            ln for ln in self.links if not (ln.host == host_name and ln.interface == interface_name)
        ]
        self.links.append(Link(host=host_name, interface=interface_name, network_name=network_name))
        return iface

    def hosts_on_network(self, network_name: str) -> list[Host]:
        """Return hosts that have an interface on the named segment.

        Args:
            network_name: Segment name.

        Returns:
            Hosts with at least one interface on that segment.
        """
        names = {ln.host for ln in self.links if ln.network_name == network_name}
        return [self.hosts[n] for n in sorted(names) if n in self.hosts]

    def find_host_by_ip(self, ip: IPv4 | str) -> Host | None:
        """Find the host owning an address.

        Args:
            ip: Address to resolve to a host.

        Returns:
            Matching host or None.
        """
        target = ip if isinstance(ip, IPv4) else parse_address(str(ip))
        for host in self.hosts.values():
            if host.has_ip(target):
                return host
        return None

    def export_snapshot(self) -> dict:
        """Export a JSON-serializable snapshot of the world.

        Returns:
            Nested dict suitable for level goals and undo.
        """
        return {
            "networks": {k: str(v) for k, v in sorted(self.networks.items())},
            "hosts": {
                name: {
                    "os": host.os.value,
                    "role": host.role,
                    "default_gateway": str(host.default_gateway) if host.default_gateway else None,
                    "routes": dict(sorted(host.routes.items())),
                    "dns_servers": list(host.dns_servers),
                    "search_domains": list(host.search_domains),
                    "firewall_enabled": host.firewall_enabled,
                    "firewall_rules": [dict(r) for r in host.firewall_rules],
                    "host_aliases": dict(sorted(host.host_aliases.items())),
                    "vars": dict(sorted(host.vars.items())),
                    "interfaces": {
                        iname: {
                            "state": iface.state.value,
                            "ip": str(iface.ip) if iface.ip else None,
                            "prefix": iface.prefix,
                            "network": iface.network_name,
                            "mac": iface.mac,
                        }
                        for iname, iface in sorted(host.interfaces.items())
                    },
                    "services": {
                        str(port): {
                            "proto": svc.proto,
                            "name": svc.name,
                            "banner": svc.banner,
                            "healthy": svc.healthy,
                        }
                        for port, svc in sorted(host.services.items())
                    },
                }
                for name, host in sorted(self.hosts.items())
            },
            "dns_zones": {
                zone: dict(sorted(records.items())) for zone, records in sorted(self.dns_zones.items())
            },
        }
