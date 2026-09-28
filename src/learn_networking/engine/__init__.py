"""Network simulation engine (pure)."""

from learn_networking.engine.addressing import (
    AddressError,
    CIDR,
    IPv4,
    ip_in_network,
    parse_address,
    parse_cidr,
)
from learn_networking.engine.dns import DNSFailure, add_record, delete_record, list_records, resolve
from learn_networking.engine.firewall import Rule, add_rule, clear_rules, evaluate, rules_as_list, set_enabled
from learn_networking.engine.reachability import ProbeResult, http_get, ping, tcp_connect
from learn_networking.engine.routing import (
    add_route,
    connected_networks,
    delete_route,
    lookup_route,
    route_table,
    set_default_gateway,
)
from learn_networking.engine.services import ServiceBinding
from learn_networking.engine.topology import Host, HostOS, Interface, Link, LinkState, NetworkWorld

__all__ = [
    "AddressError",
    "CIDR",
    "DNSFailure",
    "Host",
    "HostOS",
    "Interface",
    "IPv4",
    "Link",
    "LinkState",
    "NetworkWorld",
    "ProbeResult",
    "Rule",
    "ServiceBinding",
    "add_record",
    "add_route",
    "add_rule",
    "clear_rules",
    "connected_networks",
    "delete_record",
    "delete_route",
    "evaluate",
    "http_get",
    "ip_in_network",
    "list_records",
    "lookup_route",
    "parse_address",
    "parse_cidr",
    "ping",
    "resolve",
    "route_table",
    "rules_as_list",
    "set_default_gateway",
    "set_enabled",
    "tcp_connect",
]
