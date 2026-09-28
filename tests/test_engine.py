"""Tests for topology, routing, DNS, firewall, and reachability."""

from __future__ import annotations

import pytest

from learn_networking.engine import dns as dns_mod
from learn_networking.engine import firewall as fw
from learn_networking.engine import reachability, routing
from learn_networking.engine.addressing import parse_address
from learn_networking.engine.services import ServiceBinding
from learn_networking.engine.topology import Host, HostOS, NetworkWorld


def test_connect_assigns_ip(lab: NetworkWorld) -> None:
    web = lab.get_host("web-01")
    assert web.primary_ip() is not None
    assert str(web.primary_ip()) == "10.0.0.10"


def test_ping_same_subnet(lab: NetworkWorld) -> None:
    client = lab.get_host("client-01")
    result = reachability.ping(lab, client, "10.0.0.10")
    assert result.ok


def test_firewall_default_deny() -> None:
    world = NetworkWorld()
    world.add_network("lab", "10.0.0.0/24")
    a = Host(name="a", os=HostOS.LINUX)
    b = Host(name="b", os=HostOS.LINUX)
    world.add_host(a)
    world.add_host(b)
    world.connect("a", "eth0", "lab", ip="10.0.0.1", prefix=24)
    world.connect("b", "eth0", "lab", ip="10.0.0.2", prefix=24)
    b.firewall_enabled = True
    b.services[22] = ServiceBinding(proto="tcp", name="ssh")
    assert not reachability.tcp_connect(world, a, "10.0.0.2", 22).ok
    fw.add_rule(b, fw.Rule(action="allow", proto="tcp", port=22, src="any"))
    assert reachability.tcp_connect(world, a, "10.0.0.2", 22).ok


def test_dns_resolve_and_hosts() -> None:
    world = NetworkWorld()
    dns_mod.add_record(world, "internal", "api", "10.0.2.10")
    host = Host(name="c", search_domains=["internal"])
    assert str(dns_mod.resolve(world, host, "api.internal")) == "10.0.2.10"
    assert str(dns_mod.resolve(world, host, "api")) == "10.0.2.10"
    host.host_aliases["special.local"] = "10.0.0.1"
    assert str(dns_mod.resolve(world, host, "special.local")) == "10.0.0.1"
    with pytest.raises(dns_mod.DNSFailure):
        dns_mod.resolve(world, host, "nope.internal")


def test_default_route_lookup() -> None:
    host = Host(name="c")
    routing.set_default_gateway(host, "10.0.0.1")
    assert routing.lookup_route(host, parse_address("8.8.8.8")) == "10.0.0.1"
    routing.add_route(host, "10.0.3.0/24", "10.0.0.9")
    assert routing.lookup_route(host, parse_address("10.0.3.7")) == "10.0.0.9"


def test_http_health() -> None:
    world = NetworkWorld()
    world.add_network("lab", "10.0.0.0/24")
    client = Host(name="c", os=HostOS.LINUX)
    server = Host(name="s", os=HostOS.LINUX)
    world.add_host(client)
    world.add_host(server)
    world.connect("c", "eth0", "lab", ip="10.0.0.2", prefix=24)
    world.connect("s", "eth0", "lab", ip="10.0.0.1", prefix=24)
    client.firewall_enabled = False
    server.firewall_enabled = False
    server.services[8080] = ServiceBinding(proto="tcp", name="http", banner="up", healthy=False)
    _res, status, _body = reachability.http_get(world, client, "10.0.0.1", port=8080, path="/health")
    assert status == 503
    server.services[8080].healthy = True
    _res, status, body = reachability.http_get(world, client, "10.0.0.1", port=8080, path="/health")
    assert status == 200
    assert body == "ok"
