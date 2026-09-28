"""Sequence metadata for the ``levels`` browser."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SequenceInfo:
    """Display metadata for a level sequence.

    Args:
        key: Sequence id.
        name: Display name.
        about: One-line description.
        order: Sort order in the catalog browser.
    """

    key: str
    name: str
    about: str
    order: int


SEQUENCES: dict[str, SequenceInfo] = {
    "link": SequenceInfo(
        key="link",
        name="Link & Addressing",
        about="Interfaces, IPs, CIDR, same-subnet reachability",
        order=1,
    ),
    "route": SequenceInfo(
        key="route",
        name="Routing",
        about="Default gateways and static routes across subnets",
        order=2,
    ),
    "dns": SequenceInfo(
        key="dns",
        name="DNS",
        about="A records and internal service names — how apps find each other",
        order=3,
    ),
    "ports": SequenceInfo(
        key="ports",
        name="Ports & HTTP",
        about="Listeners, health checks, and the curl / IWR workflow",
        order=4,
    ),
    "firewall": SequenceInfo(
        key="firewall",
        name="Firewall & Security Groups",
        about="Default-deny policies and allow-listing the right ports",
        order=5,
    ),
    "containers": SequenceInfo(
        key="containers",
        name="Container Networks",
        about="Docker-style bridges and published ports",
        order=6,
    ),
    "discovery": SequenceInfo(
        key="discovery",
        name="Service Discovery & LB",
        about="K8s-style ClusterIP DNS and load-balanced backends",
        order=7,
    ),
    "troubleshoot": SequenceInfo(
        key="troubleshoot",
        name="Incident Drill",
        about="Layered debugging: why the ETL job cannot reach Postgres",
        order=8,
    ),
}
