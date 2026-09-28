"""Tests for IPv4 / CIDR helpers."""

from __future__ import annotations

import pytest

from learn_networking.engine.addressing import (
    AddressError,
    IPv4,
    ip_in_network,
    parse_address,
    parse_cidr,
)


def test_parse_address() -> None:
    assert str(parse_address("10.0.0.5")) == "10.0.0.5"


def test_parse_address_rejects_junk() -> None:
    with pytest.raises(AddressError):
        parse_address("not-an-ip")


def test_cidr_contains() -> None:
    net = parse_cidr("10.0.0.0/24")
    assert "10.0.0.5" in net
    assert "10.0.1.5" not in net


def test_ip_in_network() -> None:
    assert ip_in_network("192.168.1.10", "192.168.1.0/24")
    assert not ip_in_network("192.168.2.10", "192.168.1.0/24")


def test_prefixlen() -> None:
    assert parse_cidr("10.0.0.0/16").prefixlen == 16


def test_ipv4_int_roundtrip() -> None:
    addr = IPv4("0.0.0.1")
    assert addr.int == 1
