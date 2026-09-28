# learn-networking

Interactive networking lab for **data engineers** and **DevOps practitioners**,
on **Linux and Windows** command surfaces.

Modeled on the loop of
[learnGitBranching](https://github.com/pcottle/learnGitBranching):

| LGB | learn-networking |
|-----|------------------|
| git sandbox | multi-host network lab |
| commit-tree visualization | ASCII topology map |
| goal tree + TreeCompare | declarative goal checks (DNS, routes, firewall, HTTP) |
| `git commit` levels | address / route / DNS / firewall / container challenges |
| command golf | golf on **mutating** commands only (inspection is free) |
| `hint` / `show goal` / `undo` / `reset` | same meta verbs |

Why not a web clone of LGB? Networking work is terminal work. Teaching `ss`,
`dig`, `Test-NetConnection`, and security groups inside a commit-tree UI is
the wrong metaphor. See [DESIGN.md](DESIGN.md).

## Web demo (GitHub Pages)

An LGB-style browser UI lives in [`docs/`](docs/) and is published with GitHub Pages:

```bash
# local preview
python -m http.server 8080 --directory docs
# open http://localhost:8080
```

Same levels, same goal checks, dual OS command surfaces — terminal on the left,
live topology and goal checklist on the right.

**Tracks:** switch between **Linux** and **Windows** in the top bar. Levels are
listed per track; shared drills include both command dialects. Each level has a
**step-by-step guide** (click a step command to run it) — the learn-dvc
follow-along style.

**Logo / favicon:** `docs/assets/logo.svg` + `docs/favicon.svg`.

## Quick start (CLI)

```bash
# from repo root (Python 3.11+)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux

pip install -e ".[dev]"
learn-networking              # sandbox
learn-networking --list-levels
learn-networking link-01-address
learn-networking -c "levels" -c "topo"
```

Or without install:

```powershell
$env:PYTHONPATH = "src"
python -m learn_networking
```

```bash
PYTHONPATH=src python -m learn_networking
```

## The game loop

```
levels                 list sequences and solve status
level <id>             load a challenge
sandbox                free-play lab
hint                   level hint
goal                   goal checks with live pass/fail
topo                   ASCII topology
hosts / hostinfo       inventory and detail
ssh <host>             switch context
os linux|windows       switch dialect on current host
undo / reset           LGB-style recovery
solution [--run]       reference solution (forfeits best score)
help / man <topic>
```

### Linux surface

`ip a|link|route`, `ss`, `dig`, `ping`, `curl`, `iptables`, `sysctl`, `docker run -p`, `nsupdate`, `hostfile`

### Windows surface

`ipconfig`, `Get-NetAdapter`, `Enable/Disable-NetAdapter`, `New-NetIPAddress`,
`New-NetRoute`, `route print`, `Test-NetConnection` / `TNC`,
`Resolve-DnsName`, `Invoke-WebRequest` / `iwr`, `netsh advfirewall`, `Set-NetFirewallProfile`

Both dialects work on every host so you can compare tools; levels may set an
OS focus (`os linux` / `os windows`).

## Curriculum (data + DevOps)

| Sequence | You learn | Real job use |
|----------|-----------|--------------|
| **link** | IPs, CIDR, interface state | container IPs, cloud ENIs |
| **route** | default gateway, cross-subnet | VPC routes, bastion paths |
| **dns** | A records, hosts file, search domains | service names for APIs / warehouses |
| **ports** | listeners, TCP connect, HTTP `/health` | readiness probes, `ss` diagnosis |
| **firewall** | default-deny + targeted allow | security groups, `iptables`, Windows Firewall |
| **containers** | `docker run -p` publish | local compose debugging |
| **discovery** | ClusterIP-style DNS + VIP health | Kubernetes service names |
| **troubleshoot** | layered incident (route+DNS+FW) | "ETL cannot reach Postgres" |

## Example session

```
learn-networking link-01-address
you@client-01:~$ topo
you@client-01:~$ ip a
you@client-01:~$ ip addr add 10.0.0.30/24 dev eth0
you@client-01:~$ goal
SOLVED in 1 mutating commands (par 1)
```

Windows-style:

```
you@client-01:~$ os windows
PS C:\Users\Administrator> New-NetIPAddress -InterfaceAlias eth0 -IPAddress 10.0.0.30 -PrefixLength 24
```

## Architecture

```
src/learn_networking/
  engine/       pure simulation (addressing, topology, routing, dns, firewall, reachability)
  commands/     linux / windows / meta command surfaces
  levels/       JSON level defs + goal predicates
  viz/          ASCII topology
  session.py    game runtime (undo, golf, solve)
  progress.py   persistent best scores
  cli.py        REPL + -c batch mode
tests/          pytest suite
```

Goal checks are declarative predicates (`dns_resolves`, `tcp_ok`,
`firewall_allows`, `http_status`, ...) evaluated against the world — the
networking analog of LGB tree compare.

## Development

```bash
pytest
ruff check src tests
mypy src
```

## License

MIT
