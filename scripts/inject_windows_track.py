"""Add native Windows solution commands and Windows-only levels.

Extends every dual level with ``solution_commands_windows`` and writes a
Windows-only onboarding series.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path("src/learn_networking/levels/data")

# Native Windows reference solutions (same goals, Windows verbs).
WIN_SOLUTIONS: dict[str, list[str]] = {
    "link-01-address": [
        "New-NetIPAddress -InterfaceAlias eth0 -IPAddress 10.0.0.30 -PrefixLength 24",
    ],
    "link-02-ping": [
        "New-NetIPAddress -InterfaceAlias eth0 -IPAddress 10.0.0.30 -PrefixLength 24",
    ],
    "route-01-default-gw": [
        "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
    ],
    "route-02-cross-subnet": [
        "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
    ],
    "dns-01-a-record": [
        "nsupdate add A internal api 10.0.2.10",
    ],
    "dns-02-hosts-file": [
        "hostfile add redis.internal 10.0.20.20",
    ],
    "ports-01-listen": [
        "ssh ops-01",
        "docker run -d --name web -p 8080:80 nginx",
    ],
    "ports-02-http-health": [
        "ssh api-01",
        "docker run -d --name web -p 8080:80 nginx",
    ],
    "firewall-01-open-port": [
        "ssh web-01",
        "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
    ],
    "firewall-02-default-deny": [
        "ssh bastion-01",
        "netsh advfirewall firewall add rule name=ssh-admin protocol=tcp localport=22 action=allow",
    ],
    "containers-01-publish": [
        "ssh docker-01",
        "docker run -d --name api -p 8080:80 nginx",
    ],
    "discovery-01-service-dns": [
        "nsupdate add A payments.default.svc.cluster.local 10.96.0.20",
    ],
    "discovery-02-lb": [
        "ssh web-a",
        "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
        "ssh web-b",
        "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
    ],
    "troubleshoot-01-etl-postgres": [
        "ssh etl-01",
        "ip route add default via 10.0.10.1",
        "nsupdate add A internal db 10.0.20.10",
        "ssh db-01",
        "netsh advfirewall firewall add rule name=postgres protocol=tcp localport=5432 action=allow",
    ],
}

# Flip track labels so Windows-only drills show up on the Windows track.
TRACK_OVERRIDES = {
    "ports-01-listen": "both",
    "firewall-02-default-deny": "both",
    "containers-01-publish": "both",
    "discovery-02-lb": "both",
}

NEW_LEVELS = [
    {
        "id": "win-01-ipconfig",
        "sequence": "link",
        "name": "Windows IP Inventory",
        "objective": "On the Windows host win-01, assign 10.0.0.30/24 to Ethernet0 and prove it with ipconfig.",
        "hint": "New-NetIPAddress -InterfaceAlias Ethernet0 -IPAddress 10.0.0.30 -PrefixLength 24, then ipconfig.",
        "track": "windows",
        "par": 1,
        "os_focus": ["windows"],
        "start": {
            "networks": {"lab": "10.0.0.0/24"},
            "hosts": {
                "win-01": {
                    "os": "windows",
                    "role": "client",
                    "interfaces": {
                        "Ethernet0": {"network": "lab", "state": "down", "mac": "00:15:5D:00:00:30"}
                    },
                    "firewall_enabled": False,
                },
                "srv-01": {
                    "os": "windows",
                    "role": "server",
                    "interfaces": {
                        "Ethernet0": {"network": "lab", "ip": "10.0.0.10", "prefix": 24, "state": "up"}
                    },
                    "firewall_enabled": False,
                },
            },
        },
        "goal_checks": [
            {
                "type": "has_ip",
                "params": {"host": "win-01", "iface": "Ethernet0", "ip": "10.0.0.30", "prefix": 24},
                "description": "Ethernet0 has 10.0.0.30/24",
            },
            {
                "type": "iface_up",
                "params": {"host": "win-01", "iface": "Ethernet0"},
                "description": "Ethernet0 is up",
            },
            {
                "type": "os_is",
                "params": {"host": "win-01", "os": "windows"},
                "description": "win-01 is a Windows host",
            },
        ],
        "solution_commands": [
            "os windows",
            "New-NetIPAddress -InterfaceAlias Ethernet0 -IPAddress 10.0.0.30 -PrefixLength 24",
        ],
        "solution_commands_windows": [
            "New-NetIPAddress -InterfaceAlias Ethernet0 -IPAddress 10.0.0.30 -PrefixLength 24",
        ],
        "steps": {
            "linux": [
                {
                    "title": "Switch to Windows dialect",
                    "command": "os windows",
                    "note": "This lesson is Windows-native. Use PowerShell-shaped commands.",
                },
                {
                    "title": "List adapters",
                    "command": "Get-NetAdapter",
                    "optional": True,
                },
                {
                    "title": "Assign IPv4",
                    "command": "New-NetIPAddress -InterfaceAlias Ethernet0 -IPAddress 10.0.0.30 -PrefixLength 24",
                    "note": "PrefixLength 24 equals subnet mask 255.255.255.0.",
                },
                {
                    "title": "Confirm",
                    "command": "ipconfig",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "List adapters",
                    "command": "Get-NetAdapter",
                    "note": "Note the InterfaceAlias — here it is Ethernet0.",
                },
                {
                    "title": "Assign IPv4",
                    "command": "New-NetIPAddress -InterfaceAlias Ethernet0 -IPAddress 10.0.0.30 -PrefixLength 24",
                    "note": "This is the modern replacement for netsh interface ip set address.",
                },
                {
                    "title": "Confirm with ipconfig",
                    "command": "ipconfig",
                    "note": "IPv4 Address should read 10.0.0.30, mask 255.255.255.0.",
                },
                {
                    "title": "Goal check",
                    "command": "goal",
                    "optional": True,
                },
            ],
        },
    },
    {
        "id": "win-02-tnc-http",
        "sequence": "ports",
        "name": "Windows Health Probe",
        "objective": "From win-01, prove TCP/8080 is open on web-01 using Test-NetConnection, then HTTP GET via Invoke-WebRequest.",
        "hint": "Start the listener on web-01 with docker publish, then Test-NetConnection web-01 -Port 8080 and iwr http://web-01:8080/health.",
        "track": "windows",
        "par": 2,
        "os_focus": ["windows"],
        "start": {
            "networks": {"lab": "10.0.0.0/24"},
            "hosts": {
                "win-01": {
                    "os": "windows",
                    "role": "client",
                    "interfaces": {
                        "Ethernet0": {"network": "lab", "ip": "10.0.0.30", "prefix": 24, "state": "up"}
                    },
                    "firewall_enabled": False,
                },
                "web-01": {
                    "os": "linux",
                    "role": "web",
                    "interfaces": {
                        "eth0": {"network": "lab", "ip": "10.0.0.10", "prefix": 24, "state": "up"}
                    },
                    "firewall_enabled": False,
                    "services": {
                        "8080": {"proto": "tcp", "name": "http", "banner": "api v1", "healthy": False}
                    },
                },
            },
        },
        "goal_checks": [
            {
                "type": "listening",
                "params": {"host": "web-01", "port": 8080, "proto": "tcp"},
                "description": "web-01 listens on 8080/tcp",
            },
            {
                "type": "tcp_ok",
                "params": {"source": "win-01", "target": "web-01", "port": 8080},
                "description": "win-01 TCP-connects to web-01:8080",
            },
            {
                "type": "http_status",
                "params": {
                    "source": "win-01",
                    "target": "web-01",
                    "port": 8080,
                    "path": "/health",
                    "status": 200,
                },
                "description": "GET /health returns 200",
            },
        ],
        "solution_commands": [
            "ssh web-01",
            "docker run -d --name web -p 8080:80 nginx",
        ],
        "solution_commands_windows": [
            "ssh web-01",
            "docker run -d --name web -p 8080:80 nginx",
            "ssh win-01",
            "os windows",
        ],
        "steps": {
            "linux": [
                {
                    "title": "Reproduce with curl (optional)",
                    "command": "ssh win-01",
                    "optional": True,
                },
                {
                    "title": "Switch to Windows",
                    "command": "os windows",
                },
                {
                    "title": "Probe (will fail until fixed)",
                    "command": "Test-NetConnection web-01 -Port 8080",
                    "optional": True,
                },
                {
                    "title": "Fix the listener",
                    "command": "ssh web-01",
                },
                {
                    "title": "Publish healthy HTTP",
                    "command": "docker run -d --name web -p 8080:80 nginx",
                },
                {
                    "title": "Back to win-01",
                    "command": "ssh win-01",
                    "optional": True,
                },
                {
                    "title": "TNC again",
                    "command": "Test-NetConnection web-01 -Port 8080",
                    "optional": True,
                },
                {
                    "title": "HTTP GET",
                    "command": "iwr http://web-01:8080/health",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "You are on win-01",
                    "command": "whoami",
                    "optional": True,
                },
                {
                    "title": "TNC before the fix",
                    "command": "Test-NetConnection web-01 -Port 8080",
                    "note": "TcpTestSucceeded False — nothing healthy is serving /health yet.",
                    "optional": True,
                },
                {
                    "title": "SSH to the web host",
                    "command": "ssh web-01",
                },
                {
                    "title": "Publish a healthy listener",
                    "command": "docker run -d --name web -p 8080:80 nginx",
                    "note": "Host port 8080 becomes a healthy HTTP service.",
                },
                {
                    "title": "Return to Windows client",
                    "command": "ssh win-01",
                },
                {
                    "title": "TCP test",
                    "command": "Test-NetConnection web-01 -Port 8080",
                    "note": "TNC is the Windows reachability workhorse (ping + TCP).",
                },
                {
                    "title": "HTTP health",
                    "command": "iwr http://web-01:8080/health",
                    "note": "Invoke-WebRequest (iwr) is the Windows curl.",
                },
            ],
        },
    },
    {
        "id": "win-03-firewall",
        "sequence": "firewall",
        "name": "Windows Firewall Rule",
        "objective": "On win-fw (Windows), allow inbound TCP/80 from the LAN with netsh, leaving other ports closed.",
        "hint": "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
        "track": "windows",
        "par": 1,
        "os_focus": ["windows"],
        "start": {
            "networks": {"lan": "10.0.0.0/24"},
            "hosts": {
                "win-fw": {
                    "os": "windows",
                    "role": "web",
                    "interfaces": {
                        "Ethernet0": {"network": "lan", "ip": "10.0.0.10", "prefix": 24, "state": "up"}
                    },
                    "firewall_enabled": True,
                    "firewall_rules": [],
                    "services": {
                        "80": {"proto": "tcp", "name": "http", "banner": "hello from web", "healthy": True},
                        "22": {"proto": "tcp", "name": "ssh", "banner": "OpenSSH", "healthy": True},
                    },
                },
                "win-client": {
                    "os": "windows",
                    "role": "client",
                    "interfaces": {
                        "Ethernet0": {"network": "lan", "ip": "10.0.0.50", "prefix": 24, "state": "up"}
                    },
                    "firewall_enabled": False,
                },
            },
        },
        "goal_checks": [
            {
                "type": "firewall_allows",
                "params": {"host": "win-fw", "proto": "tcp", "port": 80, "src": "10.0.0.50"},
                "description": "TCP/80 allowed from win-client",
            },
            {
                "type": "tcp_ok",
                "params": {"source": "win-client", "target": "win-fw", "port": 80},
                "description": "win-client can reach win-fw:80",
            },
            {
                "type": "firewall_denies",
                "params": {"host": "win-fw", "proto": "tcp", "port": 22, "src": "10.0.0.50"},
                "description": "TCP/22 still denied (default policy)",
            },
        ],
        "solution_commands": [
            "os windows",
            "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
        ],
        "solution_commands_windows": [
            "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
        ],
        "steps": {
            "linux": [
                {
                    "title": "Use Windows firewall verbs",
                    "command": "os windows",
                },
                {
                    "title": "List current profile state",
                    "command": "netsh advfirewall show allprofiles",
                    "optional": True,
                },
                {
                    "title": "Allow HTTP",
                    "command": "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
                },
            ],
            "windows": [
                {
                    "title": "Inspect firewall state",
                    "command": "Get-NetFirewallProfile",
                    "note": "Default is enabled and inbound is blocked unless allowed.",
                    "optional": True,
                },
                {
                    "title": "See current rules",
                    "command": "netsh advfirewall firewall show rule name=all",
                    "optional": True,
                },
                {
                    "title": "Allow only TCP/80",
                    "command": "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
                    "note": "One targeted allow — the security-group pattern on Windows.",
                },
                {
                    "title": "Verify from the client",
                    "command": "ssh win-client",
                    "optional": True,
                },
                {
                    "title": "TCP test",
                    "command": "Test-NetConnection win-fw -Port 80",
                    "optional": True,
                },
                {
                    "title": "Confirm 22 stays closed",
                    "command": "Test-NetConnection win-fw -Port 22",
                    "optional": True,
                },
            ],
        },
    },
    {
        "id": "win-04-route-print",
        "sequence": "route",
        "name": "Windows Routing Table",
        "objective": "Give win-01 a default route via 10.0.0.1 using New-NetRoute, then read the table with route print.",
        "hint": "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
        "track": "windows",
        "par": 1,
        "os_focus": ["windows"],
        "start": {
            "networks": {"lan": "10.0.0.0/24", "wan": "10.9.9.0/24"},
            "hosts": {
                "win-01": {
                    "os": "windows",
                    "role": "client",
                    "interfaces": {
                        "Ethernet0": {"network": "lan", "ip": "10.0.0.30", "prefix": 24, "state": "up"}
                    },
                    "firewall_enabled": False,
                },
                "gw-01": {
                    "os": "windows",
                    "role": "router",
                    "interfaces": {
                        "Ethernet0": {"network": "lan", "ip": "10.0.0.1", "prefix": 24, "state": "up"},
                        "Ethernet1": {"network": "wan", "ip": "10.9.9.1", "prefix": 24, "state": "up"},
                    },
                    "firewall_enabled": False,
                    "vars": {"ip_forward": "1"},
                },
                "remote-01": {
                    "os": "windows",
                    "role": "remote",
                    "interfaces": {
                        "Ethernet0": {"network": "wan", "ip": "10.9.9.50", "prefix": 24, "state": "up"}
                    },
                    "default_gateway": "10.9.9.1",
                    "firewall_enabled": False,
                },
            },
        },
        "goal_checks": [
            {
                "type": "default_gateway",
                "params": {"host": "win-01", "gateway": "10.0.0.1"},
                "description": "Default gateway is 10.0.0.1",
            },
            {
                "type": "ping_ok",
                "params": {"source": "win-01", "target": "10.9.9.50"},
                "description": "win-01 can reach the remote subnet",
            },
        ],
        "solution_commands": [
            "os windows",
            "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
        ],
        "solution_commands_windows": [
            "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
        ],
        "steps": {
            "linux": [
                {
                    "title": "Windows routing lesson",
                    "command": "os windows",
                },
                {
                    "title": "Read the table",
                    "command": "route print",
                    "optional": True,
                },
                {
                    "title": "Default route",
                    "command": "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
                },
            ],
            "windows": [
                {
                    "title": "Read the routing table",
                    "command": "route print",
                    "note": "Network Destination / Netmask / Gateway — classic format still used on ops teams.",
                    "optional": True,
                },
                {
                    "title": "Add default route (modern)",
                    "command": "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
                    "note": "DestinationPrefix 0.0.0.0/0 is the default route.",
                },
                {
                    "title": "Confirm with route print",
                    "command": "route print",
                    "optional": True,
                },
                {
                    "title": "Cross-subnet probe",
                    "command": "Test-NetConnection 10.9.9.50",
                    "optional": True,
                },
            ],
        },
    },
    {
        "id": "win-05-dns-resolve",
        "sequence": "dns",
        "name": "Windows DNS Lookup",
        "objective": "Make api.internal resolve to 10.0.2.10 and verify with Resolve-DnsName from win-01.",
        "hint": "nsupdate add A internal api 10.0.2.10 then Resolve-DnsName api.internal.",
        "track": "windows",
        "par": 1,
        "os_focus": ["windows"],
        "start": {
            "networks": {"lan": "10.0.0.0/24", "db": "10.0.2.0/24"},
            "hosts": {
                "win-01": {
                    "os": "windows",
                    "role": "client",
                    "interfaces": {
                        "Ethernet0": {"network": "lan", "ip": "10.0.0.30", "prefix": 24, "state": "up"}
                    },
                    "dns_servers": ["10.0.0.53"],
                    "search_domains": ["internal"],
                    "firewall_enabled": False,
                },
                "gw-01": {
                    "os": "windows",
                    "role": "router",
                    "interfaces": {
                        "Ethernet0": {"network": "lan", "ip": "10.0.0.1", "prefix": 24, "state": "up"},
                        "Ethernet1": {"network": "db", "ip": "10.0.2.1", "prefix": 24, "state": "up"},
                    },
                    "firewall_enabled": False,
                    "vars": {"ip_forward": "1"},
                },
                "api-01": {
                    "os": "windows",
                    "role": "api",
                    "interfaces": {
                        "Ethernet0": {"network": "db", "ip": "10.0.2.10", "prefix": 24, "state": "up"}
                    },
                    "firewall_enabled": False,
                    "services": {
                        "8080": {"proto": "tcp", "name": "http", "banner": "api v1", "healthy": True}
                    },
                },
            },
            "dns_zones": {"internal": {}},
        },
        "goal_checks": [
            {
                "type": "dns_resolves",
                "params": {"host": "win-01", "name": "api.internal", "ip": "10.0.2.10"},
                "description": "api.internal → 10.0.2.10",
            },
            {
                "type": "tcp_ok",
                "params": {"source": "win-01", "target": "api.internal", "port": 8080},
                "description": "win-01 reaches api.internal:8080",
            },
        ],
        "solution_commands": [
            "os windows",
            "nsupdate add A internal api 10.0.2.10",
        ],
        "solution_commands_windows": [
            "nsupdate add A internal api 10.0.2.10",
        ],
        "steps": {
            "linux": [
                {
                    "title": "Windows DNS lesson",
                    "command": "os windows",
                },
                {
                    "title": "Fail lookup",
                    "command": "Resolve-DnsName api.internal",
                    "optional": True,
                },
                {
                    "title": "Add A record",
                    "command": "nsupdate add A internal api 10.0.2.10",
                },
            ],
            "windows": [
                {
                    "title": "Reproduce NXDOMAIN",
                    "command": "Resolve-DnsName api.internal",
                    "note": "Windows-native DNS tool (replaces nslookup for most checks).",
                    "optional": True,
                },
                {
                    "title": "Publish the A record",
                    "command": "nsupdate add A internal api 10.0.2.10",
                    "note": "DNS is shared infrastructure — the zone verb is the same on both OSes.",
                },
                {
                    "title": "Confirm resolution",
                    "command": "Resolve-DnsName api.internal",
                },
                {
                    "title": "HTTP smoke test",
                    "command": "iwr http://api.internal:8080/",
                    "optional": True,
                },
            ],
        },
    },
]


def main() -> None:
    for path in sorted(DATA.glob("*.json")):
        level = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        if path.stem in WIN_SOLUTIONS:
            level["solution_commands_windows"] = WIN_SOLUTIONS[path.stem]
            changed = True
        if path.stem in TRACK_OVERRIDES:
            level["track"] = TRACK_OVERRIDES[path.stem]
            changed = True
        if changed:
            path.write_text(json.dumps(level, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("updated", path.name)

    for level in NEW_LEVELS:
        dest = DATA / f"{level['id']}.json"
        dest.write_text(json.dumps(level, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("created", dest.name)

    docs = Path("docs/levels")
    for path in sorted(DATA.glob("*.json")):
        (docs / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print("synced docs/levels", len(list(DATA.glob('*.json'))), "files")


if __name__ == "__main__":
    main()
