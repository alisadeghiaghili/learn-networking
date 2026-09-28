"""Inject dual-track step instructions into level JSON files.

One-shot content migration for the web UI. Not part of the runtime package.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path("src/learn_networking/levels/data")

# Per-level dual-track walkthroughs (follow-along, not just the answer).
STEPS: dict[str, dict] = {
    "link-01-address": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "Inspect the interface",
                    "command": "ip a",
                    "note": "See eth0 is down and has no address.",
                    "optional": True,
                },
                {
                    "title": "Assign 10.0.0.30/24",
                    "command": "ip addr add 10.0.0.30/24 dev eth0",
                    "note": "IP + prefix length + interface name. This also brings the link up in the lab.",
                },
                {
                    "title": "Confirm",
                    "command": "goal",
                    "note": "Both goal checks should be green.",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Inspect adapters",
                    "command": "Get-NetAdapter",
                    "note": "Find the adapter name (eth0 in this lab).",
                    "optional": True,
                },
                {
                    "title": "Assign address",
                    "command": "New-NetIPAddress -InterfaceAlias eth0 -IPAddress 10.0.0.30 -PrefixLength 24",
                    "note": "InterfaceAlias matches the adapter name. PrefixLength 24 = /24 subnet.",
                },
                {
                    "title": "Confirm with ipconfig",
                    "command": "ipconfig",
                    "note": "You should see IPv4 10.0.0.30.",
                    "optional": True,
                },
                {
                    "title": "Check goal",
                    "command": "goal",
                    "optional": True,
                },
            ],
        },
    },
    "link-02-ping": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "Address client-01",
                    "command": "ip addr add 10.0.0.30/24 dev eth0",
                    "note": "Same-subnet address as the goal requires.",
                },
                {
                    "title": "Ping the server",
                    "command": "ping 10.0.0.10",
                    "note": "ICMP on the same L2 segment — no gateway needed.",
                    "optional": True,
                },
                {
                    "title": "Confirm goal",
                    "command": "goal",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Address client-01",
                    "command": "New-NetIPAddress -InterfaceAlias eth0 -IPAddress 10.0.0.30 -PrefixLength 24",
                },
                {
                    "title": "Test connectivity",
                    "command": "Test-NetConnection 10.0.0.10",
                    "note": "TNC shows PingSucceeded.",
                    "optional": True,
                },
                {
                    "title": "Confirm goal",
                    "command": "goal",
                    "optional": True,
                },
            ],
        },
    },
    "route-01-default-gw": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "See current routes",
                    "command": "ip r",
                    "note": "No default route yet.",
                    "optional": True,
                },
                {
                    "title": "Set default gateway",
                    "command": "ip route add default via 10.0.0.1",
                    "note": "0.0.0.0/0 via the router on the LAN.",
                },
                {
                    "title": "Verify",
                    "command": "ip r",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "See routes",
                    "command": "route print",
                    "optional": True,
                },
                {
                    "title": "Set default gateway",
                    "command": "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
                },
                {
                    "title": "Confirm goal",
                    "command": "goal",
                    "optional": True,
                },
            ],
        },
    },
    "route-02-cross-subnet": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "Notice the two subnets",
                    "command": "topo",
                    "note": "10.0.0.0/24 and 10.0.2.0/24 — needs a gateway.",
                    "optional": True,
                },
                {
                    "title": "Default route via gw-01",
                    "command": "ip route add default via 10.0.0.1",
                },
                {
                    "title": "Ping across subnets",
                    "command": "ping 10.0.2.10",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Default route",
                    "command": "New-NetRoute -DestinationPrefix 0.0.0.0/0 -NextHop 10.0.0.1",
                },
                {
                    "title": "Cross-subnet ping",
                    "command": "Test-NetConnection 10.0.2.10",
                    "optional": True,
                },
            ],
        },
    },
    "dns-01-a-record": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "Fail first (optional)",
                    "command": "dig api.internal",
                    "note": "NXDOMAIN — no record yet. Diagnosis before config.",
                    "optional": True,
                },
                {
                    "title": "Add the A record",
                    "command": "nsupdate add A internal api 10.0.2.10",
                    "note": "Lab stand-in for zone edit / cloud DNS API.",
                },
                {
                    "title": "Resolve again",
                    "command": "dig api.internal",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Fail first (optional)",
                    "command": "Resolve-DnsName api.internal",
                    "optional": True,
                },
                {
                    "title": "Add the A record",
                    "command": "nsupdate add A internal api 10.0.2.10",
                    "note": "Same zone verb on both OSes (DNS is shared infrastructure).",
                },
                {
                    "title": "Confirm resolution",
                    "command": "Resolve-DnsName api.internal",
                    "optional": True,
                },
            ],
        },
    },
    "dns-02-hosts-file": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "Add hosts entry",
                    "command": "hostfile add redis.internal 10.0.20.20",
                    "note": "Local override — only on cache-01.",
                },
                {
                    "title": "Verify name + port",
                    "command": "dig redis.internal",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Add hosts entry",
                    "command": "hostfile add redis.internal 10.0.20.20",
                    "note": "Windows hosts file works the same way for one machine.",
                },
                {
                    "title": "Confirm",
                    "command": "Resolve-DnsName redis.internal",
                    "optional": True,
                },
            ],
        },
    },
    "ports-01-listen": {
        "track": "linux",
        "steps": {
            "linux": [
                {
                    "title": "SSH to ops-01",
                    "command": "ssh ops-01",
                    "note": "We publish the container on this host.",
                },
                {
                    "title": "Publish the port",
                    "command": "docker run -d --name web -p 8080:80 nginx",
                    "note": "Host 8080 forwards to container 80.",
                },
                {
                    "title": "Check listeners",
                    "command": "ss -lntup",
                    "optional": True,
                },
                {
                    "title": "From the probe",
                    "command": "ssh probe-01",
                    "optional": True,
                },
                {
                    "title": "TCP test",
                    "command": "Test-NetConnection 10.0.0.20 -Port 8080",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Note: this level is Linux-focused",
                    "command": "os linux",
                    "note": "Switch dialect, then use docker publish steps above.",
                },
                {
                    "title": "SSH and publish",
                    "command": "ssh ops-01",
                },
                {
                    "title": "Publish",
                    "command": "docker run -d --name web -p 8080:80 nginx",
                },
            ],
        },
    },
    "ports-02-http-health": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "Reproduce the failure",
                    "command": "curl http://api-01:8080/health",
                    "note": "Expect 503 — service is marked unhealthy.",
                    "optional": True,
                },
                {
                    "title": "Go to the API host",
                    "command": "ssh api-01",
                },
                {
                    "title": "Replace with a healthy listener",
                    "command": "docker run -d --name web -p 8080:80 nginx",
                    "note": "Published port becomes a healthy HTTP service.",
                },
                {
                    "title": "Re-check health",
                    "command": "curl http://api-01:8080/health",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Reproduce",
                    "command": "Invoke-WebRequest http://api-01:8080/health",
                    "note": "IWR / iwr is the Windows curl equivalent.",
                    "optional": True,
                },
                {
                    "title": "SSH to api-01",
                    "command": "ssh api-01",
                },
                {
                    "title": "Fix the listener",
                    "command": "docker run -d --name web -p 8080:80 nginx",
                },
                {
                    "title": "Confirm HTTP 200",
                    "command": "iwr http://api-01:8080/health",
                    "optional": True,
                },
            ],
        },
    },
    "firewall-01-open-port": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "See default deny",
                    "command": "ssh web-01",
                },
                {
                    "title": "List rules",
                    "command": "iptables -L",
                    "note": "Policy DROP, no allows yet.",
                    "optional": True,
                },
                {
                    "title": "Allow TCP/80",
                    "command": "iptables -A INPUT -p tcp --dport 80 -j ACCEPT",
                },
                {
                    "title": "Verify from monitor",
                    "command": "ssh monitor-01",
                    "optional": True,
                },
                {
                    "title": "TCP test",
                    "command": "ping 10.0.0.10",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "SSH to web-01",
                    "command": "ssh web-01",
                },
                {
                    "title": "Allow TCP/80 (netsh)",
                    "command": "netsh advfirewall firewall add rule name=web protocol=tcp localport=80 action=allow",
                },
                {
                    "title": "Or PowerShell",
                    "command": "New-NetFirewallRule -DisplayName web -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow",
                    "note": "Lab accepts netsh; both teach the same idea.",
                    "optional": True,
                },
            ],
        },
    },
    "firewall-02-default-deny": {
        "track": "linux",
        "steps": {
            "linux": [
                {
                    "title": "Understand the requirement",
                    "command": "goal",
                    "note": "Allow 22 from 10.0.0.0/24 only; keep 10.9.9.50 out.",
                    "optional": True,
                },
                {
                    "title": "Targeted allow",
                    "command": "iptables -A INPUT -p tcp --dport 22 -s 10.0.0.0/24 -j ACCEPT",
                    "note": "Source-scoped rule — the security-group pattern.",
                },
            ],
            "windows": [
                {
                    "title": "Switch to Linux dialect",
                    "command": "os linux",
                    "note": "This drill is iptables-focused; the idea maps to netsh too.",
                },
                {
                    "title": "Targeted allow",
                    "command": "iptables -A INPUT -p tcp --dport 22 -s 10.0.0.0/24 -j ACCEPT",
                },
            ],
        },
    },
    "containers-01-publish": {
        "track": "linux",
        "steps": {
            "linux": [
                {
                    "title": "Go to the Docker host",
                    "command": "ssh docker-01",
                },
                {
                    "title": "Publish host 8080",
                    "command": "docker run -d --name api -p 8080:80 nginx",
                },
                {
                    "title": "Prove from Windows client",
                    "command": "ssh win-01",
                    "optional": True,
                },
                {
                    "title": "HTTP check",
                    "command": "iwr http://172.17.0.1:8080/",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "SSH to docker-01",
                    "command": "ssh docker-01",
                },
                {
                    "title": "Publish",
                    "command": "docker run -d --name api -p 8080:80 nginx",
                },
            ],
        },
    },
    "discovery-01-service-dns": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "See the cluster DNS zones",
                    "command": "goal",
                    "optional": True,
                },
                {
                    "title": "Point the service name at the VIP",
                    "command": "nsupdate add A payments.default.svc.cluster.local 10.96.0.20",
                },
                {
                    "title": "Resolve from a pod",
                    "command": "dig payments.default.svc.cluster.local",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "Add ClusterIP DNS",
                    "command": "nsupdate add A payments.default.svc.cluster.local 10.96.0.20",
                },
                {
                    "title": "Confirm",
                    "command": "Resolve-DnsName payments.default.svc.cluster.local",
                    "optional": True,
                },
            ],
        },
    },
    "discovery-02-lb": {
        "track": "linux",
        "steps": {
            "linux": [
                {
                    "title": "Open backend A",
                    "command": "ssh web-a",
                },
                {
                    "title": "Allow HTTP on A",
                    "command": "iptables -A INPUT -p tcp --dport 80 -j ACCEPT",
                },
                {
                    "title": "Open backend B",
                    "command": "ssh web-b",
                },
                {
                    "title": "Allow HTTP on B",
                    "command": "iptables -A INPUT -p tcp --dport 80 -j ACCEPT",
                },
                {
                    "title": "Verify VIP",
                    "command": "curl http://10.96.0.20/",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "SSH and open both backends",
                    "command": "ssh web-a",
                    "note": "Repeat the allow on web-b (Linux firewall in the lab).",
                },
                {
                    "title": "Allow on A",
                    "command": "iptables -A INPUT -p tcp --dport 80 -j ACCEPT",
                },
                {
                    "title": "Allow on B",
                    "command": "ssh web-b",
                },
                {
                    "title": "Allow on B",
                    "command": "iptables -A INPUT -p tcp --dport 80 -j ACCEPT",
                },
            ],
        },
    },
    "troubleshoot-01-etl-postgres": {
        "track": "both",
        "steps": {
            "linux": [
                {
                    "title": "1. Reproduce",
                    "command": "ping db.internal",
                    "note": "Name may fail — log both DNS and L3 results.",
                    "optional": True,
                },
                {
                    "title": "2. Fix routing",
                    "command": "ip route add default via 10.0.10.1",
                    "note": "ETL has no default gateway — first layer.",
                },
                {
                    "title": "3. Fix DNS",
                    "command": "nsupdate add A internal db 10.0.20.10",
                    "note": "db.internal must resolve to db-01.",
                },
                {
                    "title": "4. Open the DB firewall",
                    "command": "ssh db-01",
                },
                {
                    "title": "5. Allow Postgres",
                    "command": "netsh advfirewall firewall add rule name=postgres protocol=tcp localport=5432 action=allow",
                    "note": "db-01 is a Windows host in this incident.",
                },
                {
                    "title": "6. Prove end-to-end",
                    "command": "ssh etl-01",
                    "optional": True,
                },
                {
                    "title": "7. TCP to Postgres",
                    "command": "Test-NetConnection db.internal -Port 5432",
                    "optional": True,
                },
            ],
            "windows": [
                {
                    "title": "1. Reproduce",
                    "command": "Test-NetConnection db.internal -Port 5432",
                    "optional": True,
                },
                {
                    "title": "2. Fix routing on ETL",
                    "command": "ssh etl-01",
                },
                {
                    "title": "Default gateway",
                    "command": "ip route add default via 10.0.10.1",
                    "note": "Works on the Linux ETL host; use New-NetRoute on Windows hosts.",
                },
                {
                    "title": "3. DNS",
                    "command": "nsupdate add A internal db 10.0.20.10",
                },
                {
                    "title": "4. Firewall on db-01",
                    "command": "ssh db-01",
                },
                {
                    "title": "5. Allow 5432",
                    "command": "netsh advfirewall firewall add rule name=postgres protocol=tcp localport=5432 action=allow",
                },
                {
                    "title": "6. Prove",
                    "command": "ssh etl-01",
                    "optional": True,
                },
                {
                    "title": "7. Final check",
                    "command": "Test-NetConnection db.internal -Port 5432",
                    "optional": True,
                },
            ],
        },
    },
}


def main() -> None:
    for path in sorted(DATA.glob("*.json")):
        level = json.loads(path.read_text(encoding="utf-8"))
        extra = STEPS.get(path.stem)
        if not extra:
            print("no steps for", path.stem)
            continue
        level["track"] = extra["track"]
        level["steps"] = extra["steps"]
        # keep solution_commands as linux-first reference
        path.write_text(json.dumps(level, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("updated", path.name)

    # mirror into docs/levels
    docs = Path("docs/levels")
    for path in sorted(DATA.glob("*.json")):
        (docs / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print("synced docs/levels")


if __name__ == "__main__":
    main()
