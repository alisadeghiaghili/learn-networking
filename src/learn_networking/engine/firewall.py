"""Host firewall / security-group evaluation.

Rules are simple ordered filters. Default policy when enabled is deny for
inbound traffic that matches no allow rule (DevOps security-group mental model).
ICMP is treated as a pseudo-protocol with no port.
"""

from __future__ import annotations

from dataclasses import dataclass

from learn_networking.engine.addressing import CIDR, IPv4, parse_address, parse_cidr
from learn_networking.engine.topology import Host


@dataclass(frozen=True, slots=True)
class Rule:
    """A single firewall rule.

    Args:
        action: ``allow`` or ``deny``.
        proto: ``tcp``, ``udp``, ``icmp``, or ``any``.
        port: Destination port or None.
        src: Source CIDR string or ``"any"``.
        comment: Optional human label.
    """

    action: str
    proto: str = "any"
    port: int | None = None
    src: str = "any"
    comment: str = ""

    def matches(self, proto: str, port: int | None, src: IPv4) -> bool:
        """Return whether this rule matches a packet.

        Args:
            proto: Transport protocol of the packet.
            port: Destination port (None for ICMP).
            src: Source address.

        Returns:
            True if the rule applies.
        """
        if self.action not in ("allow", "deny"):
            return False
        if self.proto not in ("any", proto):
            return False
        if self.port is not None and port is not None and self.port != port:
            return False
        if self.port is not None and port is None:
            return False
        if self.src != "any":
            try:
                net = parse_cidr(self.src)
            except ValueError:
                return False
            if not net.is_host_in(src):
                return False
        return True

    def as_dict(self) -> dict:
        """Serialize the rule.

        Returns:
            JSON-friendly dict.
        """
        return {
            "action": self.action,
            "proto": self.proto,
            "port": self.port,
            "src": self.src,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        """Deserialize a rule.

        Args:
            data: Mapping with action/proto/port/src/comment.

        Returns:
            Constructed rule.
        """
        return cls(
            action=data.get("action", "deny"),
            proto=data.get("proto", "any"),
            port=data.get("port"),
            src=data.get("src", "any"),
            comment=data.get("comment", ""),
        )


def add_rule(host: Host, rule: Rule) -> Rule:
    """Append a firewall rule to a host.

    Args:
        host: Target host.
        rule: Rule to append.

    Returns:
        The appended rule.
    """
    host.firewall_rules.append(rule.as_dict())
    return rule


def clear_rules(host: Host) -> int:
    """Remove all firewall rules from a host.

    Args:
        host: Target host.

    Returns:
        Number of rules removed.
    """
    n = len(host.firewall_rules)
    host.firewall_rules.clear()
    return n


def set_enabled(host: Host, enabled: bool) -> bool:
    """Enable or disable the host firewall.

    Args:
        host: Target host.
        enabled: Desired state.

    Returns:
        The new state.
    """
    host.firewall_enabled = enabled
    return enabled


def evaluate(
    host: Host,
    proto: str,
    port: int | None,
    src: IPv4,
) -> tuple[bool, str]:
    """Decide whether inbound traffic is permitted.

    Args:
        host: Receiving host.
        proto: ``tcp``, ``udp``, or ``icmp``.
        port: Destination port (None for ICMP).
        src: Source address.

    Returns:
        Tuple of (permitted, reason).
    """
    if not host.firewall_enabled:
        return True, "firewall disabled"
    for raw in host.firewall_rules:
        rule = Rule.from_dict(raw)
        if rule.matches(proto, port, src):
            verb = "allowed" if rule.action == "allow" else "denied"
            label = rule.comment or f"{rule.action} {rule.proto}/{rule.port or '*'}"
            return rule.action == "allow", f"{verb} by rule: {label}"
    # default deny when firewall is on (security-group style)
    return False, "denied by default policy"


def rules_as_list(host: Host) -> list[dict]:
    """Return firewall rules as dicts.

    Args:
        host: Target host.

    Returns:
        List of rule mappings.
    """
    return [Rule.from_dict(r).as_dict() for r in host.firewall_rules]
