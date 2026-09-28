"""Shared test fixtures."""

from __future__ import annotations

import pytest

from learn_networking.engine.addressing import parse_address
from learn_networking.engine.services import ServiceBinding
from learn_networking.engine.topology import Host, HostOS, NetworkWorld
from learn_networking.session import Session


@pytest.fixture
def lab() -> NetworkWorld:
    """Build a small two-host lab on one segment.

    Returns:
        NetworkWorld with web-01 and client-01.
    """
    world = NetworkWorld()
    world.add_network("lab", "10.0.0.0/24")
    web = Host(name="web-01", os=HostOS.LINUX, role="web")
    world.add_host(web)
    world.connect("web-01", "eth0", "lab", ip="10.0.0.10", prefix=24)
    web.services[80] = ServiceBinding(proto="tcp", name="http", banner="hi", healthy=True)
    web.firewall_enabled = False

    client = Host(name="client-01", os=HostOS.LINUX, role="client")
    world.add_host(client)
    world.connect("client-01", "eth0", "lab", ip="10.0.0.30", prefix=24)
    client.firewall_enabled = False
    client.default_gateway = parse_address("10.0.0.1")
    return world


@pytest.fixture
def session() -> Session:
    """Sandbox session for command tests.

    Returns:
        Fresh Session in sandbox mode.
    """
    return Session()
