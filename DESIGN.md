# learn-networking — Design Notes

Interactive networking tutorial inspired by
[learnGitBranching](https://github.com/pcottle/learnGitBranching) (LGB),
scoped for **data engineers and DevOps practitioners** on **Windows and Linux**.

## Why not a web clone of LGB?

LGB's power is not the React UI — it is the loop:

1. a **sandbox** with a live simulated world
2. **levels** with start state, goal state, hints, and a known solution
3. **goal comparison** after every command
4. **command golf** and undo/reset
5. instant meta commands (`levels`, `hint`, `show goal`)

Git's natural interface is a terminal. Networking is the same. A web canvas of
commit trees does not teach `ss`, `dig`, `Test-NetConnection`, or security
groups. We keep the LGB loop and swap the world model for a **multi-host
network lab**, driven by real Linux and Windows command syntax.

A static HTML visualization can be added later as a thin view over the same
engine. The engine is the product.

## Style anchor

- Product feel: a serious ops lab / packet-tracer classroom, not a marketing site.
- Terminal-native UI with clear ASCII topology maps.
- English in code and level content (per project standard). Conversation may be Persian.

## Curriculum focus (data + DevOps)

What a data engineer / DevOps engineer actually needs day to day:

| Area | Why it matters | Commands taught |
|------|----------------|-----------------|
| Addressing & CIDR | container IPs, subnets, cloud VPCs | `ip`, `ipconfig`, CIDR math |
| Link / interface state | bring up adapters, rename, inspect | `ip link`, `Get-NetAdapter` |
| Routing | multi-subnet, default gateway, bastion | `ip route`, `route print` |
| DNS | service names for APIs, warehouses, Kafka | `dig`, `Resolve-DnsName`, `nslookup` |
| Ports & listeners | API ports, Postgres, Kafka, Redis | `ss`, `netstat`, listeners |
| HTTP health checks | readiness probes, LB backends | `curl`, `Invoke-WebRequest` |
| Firewalls / SGs | the #1 "why can't I connect" | `iptables`/`nft`, Windows Firewall |
| Container networks | Docker bridge, port publish | docker-style net commands |
| Service discovery | K8s-style ClusterIP DNS | `svc.cluster.local` resolution |
| LB / reverse proxy | multi-backend routing | health-aware backends |
| TLS basics | HTTPS, cert subject/SAN | `curl --insecure` / cert inspect |
| Troubleshooting | systematic path: ARP→L3→L4→L7 | `ping`, `traceroute`, `Test-NetConnection` |

Out of scope for v1: BGP, wireless, VPN crypto, packet capture decoding.

## Architecture

```
src/learn_networking/
  engine/          # pure simulation — no I/O, fully unit-testable
    addressing.py  # IPv4 + CIDR
    topology.py    # Host, Interface, Link, NetworkWorld
    routing.py     # route tables, next-hop selection
    dns.py         # zones, A records, CNAME
    services.py    # TCP/UDP listeners, HTTP apps
    firewall.py    # filter rules (allow/deny)
    reachability.py# L3/L4 path evaluation
  commands/        # command surface (Linux + Windows + meta)
    linux.py
    windows.py
    meta.py        # levels, hint, show goal, undo, reset, whoami, ssh
    router.py      # dispatch by host OS flavor
  levels/
    loader.py
    catalog.py
    data/*.json    # level definitions
  viz/
    topology_ascii.py
  session.py       # REPL session, undo stack, level runtime
  progress.py      # solved map, command golf
  cli.py           # entrypoint
tests/
```

### Level schema (JSON)

```json
{
  "id": "dns-a-record",
  "sequence": "dns",
  "name": "Name to Address",
  "objective": "Resolve api.internal to the backend IP",
  "hint": "Point the A record at the backend address.",
  "start": { "world": { "...": "hosts, links, dns, services" } },
  "goal_checks": [
    { "type": "dns_resolves", "host": "client", "name": "api.internal", "ip": "10.0.2.10" }
  ],
  "disabled_commands": [],
  "os_focus": ["linux", "windows"],
  "solution_commands": ["..."],
  "par": 2
}
```

Win conditions are declarative predicates over the world (not tree strings).
That is the right analog of LGB's `TreeCompare` for networking.

### Dual OS surface

Each simulated host has `os: "linux" | "windows"`. The prompt shows which
host/OS you are on (`you@web-01:~$` vs `PS C:\\Users\\you>`). Both syntaxes
are accepted where they teach the same concept; levels may force one OS.

### Instant / meta commands (LGB parity)

| Command | Meaning |
|---------|---------|
| `levels` | list sequences and solve status |
| `hint` | level hint |
| `show goal` / `goal` | print goal state and check status |
| `reset` | restore level start world |
| `undo` | undo last world-changing command |
| `topo` / `topology` | ASCII topology map |
| `hosts` | inventory |
| `ssh <host>` | switch context (as root/ops, no password) |
| `os linux` / `os windows` | switch command dialect on current host |
| `solution` | reveal reference solution (counts as not-best) |
| `help` | command index |
| `sandbox` | free-play mode |
| `level <id>` | load a level |

### Command golf

Count only commands that mutate world state (address changes, routes, DNS,
firewall, services). Inspection commands (`ip a`, `dig`, `ss`, `ping`) are free —
they teach diagnosis without punishing curiosity. This is stricter and more
honest than LGB counting every git verb.

## Level sequences (v1)

1. **link** — interfaces up, addresses, same-subnet ping
2. **route** — gateway, cross-subnet, static routes
3. **dns** — A records, internal service names
4. **ports** — listeners, HTTP health, `ss` diagnosis
5. **firewall** — open a port, default-deny
6. **containers** — docker bridge, published ports
7. **discovery** — K8s-style service DNS + LB
8. **troubleshoot** — multi-layer incident: "why can't the ETL reach Postgres?"

## Quality bar

- Full type hints (Python 3.11+), Google-style docstrings with Args/Returns/Raises/Examples.
- Pure engine: no hidden state; `NetworkWorld` is a value-like object with explicit mutation API.
- Tests accompany code (`pytest`).
- Conventional Commits. No AI footprint in the repository.
- README and migration notes in English.

## Non-goals (v1)

- Real packet I/O or pcap
- IPv6 (schema-ready, not implemented)
- GUI topology editor
- Multiplayer
