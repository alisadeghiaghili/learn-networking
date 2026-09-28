/**
 * learn-networking web engine — pure JS port of the Python simulation core.
 * Same world model, command intents, and goal checks as the CLI.
 */
"use strict";

// ---------------------------------------------------------------------------
// addressing
// ---------------------------------------------------------------------------

function parseIPv4(s) {
  const parts = String(s).trim().split(".");
  if (parts.length !== 4) throw new Error("invalid IPv4: " + s);
  let n = 0;
  for (const p of parts) {
    const v = Number(p);
    if (!Number.isInteger(v) || v < 0 || v > 255) throw new Error("invalid IPv4: " + s);
    n = (n << 8) | v;
  }
  return n >>> 0;
}

function formatIPv4(n) {
  return [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join(".");
}

function parseCIDR(s) {
  const [ip, prefixStr] = String(s).trim().split("/");
  const ipN = parseIPv4(ip);
  const prefix = prefixStr === undefined ? 32 : Number(prefixStr);
  if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32) throw new Error("bad prefix: " + s);
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return { network: (ipN & mask) >>> 0, mask, prefix };
}

function ipInNet(ipN, cidr) {
  return ((ipN & cidr.mask) >>> 0) === cidr.network;
}

// ---------------------------------------------------------------------------
// world model
// ---------------------------------------------------------------------------

function emptyHost(name, os, role) {
  return {
    name,
    os: os || "linux",
    role: role || "generic",
    interfaces: {},
    defaultGateway: null,
    routes: {},
    dnsServers: [],
    searchDomains: [],
    firewallEnabled: true,
    firewallRules: [],
    services: {},
    hostAliases: {},
    vars: {},
  };
}

function buildWorld(spec) {
  const world = {
    networks: {},
    hosts: {},
    dnsZones: {},
    meta: {},
  };
  for (const [name, cidr] of Object.entries(spec.networks || {})) {
    world.networks[name] = parseCIDR(cidr);
  }
  for (const [hname, hspec] of Object.entries(spec.hosts || {})) {
    const host = emptyHost(hname, hspec.os, hspec.role);
    host.firewallEnabled = hspec.firewall_enabled !== false;
    host.hostAliases = { ...(hspec.host_aliases || {}) };
    host.vars = { ...(hspec.vars || {}) };
    host.dnsServers = [...(hspec.dns_servers || [])];
    host.searchDomains = [...(hspec.search_domains || [])];
    host.routes = { ...(hspec.routes || {}) };
    for (const r of hspec.firewall_rules || []) host.firewallRules.push({ ...r });
    if (hspec.default_gateway) host.defaultGateway = parseIPv4(hspec.default_gateway);
    for (const [iname, ispec] of Object.entries(hspec.interfaces || {})) {
      host.interfaces[iname] = {
        name: iname,
        mac: ispec.mac || "02:00:00:00:00:01",
        state: ispec.state === "down" ? "down" : "up",
        ip: ispec.ip ? parseIPv4(ispec.ip) : null,
        prefix: ispec.prefix ?? 24,
        network: ispec.network || null,
      };
      if (host.interfaces[iname].network && !world.networks[host.interfaces[iname].network] && ispec.ip) {
        world.networks[host.interfaces[iname].network] = parseCIDR(
          ispec.ip + "/" + (ispec.prefix ?? 24)
        );
      }
    }
    for (const [port, sspec] of Object.entries(hspec.services || {})) {
      host.services[Number(port)] = {
        proto: sspec.proto || "tcp",
        name: sspec.name || "svc",
        banner: sspec.banner || "ok",
        healthy: sspec.healthy !== false,
        port: Number(port),
      };
    }
    world.hosts[hname] = host;
  }
  for (const [zone, records] of Object.entries(spec.dns_zones || {})) {
    world.dnsZones[zone] = { ...records };
  }
  return world;
}

function primaryIface(host) {
  const list = Object.values(host.interfaces);
  return list.find((i) => i.ip !== null) || list[0] || null;
}

function primaryIp(host) {
  const i = primaryIface(host);
  return i && i.ip !== null ? i.ip : null;
}

