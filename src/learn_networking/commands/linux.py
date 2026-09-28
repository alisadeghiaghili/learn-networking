"""Linux command surface (ip, ss, dig, ping, curl, iptables-style, docker-style)."""

from __future__ import annotations

import re

from learn_networking.commands.router import CommandContext, CommandResult
from learn_networking.engine import dns as dns_mod
from learn_networking.engine import firewall as fw
from learn_networking.engine import reachability
from learn_networking.engine import routing
from learn_networking.engine.addressing import parse_address, parse_cidr
from learn_networking.engine.services import ServiceBinding
from learn_networking.engine.topology import LinkState


def _host(ctx: CommandContext):
    return ctx.session.current_host()


# ---------------------------------------------------------------------------
# show / inspect
# ---------------------------------------------------------------------------

def cmd_ip(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``ip`` (addr | link | route | addr add | route add ...).

    Args:
        ctx: Session context.
        argv: Tokens after the program name is included as argv[0]=='ip'.

    Returns:
        Command result.
    """
    if len(argv) < 2:
        return CommandResult.out(_ip_addr(ctx))
    sub = argv[1]
    if sub in ("a", "addr", "address"):
        if len(argv) >= 5 and argv[2] == "add":
            return _ip_addr_add(ctx, argv)
        return CommandResult.out(_ip_addr(ctx))
    if sub in ("l", "link"):
        return CommandResult.out(_ip_link(ctx, argv))
    if sub in ("r", "route"):
        if len(argv) >= 4 and argv[2] == "add":
            return _ip_route_add(ctx, argv)
        return CommandResult.out(_ip_route(ctx))
    return CommandResult.fail(f"ip: unknown subcommand {sub!r}")


def _ip_addr(ctx: CommandContext) -> str:
    host = _host(ctx)
    lines = [f"{host.name} ({host.os.value})"]
    for iface in host.interfaces.values():
        lines.append(iface.describe())
    return "\n".join(lines)


def _ip_addr_add(ctx: CommandContext, argv: list[str]) -> CommandResult:
    # ip addr add 10.0.0.5/24 dev eth0
    try:
        cidr_str = argv[3]
        dev = argv[argv.index("dev") + 1] if "dev" in argv else None
    except (IndexError, ValueError):
        return CommandResult.fail("usage: ip addr add <ip/prefix> dev <iface>")
    if not dev:
        return CommandResult.fail("usage: ip addr add <ip/prefix> dev <iface>")
    try:
        net = parse_cidr(cidr_str)
        ip = net.network  # wrong if host bits... use parse of host part
        ip_s, _, prefix_s = cidr_str.partition("/")
        ip = parse_address(ip_s)
        prefix = int(prefix_s or "24")
    except Exception as exc:  # noqa: BLE001
        return CommandResult.fail(f"inet prefix is invalid: {exc}")
    host = _host(ctx)
    iface = host.interfaces.get(dev)
    if iface is None:
        iface = host.add_interface_from_name(dev) if hasattr(host, "add_interface_from_name") else None
        if iface is None:
            from learn_networking.engine.topology import Interface

            iface = host.add_interface(Interface(name=dev))
    iface.ip = ip
    iface.prefix = prefix
    if iface.state == LinkState.DOWN:
        iface.state = LinkState.UP
    return CommandResult.out(f"added {ip}/{prefix} to {dev}", mutated=True)


def _ip_link(ctx: CommandContext, argv: list[str]) -> CommandResult:
    host = _host(ctx)
    if len(argv) >= 4 and argv[2] in ("set", "up", "down"):
        name = argv[3]
        state = LinkState.UP
        if argv[2] == "down":
            state = LinkState.DOWN
        if argv[2] == "set" and "up" in argv:
            state = LinkState.UP
        if argv[2] == "set" and "down" in argv:
            state = LinkState.DOWN
        iface = host.interfaces.get(name)
        if iface is None:
            return CommandResult.fail(f"Cannot find device {name}")
        iface.state = state
        return CommandResult.out(f"{name}: state {state.value}", mutated=True)
    lines = []
    for iface in host.interfaces.values():
        flags = "UP" if iface.state == LinkState.UP else "DOWN"
        lines.append(f"{iface.name}: <{flags}> mtu 1500 state {flags} mac {iface.mac}")
    return CommandResult.out("\n".join(lines) or "no interfaces")


def _ip_route(ctx: CommandContext) -> str:
    rows = routing.route_table(_host(ctx))
    if not rows:
        return ""
    lines = []
    for dest, hop, src in rows:
        if src.startswith("iface:"):
            lines.append(f"{dest} dev {src.split(':', 1)[1]} proto kernel scope link")
        elif src == "default":
            lines.append(f"default via {hop}")
        else:
            lines.append(f"{dest} via {hop}")
    return "\n".join(lines)


def _ip_route_add(ctx: CommandContext, argv: list[str]) -> CommandResult:
    # ip route add 10.0.3.0/24 via 10.0.0.1
    try:
        dest = argv[3]
        if dest == "default":
            dest = "0.0.0.0/0"
        via = argv[argv.index("via") + 1]
    except (IndexError, ValueError):
        return CommandResult.fail("usage: ip route add <cidr|default> via <hop>")
    try:
        routing.add_route(_host(ctx), dest, via)
    except Exception as exc:  # noqa: BLE001
        return CommandResult.fail(str(exc))
    return CommandResult.out(f"added route {dest} via {via}", mutated=True)


def cmd_ss(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``ss -lntup`` style inspections."""
    host = _host(ctx)
    if not host.services:
        return CommandResult.out("Netid  State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port")
    lines = ["Netid  State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port"]
    for port, svc in sorted(host.services.items()):
        lines.append(
            f"tcp    LISTEN  0       128     0.0.0.0:{port:<5}      0.0.0.0:*    users:(({svc.name},pid=1,fd=3))"
        )
    return CommandResult.out("\n".join(lines))


def cmd_ping(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``ping [-c N] <target>``."""
    count = 3
    args = []
    i = 1
    while i < len(argv):
        if argv[i] == "-c" and i + 1 < len(argv):
            try:
                count = int(argv[i + 1])
            except ValueError:
                return CommandResult.fail("ping: bad count")
            i += 2
            continue
        args.append(argv[i])
        i += 1
    if not args:
        return CommandResult.fail("usage: ping <host|ip>")
    target = args[0]
    host = _host(ctx)
    try:
        dest_ip = dns_mod.resolve(ctx.session.state.world, host, target)
    except dns_mod.DNSFailure:
        dest_ip = parse_address(target) if re.match(r"^\d+\.\d+\.\d+\.\d+$", target) else None
        if dest_ip is None:
            return CommandResult.fail(f"ping: {target}: Name or service not known")
        dest_ip = dest_ip
    result = reachability.ping(ctx.session.state.world, host, str(dest_ip), count=count)
    if result.ok:
        return CommandResult.out(
            f"PING {target} ({dest_ip}) 56(84) bytes of data.\n"
            f"64 bytes from {dest_ip}: icmp_seq=1 ttl=64 time=0.4 ms\n"
            f"--- {target} ping statistics ---\n"
            f"{count} packets transmitted, {count} received, 0% packet loss"
        )
    return CommandResult.fail(
        f"PING {target}: {result.reason}\n"
        f"--- {target} ping statistics ---\n"
        f"{count} packets transmitted, 0 received, 100% packet loss"
    )


def cmd_dig(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``dig [@server] <name>``."""
    name = argv[-1] if len(argv) > 1 else None
    if not name or name.startswith("+") or name.startswith("@"):
        return CommandResult.fail("usage: dig <name>")
    host = _host(ctx)
    try:
        ip = dns_mod.resolve(ctx.session.state.world, host, name)
    except dns_mod.DNSFailure as exc:
        return CommandResult.fail(
            f"; <<>> DiG <<>> {name}\n;; Got answer:\n;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN\n{exc}"
        )
    return CommandResult.out(
        f"; <<>> DiG <<>> {name}\n"
        f";; Got answer:\n"
        f";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 42\n"
        f";; ANSWER SECTION:\n"
        f"{name}.\t\t30\tIN\tA\t{ip}\n\n"
        f";; Query time: 1 msec\n"
        f";; SERVER: {host.dns_servers[0] if host.dns_servers else '127.0.0.11'}#53"
    )


def cmd_nslookup(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``nslookup <name>``."""
    return cmd_dig(ctx, ["dig"] + argv[1:])


def cmd_curl(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``curl [-I] [-k] <url>``."""
    args = [a for a in argv[1:] if not a.startswith("-")]
    if not args:
        return CommandResult.fail("usage: curl <url>")
    url = args[0]
    m = re.match(r"^(https?)://([^/:]+)(?::(\d+))?(/.*)?$", url)
    if not m:
        return CommandResult.fail(f"curl: (3) URL rejected: {url}")
    scheme, hostpart, port_s, path = m.group(1), m.group(2), m.group(3), m.group(4) or "/"
    port = int(port_s) if port_s else (443 if scheme == "https" else 80)
    host = _host(ctx)
    probe, status, body = reachability.http_get(ctx.session.state.world, host, hostpart, port=port, path=path)
    if not probe.ok:
        return CommandResult.fail(f"curl: (7) Failed to connect to {hostpart} port {port}: {probe.reason}")
    return CommandResult.out(
        f"HTTP/1.1 {status} OK\n"
        f"Content-Type: text/plain\n"
        f"Content-Length: {len(body)}\n"
        f"\n{body}"
    )


def cmd_iptables(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle a simplified ``iptables`` / ``ufw``-ish firewall CLI.

    Supported:
        iptables -L
        iptables -A INPUT -p tcp --dport 80 -j ACCEPT
        iptables -F
    """
    host = _host(ctx)
    if len(argv) >= 2 and argv[1] == "-L":
        rules = fw.rules_as_list(host)
        lines = [f"Chain INPUT (policy {'DROP' if host.firewall_enabled else 'ACCEPT'})"]
        for i, r in enumerate(rules, 1):
            port = r["port"] if r["port"] is not None else "*"
            tgt = "ACCEPT" if r["action"] == "allow" else "DROP"
            lines.append(f"{i}  {tgt}  {r['proto']}  --  {r['src']}  0.0.0.0/0  {r.get('comment','')} dpt:{port}")
        return CommandResult.out("\n".join(lines))
    if len(argv) >= 2 and argv[1] == "-F":
        n = fw.clear_rules(host)
        return CommandResult.out(f"flushed {n} rules", mutated=True)
    if len(argv) >= 3 and argv[1] == "-A":
        proto = "any"
        port = None
        action = "allow"
        src = "any"
        for i, tok in enumerate(argv):
            if tok == "-p" and i + 1 < len(argv):
                proto = argv[i + 1]
            if tok == "--dport" and i + 1 < len(argv):
                port = int(argv[i + 1])
            if tok == "-s" and i + 1 < len(argv):
                src = argv[i + 1]
            if tok == "-j" and i + 1 < len(argv):
                action = "allow" if argv[i + 1] in ("ACCEPT", "accept") else "deny"
        rule = fw.Rule(action=action, proto=proto, port=port, src=src, comment="iptables")
        fw.add_rule(host, rule)
        return CommandResult.out(f"appended rule {rule.as_dict()}", mutated=True)
    return CommandResult.fail("usage: iptables -L | -F | -A INPUT -p tcp --dport N -j ACCEPT")


def cmd_sysctl_forward(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``sysctl -w net.ipv4.ip_forward=1``."""
    host = _host(ctx)
    joined = " ".join(argv)
    if "net.ipv4.ip_forward=1" in joined:
        host.vars["ip_forward"] = "1"
        return CommandResult.out("net.ipv4.ip_forward = 1", mutated=True)
    if "net.ipv4.ip_forward=0" in joined:
        host.vars["ip_forward"] = "0"
        return CommandResult.out("net.ipv4.ip_forward = 0", mutated=True)
    val = host.vars.get("ip_forward", "0")
    return CommandResult.out(f"net.ipv4.ip_forward = {val}")


# docker / container-style
def cmd_docker(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle simplified ``docker network`` / ``docker run --publish`` / ``ps``."""
    host = _host(ctx)
    if len(argv) >= 2 and argv[1] == "ps":
        lines = ["CONTAINER ID   IMAGE     COMMAND   PORTS"]
        for name, val in sorted(host.vars.items()):
            if name.startswith("container:"):
                lines.append(f"cid-{name.split(':',1)[1][:6]}   {val}")
        return CommandResult.out("\n".join(lines) or "CONTAINER ID   IMAGE     COMMAND   PORTS")
    if len(argv) >= 3 and argv[1] == "network" and argv[2] == "ls":
        return CommandResult.out("NETWORK ID     NAME        DRIVER\nlocal_lab      bridge      bridge")
    if len(argv) >= 2 and argv[1] == "run":
        # docker run -d --name web -p 8080:80 nginx
        name = "ctr"
        publish = None
        for i, tok in enumerate(argv):
            if tok == "--name" and i + 1 < len(argv):
                name = argv[i + 1]
            if tok == "-p" and i + 1 < len(argv):
                publish = argv[i + 1]
        host.vars[f"container:{name}"] = "running"
        if publish:
            try:
                host_s, container_s = publish.split(":")
                host_port = int(host_s)
                container_port = int(container_s.split("/")[0])
            except ValueError:
                return CommandResult.fail(f"invalid publish spec: {publish}")
            # published port is a local listener that forwards to container service
            inner = host.services.get(container_port) or ServiceBinding(
                proto="tcp", name=name, banner=f"{name} ok", healthy=True
            )
            host.services[host_port] = ServiceBinding(
                proto="tcp",
                name=f"{name}-publish",
                banner=inner.banner,
                healthy=inner.healthy,
                metadata={"forward_to": str(container_port)},
            )
        return CommandResult.out(f"started container {name}", mutated=True)
    return CommandResult.fail("usage: docker ps | docker run -p H:C --name N image")


def cmd_nsupdate(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``nsupdate add A name ip`` / ``dns-add-record zone name ip``.

    This is the lab's zone-editing verb (stands in for nsupdate, RFC2136,
    or a cloud DNS API call).

    Usage:
        nsupdate add A api.internal 10.0.2.10
        nsupdate add A internal api 10.0.2.10
        dns-add-record internal api 10.0.2.10
    """
    args = [a for a in argv[1:] if a.lower() not in ("add", "a", "aaaa", "update")]
    if len(args) == 2 and "." in args[0]:
        fqdn, ip = args
        zone, _, name = fqdn.partition(".")
        # if multiple dots, treat first label as name and rest as zone
        if "." in fqdn:
            name, _, zone = fqdn.partition(".")
            # name is first label, zone is remainder — actually we want name+zone
            parts = fqdn.split(".")
            name, zone = parts[0], ".".join(parts[1:])
        dns_mod.add_record(ctx.session.state.world, zone, name, ip)
        return CommandResult.out(f"added A {name}.{zone} -> {ip}", mutated=True)
    if len(args) == 3:
        zone, name, ip = args
        dns_mod.add_record(ctx.session.state.world, zone, name, ip)
        return CommandResult.out(f"added A {name}.{zone} -> {ip}", mutated=True)
    return CommandResult.fail("usage: nsupdate add A <fqdn> <ip>  |  dns-add-record <zone> <name> <ip>")


def cmd_hostsfile(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Handle ``hostfile add <name> <ip>`` (lab stand-in for /etc/hosts)."""
    host = _host(ctx)
    if len(argv) >= 4 and argv[1] == "add":
        name = argv[2].rstrip(".").lower()
        try:
            ip = str(parse_address(argv[3]))
        except Exception as exc:  # noqa: BLE001
            return CommandResult.fail(str(exc))
        host.host_aliases[name] = ip
        return CommandResult.out(f"{ip}    {name}", mutated=True)
    if len(argv) >= 3 and argv[1] == "list":
        return CommandResult.out("\n".join(f"{v}    {k}" for k, v in sorted(host.host_aliases.items())) or "")
    return CommandResult.fail("usage: hostfile add <name> <ip> | hostfile list")


LINUX_HANDLERS = {
    "ip": cmd_ip,
    "ss": cmd_ss,
    "netstat": cmd_ss,
    "ping": cmd_ping,
    "dig": cmd_dig,
    "nslookup": cmd_nslookup,
    "curl": cmd_curl,
    "wget": cmd_curl,
    "iptables": cmd_iptables,
    "ufw": cmd_iptables,
    "sysctl": cmd_sysctl_forward,
    "docker": cmd_docker,
    "nsupdate": cmd_nsupdate,
    "dns-add-record": cmd_nsupdate,
    "hostfile": cmd_hostsfile,
}
