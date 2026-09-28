"""Windows command surface (ipconfig, route, Test-NetConnection, Resolve-DnsName...)."""

from __future__ import annotations

import re

from learn_networking.commands.router import CommandContext, CommandResult
from learn_networking.engine import dns as dns_mod
from learn_networking.engine import firewall as fw
from learn_networking.engine import reachability
from learn_networking.engine import routing
from learn_networking.engine.addressing import parse_address
from learn_networking.engine.topology import LinkState


def _host(ctx: CommandContext):
    return ctx.session.current_host()


def cmd_ipconfig(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``ipconfig`` / ``ipconfig /all``."""
    host = _host(ctx)
    lines = [
        "Windows IP Configuration",
        "",
    ]
    for iface in host.interfaces.values():
        lines.append(f"Ethernet adapter {iface.name}:")
        lines.append("")
        lines.append(f"   Connection-specific DNS Suffix  . : {host.search_domains[0] if host.search_domains else ''}")
        lines.append(f"   Link-local IPv6 Address . . . . . : fe80::1%{iface.name}")
        if iface.ip:
            lines.append(f"   IPv4 Address. . . . . . . . . . . : {iface.ip}")
            mask = _prefix_to_mask(iface.prefix)
            lines.append(f"   Subnet Mask . . . . . . . . . . . : {mask}")
        else:
            lines.append("   Media State . . . . . . . . . . . : Media disconnected")
        if host.default_gateway:
            lines.append(f"   Default Gateway . . . . . . . . . : {host.default_gateway}")
        lines.append("")
    return CommandResult.out("\n".join(lines))


def _prefix_to_mask(prefix: int) -> str:
    """Convert a prefix length to a dotted-quad netmask.

    Args:
        prefix: Prefix length 0-32.

    Returns:
        Dotted-quad netmask.

    Examples:
        >>> _prefix_to_mask(24)
        '255.255.255.0'
    """
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix else 0
    return ".".join(str((mask >> (8 * (3 - i))) & 0xFF) for i in range(4))


def cmd_new_netipaddress(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``New-NetIPAddress -InterfaceAlias eth0 -IPAddress 10.0.0.5 -PrefixLength 24``."""
    host = _host(ctx)
    joined = " ".join(argv)

    def flag(name: str) -> str | None:
        m = re.search(rf"-{name}\s+(\S+)", joined, flags=re.I)
        return m.group(1) if m else None

    iface_name = flag("InterfaceAlias") or flag("InterfaceIndex")
    ip = flag("IPAddress")
    prefix = flag("PrefixLength") or "24"
    if not iface_name or not ip:
        return CommandResult.fail(
            "usage: New-NetIPAddress -InterfaceAlias <name> -IPAddress <ip> -PrefixLength <n>"
        )
    from learn_networking.engine.topology import Interface

    iface = host.interfaces.get(iface_name)
    if iface is None:
        iface = host.add_interface(Interface(name=iface_name))
    iface.ip = parse_address(ip)
    iface.prefix = int(prefix)
    iface.state = LinkState.UP
    return CommandResult.out(
        f"IPAddress    : {ip}\nInterfaceAlias : {iface_name}\nPrefixLength   : {prefix}",
        mutated=True,
    )


def cmd_new_netroute(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``New-NetRoute -DestinationPrefix 10.0.3.0/24 -NextHop 10.0.0.1``."""
    joined = " ".join(argv)

    def flag(name: str) -> str | None:
        m = re.search(rf"-{name}\s+(\S+)", joined, flags=re.I)
        return m.group(1) if m else None

    dest = flag("DestinationPrefix")
    hop = flag("NextHop")
    if not dest or not hop:
        return CommandResult.fail("usage: New-NetRoute -DestinationPrefix <cidr> -NextHop <ip>")
    routing.add_route(_host(ctx), dest, hop)
    return CommandResult.out(f"DestinationPrefix : {dest}\nNextHop           : {hop}", mutated=True)


def cmd_route(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``route print`` and ``route add``."""
    host = _host(ctx)
    if len(argv) >= 2 and argv[1] == "print":
        rows = routing.route_table(host)
        lines = [
            "===========================================================================",
            "Interface List",
            "===========================================================================",
            "Network Destination        Netmask          Gateway       Interface  Metric",
        ]
        for dest, hop, src in rows:
            net, _, plen = dest.partition("/")
            mask = _prefix_to_mask(int(plen or 32))
            lines.append(f"{net:<24} {mask:<16} {hop:<14} 1          25")
        return CommandResult.out("\n".join(lines))
    if len(argv) >= 3 and argv[1] == "add":
        # route add 10.0.3.0 mask 255.255.255.0 10.0.0.1
        try:
            dest_ip = argv[2]
            mask = argv[argv.index("mask") + 1]
            hop = argv[-1]
            prefix = _mask_to_prefix(mask)
            routing.add_route(host, f"{dest_ip}/{prefix}", hop)
        except Exception as exc:  # noqa: BLE001
            return CommandResult.fail(f"route add failed: {exc}")
        return CommandResult.out(f" OK!", mutated=True)
    return CommandResult.fail("usage: route print | route add <net> mask <mask> <gw>")


def _mask_to_prefix(mask: str) -> int:
    """Convert dotted netmask to prefix length.

    Args:
        mask: Dotted-quad netmask.

    Returns:
        Prefix length.

    Raises:
        ValueError: If the mask is invalid.

    Examples:
        >>> _mask_to_prefix("255.255.255.0")
        24
    """
    parts = [int(x) for x in mask.split(".")]
    if len(parts) != 4:
        raise ValueError(f"bad mask: {mask}")
    value = (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
    bits = bin(value).count("1")
    # validate contiguous
    if value != ((0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF) and bits != 0:
        raise ValueError(f"non-contiguous mask: {mask}")
    return bits


def cmd_get_netadapter(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``Get-NetAdapter``."""
    host = _host(ctx)
    lines = [
        "Name                      InterfaceDescription                    ifIndex Status       MacAddress             LinkSpeed",
        "----                      --------------------                    ------- ------       ----------             ---------",
    ]
    for i, iface in enumerate(host.interfaces.values(), 1):
        status = "Up" if iface.state == LinkState.UP else "Disconnected"
        lines.append(
            f"{iface.name:<25} Hyper-V Virtual Ethernet Adapter          {i:<7} {status:<12} {iface.mac.replace(':', '-')}  10 Gbps"
        )
    return CommandResult.out("\n".join(lines))


def cmd_enable_netadapter(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``Enable-NetAdapter -Name eth0``."""
    joined = " ".join(argv)
    m = re.search(r"-Name\s+(\S+)", joined, flags=re.I)
    if not m:
        return CommandResult.fail("usage: Enable-NetAdapter -Name <name>")
    host = _host(ctx)
    iface = host.interfaces.get(m.group(1))
    if iface is None:
        return CommandResult.fail(f"Get-NetAdapter : No MSFT_NetAdapter objects found")
    iface.state = LinkState.UP
    return CommandResult.out(f"{iface.name} enabled", mutated=True)


def cmd_disable_netadapter(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``Disable-NetAdapter -Name eth0``."""
    joined = " ".join(argv)
    m = re.search(r"-Name\s+(\S+)", joined, flags=re.I)
    if not m:
        return CommandResult.fail("usage: Disable-NetAdapter -Name <name>")
    host = _host(ctx)
    iface = host.interfaces.get(m.group(1))
    if iface is None:
        return CommandResult.fail("Get-NetAdapter : No MSFT_NetAdapter objects found")
    iface.state = LinkState.DOWN
    return CommandResult.out(f"{iface.name} disabled", mutated=True)


def cmd_test_netconnection(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``Test-NetConnection [-Port N] <target>`` and ``TNC`` alias."""
    port = None
    target = None
    args = argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("-Port", "-port") and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                return CommandResult.fail("TNC: bad port")
            i += 2
            continue
        if args[i].startswith("-"):
            i += 1
            continue
        target = args[i]
        i += 1
    if not target:
        return CommandResult.fail("usage: Test-NetConnection [-Port N] <computer>")
    host = _host(ctx)
    try:
        dest_ip = dns_mod.resolve(ctx.session.state.world, host, target)
    except dns_mod.DNSFailure:
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
            dest_ip = parse_address(target)
        else:
            return CommandResult.fail(f"Test-NetConnection : Cannot resolve {target}")

    icmp = reachability.ping(ctx.session.state.world, host, str(dest_ip))
    lines = [
        "ComputerName           : " + target,
        "RemoteAddress          : " + str(dest_ip),
        "PingSucceeded          : " + ("True" if icmp.ok else "False"),
    ]
    if port is not None:
        conn = reachability.tcp_connect(ctx.session.state.world, host, target, port)
        lines.extend(
            [
                f"TcpTestSucceeded       : {str(conn.ok)}",
                f"RemotePort             : {port}",
            ]
        )
        ok = conn.ok
        reason = conn.reason
    else:
        ok = icmp.ok
        reason = icmp.reason
    return CommandResult.out(
        "\n".join(lines) + f"\nDetail                 : {reason}",
        # TNC failure is still "ran fine" as a command — report via text
    )


def cmd_resolve_dnsname(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``Resolve-DnsName <name>``."""
    name = next((a for a in argv[1:] if not a.startswith("-")), None)
    if not name:
        return CommandResult.fail("usage: Resolve-DnsName <name>")
    host = _host(ctx)
    try:
        ip = dns_mod.resolve(ctx.session.state.world, host, name)
    except dns_mod.DNSFailure as exc:
        return CommandResult.fail(f"Resolve-DnsName : {name} : {exc}")
    return CommandResult.out(
        f"Name                           Type   TTL   Section    NameHost\n"
        f"----                           ----   ---   -------    --------\n"
        f"{name}                         A      30    Answer     {ip}"
    )


def cmd_nslookup(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``nslookup <name>`` on Windows."""
    return cmd_resolve_dnsname(ctx, ["Resolve-DnsName"] + argv[1:])


def cmd_invoke_webrequest(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``Invoke-WebRequest <url>`` / ``iwr``."""
    url = next((a for a in argv[1:] if not a.startswith("-")), None)
    if not url:
        return CommandResult.fail("usage: Invoke-WebRequest <url>")
    m = re.match(r"^(https?)://([^/:]+)(?::(\d+))?(/.*)?$", url)
    if not m:
        return CommandResult.fail(f"IWR: cannot parse URL {url}")
    scheme, hostpart, port_s, path = m.group(1), m.group(2), m.group(3), m.group(4) or "/"
    port = int(port_s) if port_s else (443 if scheme == "https" else 80)
    host = _host(ctx)
    probe, status, body = reachability.http_get(ctx.session.state.world, host, hostpart, port=port, path=path)
    if not probe.ok:
        return CommandResult.fail(f"IWR: Unable to connect to {hostpart}:{port} — {probe.reason}")
    return CommandResult.out(
        f"StatusCode        : {status}\nStatusDescription : OK\nContent           : {body}"
    )


def cmd_netsh_advfirewall(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``netsh advfirewall firewall add rule ...`` and ``show``."""
    host = _host(ctx)
    joined = " ".join(argv)
    if "add" in joined and "rule" in joined:
        name_m = re.search(r'name="?([^"]+)"?', joined, flags=re.I)
        port_m = re.search(r"localport=(\d+)", joined, flags=re.I)
        action_allow = "action=allow" in joined.lower()
        proto = "tcp" if "protocol=tcp" in joined.lower() else "any"
        rule = fw.Rule(
            action="allow" if action_allow else "deny",
            proto=proto,
            port=int(port_m.group(1)) if port_m else None,
            src="any",
            comment=name_m.group(1) if name_m else "netsh",
        )
        fw.add_rule(host, rule)
        return CommandResult.out(f"Ok.\nAdded rule {rule.as_dict()}", mutated=True)
    rules = fw.rules_as_list(host)
    lines = [f"Firewall Enabled: {host.firewall_enabled}"]
    for r in rules:
        lines.append(f"  {r['action']} {r['proto']}/{r['port'] or '*'} src={r['src']}  # {r.get('comment','')}")
    return CommandResult.out("\n".join(lines))


def cmd_set_netfirewallprofile(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``Set-NetFirewallProfile -Enabled False`` / ``True``."""
    joined = " ".join(argv)
    if re.search(r"-Enabled\s+False", joined, flags=re.I):
        fw.set_enabled(_host(ctx), False)
        return CommandResult.out("Firewall profile disabled", mutated=True)
    if re.search(r"-Enabled\s+True", joined, flags=re.I):
        fw.set_enabled(_host(ctx), True)
        return CommandResult.out("Firewall profile enabled", mutated=True)
    return CommandResult.fail("usage: Set-NetFirewallProfile -Enabled <True|False>")


WINDOWS_HANDLERS = {
    "ipconfig": cmd_ipconfig,
    "new-netipaddress": cmd_new_netipaddress,
    "new-netroute": cmd_new_netroute,
    "get-netadapter": cmd_get_netadapter,
    "enable-netadapter": cmd_enable_netadapter,
    "disable-netadapter": cmd_disable_netadapter,
    "test-netconnection": cmd_test_netconnection,
    "tnc": cmd_test_netconnection,
    "resolve-dnsname": cmd_resolve_dnsname,
    "nslookup": cmd_nslookup,
    "ping": cmd_test_netconnection,
    "invoke-webrequest": cmd_invoke_webrequest,
    "iwr": cmd_invoke_webrequest,
    "curl": cmd_invoke_webrequest,
    "netstat": cmd_ipconfig,  # fallback listing; real netstat below via ss map
    "route": cmd_route,
    "netsh": cmd_netsh_advfirewall,
    "set-netfirewallprofile": cmd_set_netfirewallprofile,
    "get-netfirewallrule": cmd_netsh_advfirewall,
    "new-netfirewallrule": cmd_netsh_advfirewall,
}