function findHostByIp(world, ipN) {
  for (const host of Object.values(world.hosts)) {
    for (const iface of Object.values(host.interfaces)) {
      if (iface.ip === ipN) return host;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// routing
// ---------------------------------------------------------------------------

function lookupRoute(host, destN) {
  let bestConn = null;
  for (const iface of Object.values(host.interfaces)) {
    if (iface.ip === null) continue;
    const net = parseCIDR(formatIPv4(iface.ip) + "/" + iface.prefix);
    if (ipInNet(destN, net)) {
      if (!bestConn || iface.prefix > bestConn) bestConn = iface.prefix;
    }
  }
  if (bestConn !== null) return "on-link";

  let best = null;
  for (const [dest, hop] of Object.entries(host.routes)) {
    const net = parseCIDR(dest);
    if (ipInNet(destN, net)) {
      if (!best || net.prefix > best.prefix) best = { prefix: net.prefix, hop };
    }
  }
  if (best) return best.hop;
  if (host.defaultGateway !== null) return formatIPv4(host.defaultGateway);
  return null;
}

// ---------------------------------------------------------------------------
// DNS
// ---------------------------------------------------------------------------

function dnsResolve(world, host, name) {
  const qname = String(name).replace(/\.$/, "").toLowerCase();
  if (/^\d+\.\d+\.\d+\.\d+$/.test(qname)) return parseIPv4(qname);

  const inv = world.hosts[qname];
  if (inv) {
    const ip = primaryIp(inv);
    if (ip !== null) return ip;
  }
  if (host && host.hostAliases[qname]) return parseIPv4(host.hostAliases[qname]);

  for (const records of Object.values(world.dnsZones)) {
    if (records[qname]) return parseIPv4(records[qname]);
    for (const zone of Object.keys(world.dnsZones)) {
      const fqdn = qname.endsWith("." + zone) ? qname : qname + "." + zone;
      if (records[fqdn]) return parseIPv4(records[fqdn]);
    }
  }
  if (host) {
    for (const domain of host.searchDomains) {
      const fqdn = qname.endsWith("." + domain) ? qname : qname + "." + domain;
      for (const records of Object.values(world.dnsZones)) {
        if (records[fqdn]) return parseIPv4(records[fqdn]);
      }
    }
  }
  throw new Error("NXDOMAIN: " + name);
}

// ---------------------------------------------------------------------------
// firewall
// ---------------------------------------------------------------------------

function firewallEvaluate(host, proto, port, srcN) {
  if (!host.firewallEnabled) return { ok: true, reason: "firewall disabled" };
  for (const rule of host.firewallRules) {
    const action = rule.action || "deny";
    const rproto = rule.proto || "any";
    if (rproto !== "any" && rproto !== proto) continue;
    if (rule.port != null && port != null && rule.port !== port) continue;
    if (rule.port != null && port == null) continue;
    if (rule.src && rule.src !== "any") {
      try {
        if (!ipInNet(srcN, parseCIDR(rule.src))) continue;
      } catch {
        continue;
      }
    }
    return {
      ok: action === "allow",
      reason: (action === "allow" ? "allowed" : "denied") + " by rule: " + (rule.comment || action),
    };
  }
  return { ok: false, reason: "denied by default policy" };
}

// ---------------------------------------------------------------------------
// reachability
// ---------------------------------------------------------------------------

function ping(world, source, target) {
  let destN;
  try {
    destN = dnsResolve(world, source, target);
  } catch (e) {
    return { ok: false, layer: "DNS", reason: e.message };
  }
  const destHost = findHostByIp(world, destN);
  if (!destHost) return { ok: false, layer: "L3", reason: "no host owns " + formatIPv4(destN) };

  const srcIp = primaryIp(source);
  const hop = lookupRoute(source, destN);
  if (!hop) return { ok: false, layer: "L3", reason: "no route from " + source.name };

  if (hop !== "on-link") {
    const hopN = parseIPv4(hop);
    const hopHost = findHostByIp(world, hopN);
    if (hopHost && hopHost !== destHost && hopHost !== source) {
      const nested = ping(world, hopHost, formatIPv4(destN));
      if (!nested.ok) return nested;
    }
  }

  const fw = firewallEvaluate(destHost, "icmp", null, srcIp ?? destN);
  if (!fw.ok) return { ok: false, layer: "L3", reason: "icmp blocked: " + fw.reason };
  return { ok: true, layer: "L3", reason: "echo reply from " + formatIPv4(destN) };
}

function tcpConnect(world, source, target, port) {
  let destN;
  try {
    destN = dnsResolve(world, source, target);
  } catch (e) {
    return { ok: false, layer: "DNS", reason: e.message };
  }
  const destHost = findHostByIp(world, destN);
  if (!destHost) return { ok: false, layer: "L3", reason: "no host owns " + formatIPv4(destN) };

  const hop = lookupRoute(source, destN);
  if (!hop) return { ok: false, layer: "L3", reason: "no route from " + source.name };

  const srcIp = primaryIp(source);
  const fw = firewallEvaluate(destHost, "tcp", port, srcIp ?? destN);
  if (!fw.ok) return { ok: false, layer: "L4", reason: "filtered: " + fw.reason };

  const svc = destHost.services[port];
  if (!svc || svc.proto !== "tcp") {
    return {
      ok: false,
      layer: "L4",
      reason: "connection refused — nothing listening on " + destHost.name + ":" + port,
    };
  }
  return {
    ok: true,
    layer: "L4",
    reason: "connected to " + destHost.name + ":" + port + " (" + svc.name + ")",
  };
}

function httpGet(world, source, target, port, path) {
  const conn = tcpConnect(world, source, target, port);
  if (!conn.ok) return { probe: conn, status: null, body: conn.reason };
  let destN;
  try {
    destN = dnsResolve(world, source, target);
  } catch (e) {
    return { probe: { ok: false, layer: "DNS", reason: e.message }, status: null, body: e.message };
  }
  const destHost = findHostByIp(world, destN);
  const svc = destHost && destHost.services[port];
  if (!svc) return { probe: conn, status: null, body: "no service" };
  let status = 200;
  let body = svc.banner || "ok";
  const p = path || "/";
  if (p === "/health" || p === "/healthz" || p === "/ready" || p === "/readyz") {
    if (svc.healthy) {
      status = 200;
      body = "ok";
    } else {
      status = 503;
      body = "unhealthy";
    }
  } else if (p === "/" || p === "/index.html") {
    status = 200;
    body = svc.banner || svc.name + " ok";
  } else {
    status = 404;
    body = "not found";
  }
  return {
    probe: { ok: status >= 200 && status < 400, layer: "L7", reason: "HTTP " + status },
    status,
    body,
  };
}

// ---------------------------------------------------------------------------
// goal checks
// ---------------------------------------------------------------------------

function evaluateCheck(check, world, currentHost) {
  const p = check.params || {};
  const t = check.type;
  const h = (key) => world.hosts[p[key] || currentHost];
  try {
    if (t === "dns_resolves") {
      const ip = dnsResolve(world, h(), p.name);
      const want = parseIPv4(p.ip);
      return { ok: ip === want, detail: "dns " + p.name + " -> " + formatIPv4(ip) + " (want " + p.ip + ")" };
    }
    if (t === "has_ip") {
      const host = h();
      const iface = (p.iface && host.interfaces[p.iface]) || primaryIface(host);
      if (!iface || iface.ip === null) return { ok: false, detail: "no address on interface" };
      const want = parseIPv4(p.ip);
      let ok = iface.ip === want;
      if (ok && p.prefix != null) ok = iface.prefix === p.prefix;
      return {
        ok,
        detail:
          "iface addr " + formatIPv4(iface.ip) + "/" + iface.prefix + " (want " + p.ip + ")",
      };
    }
    if (t === "iface_up") {
      const iface = h().interfaces[p.iface];
      if (!iface) return { ok: false, detail: "missing iface " + p.iface };
      return { ok: iface.state === "up", detail: iface.name + " is " + iface.state };
    }
    if (t === "route_exists") {
      const host = h();
      const dest = p.dest.includes("/") ? p.dest : p.dest;
      const stored = host.routes[dest] || host.routes[parseCIDR(dest).prefix === 0 ? "0.0.0.0/0" : dest];
      return { ok: stored === p.via, detail: "route " + dest + " via " + stored + " (want " + p.via + ")" };
    }
    if (t === "default_gateway") {
      const host = h();
      const got = host.defaultGateway !== null ? formatIPv4(host.defaultGateway) : null;
      return { ok: got === p.gateway, detail: "default gw " + got + " (want " + p.gateway + ")" };
    }
    if (t === "listening") {
      const host = h();
      const svc = host.services[Number(p.port)];
      const ok = !!svc && svc.proto === (p.proto || "tcp");
      return { ok, detail: host.name + ":" + p.port + (ok ? " listening" : " not listening") };
    }
    if (t === "firewall_allows") {
      const r = firewallEvaluate(h(), p.proto || "tcp", p.port, parseIPv4(p.src || "0.0.0.0"));
      return { ok: r.ok, detail: r.reason };
    }
    if (t === "firewall_denies") {
      const r = firewallEvaluate(h(), p.proto || "tcp", p.port, parseIPv4(p.src || "0.0.0.0"));
      return { ok: !r.ok, detail: r.reason };
    }
    if (t === "ping_ok") {
      const r = ping(world, world.hosts[p.source], p.target);
      return { ok: r.ok, detail: r.layer + ": " + r.reason };
    }
    if (t === "ping_fail") {
      const r = ping(world, world.hosts[p.source], p.target);
      return { ok: !r.ok, detail: r.layer + ": " + r.reason };
    }
    if (t === "tcp_ok") {
      const r = tcpConnect(world, world.hosts[p.source], p.target, Number(p.port));
      return { ok: r.ok, detail: r.layer + ": " + r.reason };
    }
    if (t === "tcp_fail") {
      const r = tcpConnect(world, world.hosts[p.source], p.target, Number(p.port));
      return { ok: !r.ok, detail: r.layer + ": " + r.reason };
    }
    if (t === "http_status") {
      const r = httpGet(
        world,
        world.hosts[p.source],
        p.target,
        Number(p.port ?? 80),
        p.path || "/"
      );
      return {
        ok: r.status === Number(p.status),
        detail: "HTTP " + r.status + " (want " + p.status + ")",
      };
    }
    if (t === "http_body_contains") {
      const r = httpGet(
        world,
        world.hosts[p.source],
        p.target,
        Number(p.port ?? 80),
        p.path || "/"
      );
      const text = String(p.text);
      return {
        ok: r.body != null && String(r.body).includes(text),
        detail: "body contains " + text,
      };
    }
    if (t === "host_var") {
      const got = h().vars[p.key];
      return {
        ok: String(got) === String(p.value),
        detail: "var " + p.key + "=" + got + " (want " + p.value + ")",
      };
    }
    if (t === "os_is") {
      return { ok: h().os === String(p.os).toLowerCase(), detail: "os=" + h().os };
    }
    return { ok: false, detail: "unknown check type: " + t };
  } catch (e) {
    return { ok: false, detail: "check error: " + e.message };
  }
}

// ---------------------------------------------------------------------------
// commands
// ---------------------------------------------------------------------------

function tokenize(line) {
  const out = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let m;
  while ((m = re.exec(line))) out.push(m[1] ?? m[2] ?? m[3]);
  return out;
}

function prefixToMask(prefix) {
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return formatIPv4(mask);
}

function maskToPrefix(mask) {
  const n = parseIPv4(mask);
  return n.toString(2).split("1").length - 1;
}

class GameSession {
  constructor() {
    this.catalog = {};
    this.level = null;
    this.progress = this.loadProgress();
    this.enterSandbox();
  }

  loadProgress() {
    try {
      if (typeof localStorage === "undefined") return {};
      return JSON.parse(localStorage.getItem("learn-networking-progress") || "{}");
    } catch {
      return {};
    }
  }

  saveProgress() {
    try {
      if (typeof localStorage === "undefined") return;
      localStorage.setItem("learn-networking-progress", JSON.stringify(this.progress));
    } catch {
      /* ignore quota / private mode */
    }
  }

  enterSandbox() {
    this.level = null;
    this.world = buildWorld({
      networks: { lab: "10.0.0.0/24", "db-net": "10.0.2.0/24" },
      hosts: {
        "gw-01": {
          os: "linux",
          role: "router",
          interfaces: {
            eth0: { network: "lab", ip: "10.0.0.1", prefix: 24, state: "up" },
            eth1: { network: "db-net", ip: "10.0.2.1", prefix: 24, state: "up" },
          },
          vars: { ip_forward: "1" },
          firewall_enabled: false,
        },
        "web-01": {
          os: "linux",
          role: "web",
          interfaces: { eth0: { network: "lab", ip: "10.0.0.10", prefix: 24, state: "up" } },
          default_gateway: "10.0.0.1",
          firewall_enabled: false,
        },
        "ops-01": {
          os: "windows",
          role: "ops",
          interfaces: { Ethernet0: { network: "lab", ip: "10.0.0.20", prefix: 24, state: "up" } },
          default_gateway: "10.0.0.1",
          firewall_enabled: false,
        },
        "db-01": {
          os: "linux",
          role: "db",
          interfaces: { eth0: { network: "db-net", ip: "10.0.2.10", prefix: 24, state: "up" } },
          firewall_enabled: false,
          services: {
            5432: { proto: "tcp", name: "postgres", banner: "PostgreSQL", healthy: true },
          },
        },
      },
    });
    this.currentHost = "web-01";
    this.undoStack = [];
    this.commandsIssued = 0;
    this.solved = false;
    this.showSolutionUsed = false;
    this.commandLog = [];
  }

  loadLevel(id) {
    const level = this.catalog[id];
    if (!level) return { ok: false, error: "unknown level " + id };
    this.level = level;
    this.world = buildWorld(level.start);
    this.currentHost = this.pickStartHost();
    this.undoStack = [];
    this.commandsIssued = 0;
    this.solved = false;
    this.showSolutionUsed = false;
    this.commandLog = [];
    return { ok: true, output: this.renderObjective() + "\n\n" + this.renderGoal() };
  }

  pickStartHost() {
    for (const host of Object.values(this.world.hosts)) {
      if (!["router", "gw", "firewall"].includes(host.role)) return host.name;
    }
    return Object.keys(this.world.hosts)[0];
  }

  snapshot() {
    return JSON.stringify({
      world: this.world,
      currentHost: this.currentHost,
      commandsIssued: this.commandsIssued,
      solved: this.solved,
    });
  }

  restore(snap) {
    const data = JSON.parse(snap);
    this.world = data.world;
    this.currentHost = data.currentHost;
    this.commandsIssued = data.commandsIssued;
    this.solved = data.solved;
    // revive typed fields
    for (const host of Object.values(this.world.hosts)) {
      if (typeof host.defaultGateway === "string") {
        try {
          host.defaultGateway = parseIPv4(host.defaultGateway);
        } catch {
          host.defaultGateway = null;
        }
      }
    }
  }

  pushUndo() {
    this.undoStack.push(this.snapshot());
    if (this.undoStack.length > 50) this.undoStack.shift();
  }

  host() {
    return this.world.hosts[this.currentHost];
  }

  prompt() {
    const h = this.host();
    return h.os === "windows"
      ? "PS C:\\Users\\Administrator>"
      : "you@" + h.name + ":~$";
  }

  execute(line) {
    line = (line || "").trim();
    if (!line) return { ok: true, output: "" };
    if (line.includes(";")) {
      const parts = line.split(";").map((s) => s.trim()).filter(Boolean);
      const results = parts.map((p) => this.execute(p));
      return {
        ok: results.every((r) => r.ok),
        output: results.map((r) => r.output).filter(Boolean).join("\n"),
        error: results.map((r) => r.error).filter(Boolean).join("\n"),
        mutated: results.some((r) => r.mutated),
      };
    }

    const argv = tokenize(line);
    const prog = argv[0].toLowerCase();
    const joined = argv.map((a) => a.toLowerCase()).join(" ");

    // meta
    if (prog === "levels") return { ok: true, output: this.renderLevels() };
    if (prog === "level") return this.loadLevel(argv[1] || "");
    if (prog === "hint") return { ok: true, output: this.renderHint() };
    if (prog === "goal" || joined === "show goal")
      return { ok: true, output: this.renderGoal() };
    if (prog === "objective" || joined === "show objective")
      return { ok: true, output: this.renderObjective() };
    if (prog === "reset") return this.reset();
    if (prog === "undo") return this.undo();
    if (prog === "topo" || prog === "topology")
      return { ok: true, output: this.renderTopology() };
    if (prog === "hosts") return { ok: true, output: this.renderHosts() };
    if (prog === "hostinfo") return { ok: true, output: this.renderHostInfo(argv[1]) };
    if (prog === "ssh") return this.ssh(argv[1]);
    if (prog === "os") return this.setOs(argv[1]);
    if (prog === "solution") return this.showSolution(argv.includes("--run") || argv.includes("-r"));
    if (prog === "help" || prog === "?") return { ok: true, output: HELP_TEXT };
    if (prog === "sandbox") {
      this.enterSandbox();
      return { ok: true, output: "Sandbox mode." };
    }
    if (prog === "whoami") return { ok: true, output: this.prompt().replace(/^\S+@/, "").replace(/:~\$$/, "").replace(/^PS /, "") };
    if (prog === "clear") return { ok: true, output: "\u001b[2J\u001b[H", clear: true };

    if (this.level && this.level.disabled_commands) {
      for (const blocked of this.level.disabled_commands) {
        if (line.toLowerCase().startsWith(blocked.toLowerCase())) {
          return { ok: false, error: "command disabled in this level: " + blocked };
        }
      }
    }

    const before = JSON.stringify(this.world);
    this.pushUndo();
    let result;
    try {
      result = this.dispatch(prog, argv, line);
    } catch (e) {
      this.undoStack.pop();
      return { ok: false, error: String(e.message || e) };
    }
    const after = JSON.stringify(this.world);
    if (!result.ok) {
      this.undoStack.pop();
      return result;
    }
    if (result.mutated || after !== before) {
      result.mutated = true;
      this.commandsIssued += 1;
    } else {
      this.undoStack.pop();
      result.mutated = false;
    }
    this.maybeSolve();
    return result;
  }

  dispatch(prog, argv, line) {
    const h = this.host();
    const world = this.world;
    const session = this;

    function flagMap(args) {
      const map = {};
      for (let i = 0; i < args.length; i++) {
        const a = args[i];
        if (a.startsWith("-") && args[i + 1] && !args[i + 1].startsWith("-")) {
          map[a.replace(/^-+/, "").toLowerCase()] = args[i + 1];
        }
      }
      return map;
    }

    // ---- shared / linux
    if (prog === "ip") {
      const sub = (argv[1] || "").toLowerCase();
      if (sub === "a" || sub === "addr" || sub === "address") {
        if (argv[2] === "add") {
          const cidr = argv[3];
          const dev = argv[argv.indexOf("dev") + 1];
          const [ipS, prefixS] = cidr.split("/");
          const iface = (h.interfaces[dev] = h.interfaces[dev] || {
            name: dev,
            mac: "02:00:00:00:00:02",
            state: "up",
            ip: null,
            prefix: 24,
            network: null,
          });
          iface.ip = parseIPv4(ipS);
          iface.prefix = Number(prefixS || 24);
          iface.state = "up";
          return { ok: true, output: "added " + cidr + " to " + dev, mutated: true };
        }
        let out = h.name + " (" + h.os + ")";
        for (const iface of Object.values(h.interfaces)) {
          out +=
            "\n" +
            iface.name +
            ": <" +
            iface.state +
            "> " +
            (iface.ip !== null ? formatIPv4(iface.ip) + "/" + iface.prefix : "no address") +
            " net=" +
            (iface.network || "-") +
            " mac=" +
            iface.mac;
        }
        return { ok: true, output: out };
      }
      if (sub === "l" || sub === "link") {
        if (argv[2] === "up" || argv[2] === "down" || argv[2] === "set") {
          const name = argv[2] === "set" ? argv[3] : argv[3];
          const state = argv.includes("down") ? "down" : "up";
          if (!h.interfaces[name]) return { ok: false, error: "Cannot find device " + name };
          h.interfaces[name].state = state;
          return { ok: true, output: name + ": state " + state, mutated: true };
        }
        let out = "";
        for (const iface of Object.values(h.interfaces)) {
          out +=
            iface.name +
            ": <" +
            iface.state.toUpperCase() +
            "> mtu 1500 mac " +
            iface.mac +
            "\n";
        }
        return { ok: true, output: out || "no interfaces" };
      }
      if (sub === "r" || sub === "route") {
        if (argv[2] === "add") {
          let dest = argv[3];
          if (dest === "default") dest = "0.0.0.0/0";
          const via = argv[argv.indexOf("via") + 1];
          if (dest === "0.0.0.0/0") {
            h.defaultGateway = parseIPv4(via);
            h.routes["0.0.0.0/0"] = via;
          } else {
            h.routes[dest] = via;
          }
          return { ok: true, output: "added route " + dest + " via " + via, mutated: true };
        }
        const lines = [];
        for (const iface of Object.values(h.interfaces)) {
          if (iface.ip !== null)
            lines.push(
              formatIPv4(iface.ip) + "/" + iface.prefix + " dev " + iface.name + " proto kernel"
            );
        }
        for (const [dest, hop] of Object.entries(h.routes)) {
          lines.push(dest === "0.0.0.0/0" ? "default via " + hop : dest + " via " + hop);
        }
        return { ok: true, output: lines.join("\n") };
      }
      return { ok: false, error: "usage: ip a|link|route ..." };
    }

    if (prog === "ss" || prog === "netstat") {
      let out = "Netid  State   Local Address:Port\n";
      for (const [port, svc] of Object.entries(h.services)) {
        out += "tcp    LISTEN  0.0.0.0:" + port + "  (" + svc.name + ")\n";
      }
      return { ok: true, output: out };
    }

    if (prog === "ping") {
      const args = argv.slice(1).filter((a) => a !== "-c" && !/^\d+$/.test(a) || true);
      const target = argv.slice(1).find((a) => !a.startsWith("-") && a !== "3" && a !== "1");
      if (!target) return { ok: false, error: "usage: ping <host|ip>" };
      const r = ping(world, h, target);
      return {
        ok: r.ok,
        output: r.ok
          ? "PING " + target + " ok\n3 packets transmitted, 3 received, 0% packet loss"
          : "",
        error: r.ok ? "" : "PING " + target + ": " + r.reason + "\n100% packet loss",
      };
    }

    if (prog === "dig" || prog === "nslookup") {
      const name = argv[argv.length - 1];
      try {
        const ip = dnsResolve(world, h, name);
        return {
          ok: true,
          output:
            "; <<>> DiG <<>> " +
            name +
            "\n;; ANSWER SECTION:\n" +
            name +
            ".\t30\tIN\tA\t" +
            formatIPv4(ip),
        };
      } catch (e) {
        return { ok: false, error: String(e.message) };
      }
    }

    if (prog === "curl" || prog === "wget" || prog === "iwr" || prog === "invoke-webrequest") {
      const url = argv.slice(1).find((a) => !a.startsWith("-"));
      if (!url) return { ok: false, error: "usage: curl <url>" };
      const m = url.match(/^(https?):\/\/([^/:]+)(?::(\d+))?(\/.*)?$/);
      if (!m) return { ok: false, error: "cannot parse URL " + url };
      const port = Number(m[3] || (m[1] === "https" ? 443 : 80));
      const r = httpGet(world, h, m[2], port, m[4] || "/");
      if (!r.probe.ok)
        return {
          ok: false,
          error: "Failed to connect to " + m[2] + " port " + port + ": " + r.probe.reason,
        };
      return {
        ok: true,
        output: "HTTP/1.1 " + r.status + " OK\n\n" + r.body,
      };
    }

    if (prog === "iptables" || prog === "ufw") {
      if (argv[1] === "-L") {
        let out = "Chain INPUT (policy " + (h.firewallEnabled ? "DROP" : "ACCEPT") + ")\n";
        h.firewallRules.forEach((r, i) => {
          out +=
            i +
            1 +
            "  " +
            (r.action === "allow" ? "ACCEPT" : "DROP") +
            "  " +
            r.proto +
            "  " +
            r.src +
            "  dpt:" +
            (r.port ?? "*") +
            "\n";
        });
        return { ok: true, output: out };
      }
      if (argv[1] === "-F") {
        const n = h.firewallRules.length;
        h.firewallRules = [];
        return { ok: true, output: "flushed " + n + " rules", mutated: true };
      }
      if (argv[1] === "-A") {
        let proto = "any",
          port = null,
          action = "allow",
          src = "any";
        for (let i = 0; i < argv.length; i++) {
          if (argv[i] === "-p") proto = argv[i + 1];
          if (argv[i] === "--dport") port = Number(argv[i + 1]);
          if (argv[i] === "-s") src = argv[i + 1];
          if (argv[i] === "-j") action = /accept/i.test(argv[i + 1]) ? "allow" : "deny";
        }
        const rule = { action, proto, port, src, comment: "iptables" };
        h.firewallRules.push(rule);
        return { ok: true, output: "appended rule " + JSON.stringify(rule), mutated: true };
      }
      return { ok: false, error: "usage: iptables -L|-F|-A INPUT ..." };
    }

    if (prog === "docker") {
      if (argv[1] === "ps") {
        let out = "CONTAINER ID   IMAGE\n";
        for (const [k, v] of Object.entries(h.vars)) {
          if (k.startsWith("container:")) out += k.slice(10) + "   " + v + "\n";
        }
        return { ok: true, output: out };
      }
      if (argv[1] === "run") {
        let name = "ctr",
          publish = null;
        for (let i = 0; i < argv.length; i++) {
          if (argv[i] === "--name") name = argv[i + 1];
          if (argv[i] === "-p") publish = argv[i + 1];
        }
        h.vars["container:" + name] = "running";
        if (publish) {
          const [hostP, contP] = publish.split(":");
          const hostPort = Number(hostP);
          const contPort = Number(String(contP).split("/")[0]);
          const inner = h.services[contPort] || {
            name,
            banner: name + " ok",
            healthy: true,
            proto: "tcp",
          };
          h.services[hostPort] = {
            proto: "tcp",
            name: name + "-publish",
            banner: inner.banner,
            healthy: inner.healthy,
            port: hostPort,
          };
        }
        return { ok: true, output: "started container " + name, mutated: true };
      }
      return { ok: false, error: "usage: docker run -p H:C --name N image" };
    }

    if (prog === "nsupdate" || prog === "dns-add-record") {
      const args = argv.slice(1).filter((a) => !["add", "a", "aaaa", "update"].includes(a.toLowerCase()));
      if (args.length === 2) {
        const parts = args[0].split(".");
        const name = parts[0];
        const zone = parts.slice(1).join(".");
        world.dnsZones[zone] = world.dnsZones[zone] || {};
        world.dnsZones[zone][name + "." + zone] = args[1];
        // also store short key
        world.dnsZones[zone][args[0]] = args[1];
        return { ok: true, output: "added A " + args[0] + " -> " + args[1], mutated: true };
      }
      if (args.length === 3) {
        const [zone, name, ip] = args;
        world.dnsZones[zone] = world.dnsZones[zone] || {};
        world.dnsZones[zone][name + "." + zone] = ip;
        world.dnsZones[zone][name] = ip;
        return { ok: true, output: "added A " + name + "." + zone + " -> " + ip, mutated: true };
      }
      return { ok: false, error: "usage: nsupdate add A <fqdn> <ip>" };
    }

    if (prog === "hostfile") {
      if (argv[1] === "add") {
        h.hostAliases[argv[2].toLowerCase()] = argv[3];
        return { ok: true, output: argv[3] + "    " + argv[2], mutated: true };
      }
      return { ok: false, error: "usage: hostfile add <name> <ip>" };
    }

    if (prog === "sysctl") {
      const joined2 = argv.join(" ");
      if (joined2.includes("net.ipv4.ip_forward=1")) {
        h.vars.ip_forward = "1";
        return { ok: true, output: "net.ipv4.ip_forward = 1", mutated: true };
      }
      return { ok: true, output: "net.ipv4.ip_forward = " + (h.vars.ip_forward || "0") };
    }

    // ---- windows
    if (prog === "ipconfig") {
      let out = "Windows IP Configuration\n\n";
      for (const iface of Object.values(h.interfaces)) {
        out += "Ethernet adapter " + iface.name + ":\n\n";
        if (iface.ip !== null) {
          out += "   IPv4 Address. . . . . . . . . . . : " + formatIPv4(iface.ip) + "\n";
          out += "   Subnet Mask . . . . . . . . . . . : " + prefixToMask(iface.prefix) + "\n";
        }
        if (h.defaultGateway !== null)
          out += "   Default Gateway . . . . . . . . . : " + formatIPv4(h.defaultGateway) + "\n";
        out += "\n";
      }
      return { ok: true, output: out };
    }

    if (prog === "new-netipaddress") {
      const map = flagMap(argv.slice(1));
      const ifaceName = map.interfacealias || map.interfaceindex;
      const ip = map.ipaddress;
      const prefix = Number(map.prefixlength || 24);
      if (!ifaceName || !ip)
        return {
          ok: false,
          error: "usage: New-NetIPAddress -InterfaceAlias X -IPAddress A -PrefixLength N",
        };
      h.interfaces[ifaceName] = h.interfaces[ifaceName] || {
        name: ifaceName,
        mac: "02:00:00:00:00:03",
        state: "up",
        ip: null,
        prefix: 24,
        network: null,
      };
      h.interfaces[ifaceName].ip = parseIPv4(ip);
      h.interfaces[ifaceName].prefix = prefix;
      h.interfaces[ifaceName].state = "up";
      return {
        ok: true,
        output: "IPAddress    : " + ip + "\nInterfaceAlias : " + ifaceName,
        mutated: true,
      };
    }

    if (prog === "new-netroute") {
      const map = flagMap(argv.slice(1));
      const dest = map.destinationprefix;
      const hop = map.nexthop;
      if (!dest || !hop) return { ok: false, error: "usage: New-NetRoute -DestinationPrefix ... -NextHop ..." };
      if (dest === "0.0.0.0/0") {
        h.defaultGateway = parseIPv4(hop);
        h.routes["0.0.0.0/0"] = hop;
      } else h.routes[dest] = hop;
      return { ok: true, output: "DestinationPrefix : " + dest + "\nNextHop           : " + hop, mutated: true };
    }

    if (prog === "route") {
      if (argv[1] === "print") {
        let out = "Network Destination        Netmask          Gateway\n";
        for (const iface of Object.values(h.interfaces)) {
          if (iface.ip !== null)
            out +=
              formatIPv4(iface.ip) +
              "/" +
              iface.prefix +
              " " +
              prefixToMask(iface.prefix) +
              " on-link\n";
        }
        if (h.defaultGateway !== null)
          out += "0.0.0.0          0.0.0.0          " + formatIPv4(h.defaultGateway) + "\n";
        return { ok: true, output: out };
      }
      return { ok: false, error: "usage: route print" };
    }

    if (prog === "get-netadapter") {
      let out =
        "Name                      Status       MacAddress\n----                      ------       ----------\n";
      for (const iface of Object.values(h.interfaces)) {
        out +=
          iface.name +
          "                     " +
          (iface.state === "up" ? "Up" : "Disconnected") +
          "        " +
          iface.mac.replace(/:/g, "-") +
          "\n";
      }
      return { ok: true, output: out };
    }

    if (prog === "enable-netadapter" || prog === "disable-netadapter") {
      const map = flagMap(argv.slice(1));
      const name = map.name;
      if (!name || !h.interfaces[name]) return { ok: false, error: "adapter not found" };
      h.interfaces[name].state = prog === "enable-netadapter" ? "up" : "down";
      return { ok: true, output: name + " " + h.interfaces[name].state, mutated: true };
    }

    if (prog === "test-netconnection" || prog === "tnc") {
      let port = null,
        target = null;
      for (let i = 1; i < argv.length; i++) {
        if (argv[i].toLowerCase() === "-port") port = Number(argv[++i]);
        else if (!argv[i].startsWith("-")) target = argv[i];
      }
      if (!target) return { ok: false, error: "usage: Test-NetConnection [-Port N] host" };
      const icmp = ping(world, h, target);
      let out =
        "ComputerName           : " +
        target +
        "\nPingSucceeded          : " +
        icmp.ok +
        "\n";
      if (port != null) {
        const conn = tcpConnect(world, h, target, port);
        out += "TcpTestSucceeded       : " + conn.ok + "\nRemotePort             : " + port + "\n";
        out += "Detail                 : " + conn.reason;
      } else out += "Detail                 : " + icmp.reason;
      return { ok: true, output: out };
    }

    if (prog === "resolve-dnsname") {
      const name = argv.slice(1).find((a) => !a.startsWith("-"));
      try {
        const ip = dnsResolve(world, h, name);
        return {
          ok: true,
          output:
            "Name                           Type   TTL   Section\n" +
            "----                           ----   ---   -------\n" +
            name +
            "                         A      30    Answer     " +
            formatIPv4(ip),
        };
      } catch (e) {
        return { ok: false, error: String(e.message) };
      }
    }

    if (prog === "netsh") {
      const joined3 = line.toLowerCase();
      if (joined3.includes("add") && joined3.includes("rule")) {
        const nameM = line.match(/name="?([^"]+)"?/i);
        const portM = joined3.match(/localport=(\d+)/);
        const allow = joined3.includes("action=allow");
        const rule = {
          action: allow ? "allow" : "deny",
          proto: joined3.includes("protocol=tcp") ? "tcp" : "any",
          port: portM ? Number(portM[1]) : null,
          src: "any",
          comment: nameM ? nameM[1] : "netsh",
        };
        h.firewallRules.push(rule);
        return { ok: true, output: "Ok.\nAdded rule " + JSON.stringify(rule), mutated: true };
      }
      return { ok: true, output: "Firewall Enabled: " + h.firewallEnabled };
    }

    if (prog === "set-netfirewallprofile") {
      const on = /-enabled\s+true/i.test(line);
      h.firewallEnabled = on;
      return { ok: true, output: "Firewall profile " + (on ? "enabled" : "disabled"), mutated: true };
    }

    return {
      ok: false,
      error:
        prog +
        ": command not found on " +
        h.name +
        " (" +
        h.os +
        "). Try 'help' or 'man'.",
    };
  }

  maybeSolve() {
    if (!this.level || this.solved) return;
    const checks = this.level.goal_checks.map((c) => evaluateCheck(c, this.world, this.currentHost));
    if (checks.every((c) => c.ok)) {
      this.solved = true;
      const id = this.level.id;
      const best = this.level.par || (this.level.solution_commands || []).length || this.commandsIssued;
      const prev = this.progress[id];
      this.progress[id] = {
        solved: true,
        best_commands:
          prev && prev.best_commands != null
            ? Math.min(prev.best_commands, this.commandsIssued)
            : this.commandsIssued,
      };
      this.saveProgress();
    }
  }

  reset() {
    if (this.level) {
      this.world = buildWorld(this.level.start);
      this.currentHost = this.pickStartHost();
    } else {
      this.enterSandbox();
    }
    this.undoStack = [];
    this.commandsIssued = 0;
    this.solved = false;
    return { ok: true, output: "Reset.", mutated: true };
  }

  undo() {
    if (!this.undoStack.length) return { ok: false, error: "nothing to undo" };
    this.restore(this.undoStack.pop());
    return { ok: true, output: "undone", mutated: true };
  }

  ssh(name) {
    if (!this.world.hosts[name]) return { ok: false, error: "ssh: Could not resolve hostname " + name };
    this.currentHost = name;
    return { ok: true, output: "connected to " + name + " (" + this.world.hosts[name].os + ")" };
  }

  setOs(os) {
    if (!["linux", "windows"].includes(String(os).toLowerCase()))
      return { ok: false, error: "usage: os linux|windows" };
    this.host().os = String(os).toLowerCase();
    return { ok: true, output: this.host().name + " now speaks " + os };
  }

  showSolution(run) {
    if (!this.level) return { ok: false, error: "no level loaded" };
    const track = (typeof localStorage !== "undefined" && localStorage.getItem("ln-track")) || "linux";
    const cmds =
      (track === "windows"
        ? this.level.solution_commands_windows
        : this.level.solution_commands_linux) ||
      this.level.solution_commands ||
      [];
    if (!cmds.length) return { ok: false, error: "this level has no recorded solution" };
    this.showSolutionUsed = true;
    if (!run) {
      return {
        ok: true,
        output:
          "Reference solution (" +
          track +
          ") — revealing this forfeits a best score:\n  " +
          cmds.join("\n  "),
      };
    }
    const outs = [];
    for (const line of cmds) {
      const r = this.execute(line);
      outs.push("$ " + line + "\n" + (r.output || r.error || ""));
    }
    this.maybeSolve();
    return { ok: true, output: outs.join("\n"), mutated: true };
  }

  renderLevels() {
    const seqs = {};
    for (const level of Object.values(this.catalog)) {
      (seqs[level.sequence] = seqs[level.sequence] || []).push(level);
    }
    const order = [
      "link",
      "route",
      "dns",
      "ports",
      "firewall",
      "containers",
      "discovery",
      "troubleshoot",
    ];
    const names = {
      link: "Link & Addressing",
      route: "Routing",
      dns: "DNS",
      ports: "Ports & HTTP",
      firewall: "Firewall & Security Groups",
      containers: "Container Networks",
      discovery: "Service Discovery & LB",
      troubleshoot: "Incident Drill",
    };
    let out = "Levels\n======\n";
    for (const key of order) {
      const list = seqs[key] || [];
      if (!list.length) continue;
      out += "\n[" + key + "] " + (names[key] || key) + "\n";
      for (const level of list.sort((a, b) => a.id.localeCompare(b.id))) {
        const p = this.progress[level.id];
        const mark = p && p.solved ? "x" : " ";
        const best = p && p.best_commands != null ? "  best=" + p.best_commands : "";
        out +=
          "  (" + mark + ") " + level.id.padEnd(24) + level.name + "  par=" + (level.par || "?") + best + "\n";
      }
    }
    return out;
  }

  renderHint() {
    if (!this.level) return "No level loaded. Type 'levels' then 'level <id>'.";
    return this.level.hint || "No hint for this level.";
  }

  renderObjective() {
    if (!this.level) return "Sandbox mode — explore freely. Type 'levels' for challenges.";
    return (
      this.level.name +
      "\n\n" +
      this.level.objective +
      "\n\nOS focus: " +
      (this.level.os_focus || []).join(", ")
    );
  }

  renderGoal() {
    if (!this.level) return "No level — no goal. Type 'levels'.";
    let out =
      "Goal — " +
      this.level.name +
      "\n=======================\n" +
      this.level.objective +
      "\n\n";
    for (const check of this.level.goal_checks) {
      const r = evaluateCheck(check, this.world, this.currentHost);
      out +=
        "  [" +
        (r.ok ? "x" : " ") +
        "] " +
        (check.description || check.type) +
        "\n      " +
        r.detail +
        "\n";
    }
    out += "\n";
    if (this.solved) {
      out +=
        "SOLVED in " +
        this.commandsIssued +
        " mutating commands (par " +
        (this.level.par || "?") +
        ")" +
        (this.showSolutionUsed ? " (solution revealed — not a best)" : "");
    } else {
      out += "Not solved yet. Mutating commands used: " + this.commandsIssued;
    }
    return out;
  }

  renderTopology() {
    const lines = ["Network topology", "================", ""];
    for (const [netName, cidr] of Object.entries(this.world.networks).sort()) {
      lines.push("[" + netName + "]  " + formatIPv4(cidr.network) + "/" + cidr.prefix);
      const hosts = Object.values(this.world.hosts).filter((h) =>
        Object.values(h.interfaces).some((i) => i.network === netName)
      );
      if (!hosts.length) {
        lines.push("    (empty)");
      } else {
        for (const host of hosts) {
          const addrs = Object.values(host.interfaces)
            .filter((i) => i.network === netName)
            .map(
              (i) =>
                (i.ip !== null ? formatIPv4(i.ip) + "/" + i.prefix : "-") +
                ":" +
                i.state
            )
            .join(" ");
          const mark = host.os === "windows" ? "W" : "L";
          lines.push(
            "    " + mark + "  " + host.name.padEnd(16) + (addrs || "-").padEnd(28) + "(" + host.role + ")"
          );
        }
      }
      lines.push("");
    }
    lines.push("Legend: L=linux  W=windows");
    return lines.join("\n");
  }

  renderHosts() {
    let out = "HOST              OS        ROLE            PRIMARY IP\n" + "-".repeat(58) + "\n";
    for (const name of Object.keys(this.world.hosts).sort()) {
      const h = this.world.hosts[name];
      const ip = primaryIp(h);
      out +=
        name.padEnd(17) +
        h.os.padEnd(9) +
        h.role.padEnd(15) +
        (ip !== null ? formatIPv4(ip) : "-") +
        "\n";
    }
    return out;
  }

  renderHostInfo(name) {
    const host = this.world.hosts[name || this.currentHost];
    if (!host) return "unknown host";
    let out = "Host " + host.name + "  os=" + host.os + "  role=" + host.role + "\ninterfaces:\n";
    for (const iface of Object.values(host.interfaces)) {
      out +=
        "  " +
        iface.name +
        ": " +
        (iface.ip !== null ? formatIPv4(iface.ip) + "/" + iface.prefix : "no address") +
        " " +
        iface.state +
        "\n";
    }
    out +=
      "default gateway: " +
      (host.defaultGateway !== null ? formatIPv4(host.defaultGateway) : "-") +
      "\n";
    out += "firewall: " + (host.firewallEnabled ? "on" : "off") + " rules=" + host.firewallRules.length + "\n";
    out += "services: " + Object.keys(host.services).join(", ") + "\n";
    return out;
  }
}

const HELP_TEXT = `learn-networking — meta commands
  levels              list sequences and solve status
  level <id>          load a level
  sandbox             free-play mode
  hint                level hint
  goal                goal checks and status
  topo | topology     ASCII topology map
  hosts / hostinfo    inventory
  ssh <host>          switch context
  os linux|windows    switch command dialect
  undo / reset        recover
  solution [--run]    reference solution
  help                this help

Linux: ip, ss, dig, ping, curl, iptables, docker, nsupdate, hostfile
Windows: ipconfig, New-NetIPAddress, New-NetRoute, TNC, Resolve-DnsName, netsh`;

// browser export
if (typeof window !== "undefined") {
  window.LearnNetworking = {
    GameSession,
    buildWorld,
    evaluateCheck,
    parseIPv4,
    formatIPv4,
    HELP_TEXT,
  };
}

if (typeof module !== "undefined") {
  module.exports = {
    GameSession,
    buildWorld,
    evaluateCheck,
    parseIPv4,
    formatIPv4,
    HELP_TEXT,
  };
}
