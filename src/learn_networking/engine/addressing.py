"""IPv4 addressing and CIDR helpers.

Pure functions and small value types used by the network simulation engine.
No I/O. No hidden state.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass


class AddressError(ValueError):
    """Raised when an IP or CIDR string is invalid."""


@dataclass(frozen=True, slots=True)
class IPv4:
    """A single IPv4 address.

    Args:
        value: Dotted-quad string, e.g. ``"10.0.0.5"``.

    Raises:
        AddressError: If ``value`` is not a valid IPv4 address.

    Examples:
        >>> addr = IPv4("10.0.0.5")
        >>> str(addr)
        '10.0.0.5'
    """

    value: ipaddress.IPv4Address

    def __init__(self, value: str | ipaddress.IPv4Address) -> None:
        try:
            parsed = (
                value
                if isinstance(value, ipaddress.IPv4Address)
                else ipaddress.IPv4Address(value)
            )
        except (ipaddress.AddressValueError, ValueError) as exc:
            raise AddressError(f"invalid IPv4 address: {value!r}") from exc
        object.__setattr__(self, "value", parsed)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"IPv4({str(self.value)!r})"

    @property
    def int(self) -> int:
        """Return the integer form of the address.

        Returns:
            The 32-bit unsigned integer representation.
        """
        return int(self.value)


@dataclass(frozen=True, slots=True)
class CIDR:
    """An IPv4 network in CIDR notation.

    Args:
        value: Network string, e.g. ``"10.0.0.0/24"``.

    Raises:
        AddressError: If ``value`` is not a valid IPv4 network.

    Examples:
        >>> net = CIDR("10.0.0.0/24")
        >>> "10.0.0.5" in net
        True
    """

    value: ipaddress.IPv4Network

    def __init__(self, value: str | ipaddress.IPv4Network) -> None:
        try:
            parsed = (
                value
                if isinstance(value, ipaddress.IPv4Network)
                else ipaddress.IPv4Network(value, strict=False)
            )
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as exc:
            raise AddressError(f"invalid IPv4 network: {value!r}") from exc
        object.__setattr__(self, "value", parsed)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"CIDR({str(self.value)!r})"

    def __contains__(self, item: object) -> bool:
        if isinstance(item, IPv4):
            return item.value in self.value
        if isinstance(item, str):
            try:
                return ipaddress.IPv4Address(item) in self.value
            except (ipaddress.AddressValueError, ValueError):
                return False
        return False

    @property
    def prefixlen(self) -> int:
        """Return the prefix length (e.g. 24 for /24)."""
        return self.value.prefixlen

    @property
    def network(self) -> IPv4:
        """Return the network address (host bits zero)."""
        return IPv4(self.value.network_address)

    @property
    def broadcast(self) -> IPv4:
        """Return the broadcast address."""
        return IPv4(self.value.broadcast_address)

    def is_host_in(self, addr: IPv4) -> bool:
        """Return whether ``addr`` falls inside this network.

        Args:
            addr: Address to test.

        Returns:
            True if the address is contained in this CIDR.
        """
        return addr.value in self.value

    def same_subnet(self, a: IPv4, b: IPv4) -> bool:
        """Return whether two addresses share this network.

        Args:
            a: First address.
            b: Second address.

        Returns:
            True if both addresses are in this network.
        """
        return self.is_host_in(a) and self.is_host_in(b)


def parse_address(value: str) -> IPv4:
    """Parse a dotted-quad IPv4 string.

    Args:
        value: Address text.

    Returns:
        Parsed address.

    Raises:
        AddressError: If the string is not a valid IPv4 address.

    Examples:
        >>> str(parse_address("192.168.1.10"))
        '192.168.1.10'
    """
    return IPv4(value)


def parse_cidr(value: str) -> CIDR:
    """Parse a CIDR network string.

    Args:
        value: Network text, e.g. ``"10.0.0.0/24"``.

    Returns:
        Parsed network.

    Raises:
        AddressError: If the string is not a valid IPv4 network.

    Examples:
        >>> str(parse_cidr("10.0.0.0/24"))
        '10.0.0.0/24'
    """
    return CIDR(value)


def ip_in_network(ip: str, network: str) -> bool:
    """Return whether an address string sits inside a network string.

    Args:
        ip: Dotted-quad address.
        network: CIDR network.

    Returns:
        True if ``ip`` is contained in ``network``.

    Raises:
        AddressError: If either argument is invalid.

    Examples:
        >>> ip_in_network("10.0.0.5", "10.0.0.0/24")
        True
        >>> ip_in_network("10.0.1.5", "10.0.0.0/24")
        False
    """
    return parse_cidr(network).is_host_in(parse_address(ip))
