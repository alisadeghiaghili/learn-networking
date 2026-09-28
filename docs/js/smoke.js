/**
 * Quick smoke test for docs/js/engine.js (run: node docs/js/smoke.js)
 */
"use strict";

const { GameSession, evaluateCheck } = require("./engine.js");

function assert(cond, msg) {
  if (!cond) {
    console.error("FAIL:", msg);
    process.exit(1);
  }
}

const session = new GameSession();
assert(session.world.hosts["web-01"], "sandbox hosts exist");

const level = {
  id: "link-01-address",
  sequence: "link",
  name: "Give It an Address",
  objective: "Assign 10.0.0.30/24",
  hint: "ip addr add",
  start: {
    networks: { lab: "10.0.0.0/24" },
    hosts: {
      "client-01": {
        os: "linux",
        role: "client",
        interfaces: { eth0: { network: "lab", state: "down" } },
      },
      "server-01": {
        os: "linux",
        role: "server",
        interfaces: {
          eth0: { network: "lab", ip: "10.0.0.10", prefix: 24, state: "up" },
        },
      },
    },
  },
  goal_checks: [
    {
      type: "has_ip",
      params: { host: "client-01", iface: "eth0", ip: "10.0.0.30", prefix: 24 },
      description: "has ip",
    },
  ],
  solution_commands: ["ip addr add 10.0.0.30/24 dev eth0"],
  par: 1,
};

session.catalog["link-01-address"] = level;
const load = session.loadLevel("link-01-address");
assert(load.ok, "level loads");
assert(!session.solved, "not solved yet");
const r = session.execute("ip addr add 10.0.0.30/24 dev eth0");
assert(r.ok, "addr add ok");
assert(session.solved, "level solved");
assert(session.commandsIssued === 1, "golf count=1, got " + session.commandsIssued);

const dnsLevel = {
  id: "dns-01",
  sequence: "dns",
  name: "DNS",
  objective: "resolve api.internal",
  hint: "nsupdate",
  start: {
    networks: { lab: "10.0.0.0/24" },
    hosts: {
      c: {
        os: "linux",
        interfaces: { eth0: { network: "lab", ip: "10.0.0.2", prefix: 24, state: "up" } },
        firewall_enabled: false,
        search_domains: ["internal"],
      },
    },
    dns_zones: { internal: {} },
  },
  goal_checks: [
    {
      type: "dns_resolves",
      params: { host: "c", name: "api.internal", ip: "10.0.2.10" },
      description: "api.internal",
    },
  ],
  solution_commands: ["nsupdate add A internal api 10.0.2.10"],
  par: 1,
};
session.catalog["dns-01"] = dnsLevel;
session.loadLevel("dns-01");
const d = session.execute("nsupdate add A internal api 10.0.2.10");
assert(d.ok, "nsupdate ok " + d.error);
assert(session.solved, "dns level solved");

console.log("engine.js smoke OK");
