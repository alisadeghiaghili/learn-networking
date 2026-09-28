/**
 * learn-networking web UI controller.
 */
"use strict";

(function () {
  const session = new LearnNetworking.GameSession();
  const termOut = document.getElementById("term-out");
  const termInput = document.getElementById("term-input");
  const termForm = document.getElementById("term-form");
  const termPrompt = document.getElementById("term-prompt");
  const goalBox = document.getElementById("goal-box");
  const topoView = document.getElementById("topo-view");
  const hostList = document.getElementById("host-list");
  const objectiveTitle = document.getElementById("objective-title");
  const objectiveText = document.getElementById("objective-text");
  const modePill = document.getElementById("mode-pill");
  const hostLabel = document.getElementById("host-label");
  const scoreLabel = document.getElementById("score-label");
  const levelsDialog = document.getElementById("levels-dialog");
  const levelsBody = document.getElementById("levels-body");

  const history = [];
  let historyIdx = -1;

  function appendLine(text, cls) {
    const div = document.createElement("div");
    div.className = cls || "line-ok";
    div.textContent = text;
    termOut.appendChild(div);
    termOut.scrollTop = termOut.scrollHeight;
  }

  function appendBlock(text, cls) {
    const lines = String(text).split("\n");
    for (const line of lines) appendLine(line, cls);
  }

  function refreshChrome() {
    termPrompt.textContent = session.prompt();
    const h = session.host();
    hostLabel.textContent = session.currentHost + " · " + h.os;
    modePill.textContent = session.level ? session.level.id : "sandbox";
    scoreLabel.textContent = "commands " + session.commandsIssued;

    if (session.level) {
      objectiveTitle.textContent = session.level.name;
      objectiveText.textContent = session.level.objective;
    } else {
      objectiveTitle.textContent = "Sandbox";
      objectiveText.innerHTML =
        "Free-play lab. Type <code>levels</code> to pick a challenge, or explore with <code>ip</code>, <code>ping</code>, <code>ssh</code>.";
    }

    // goals
    if (session.level) {
      const checks = session.level.goal_checks.map((c) =>
        LearnNetworking.evaluateCheck(c, session.world, session.currentHost)
      );
      goalBox.innerHTML = "";
      checks.forEach((r, i) => {
        const check = session.level.goal_checks[i];
        const item = document.createElement("div");
        item.className = "goal-item " + (r.ok ? "ok" : "bad");
        item.innerHTML =
          '<div class="goal-mark">' +
          (r.ok ? "✓" : "") +
          "</div><div><div class=\"goal-title\">" +
          escapeHtml(check.description || check.type) +
          '</div><div class="goal-detail">' +
          escapeHtml(r.detail) +
          "</div></div>";
        goalBox.appendChild(item);
      });
      if (session.solved) {
        const banner = document.createElement("div");
        banner.className = "solved-banner";
        banner.textContent =
          "SOLVED in " +
          session.commandsIssued +
          " mutating commands (par " +
          (session.level.par || "?") +
          ")" +
          (session.showSolutionUsed ? " · solution revealed" : "");
        goalBox.appendChild(banner);
      }
    } else {
      goalBox.innerHTML =
        '<div class="muted">Goal checks appear when a level is loaded.</div>';
    }

    topoView.textContent = session.renderTopology();

    hostList.innerHTML = "";
    for (const name of Object.keys(session.world.hosts).sort()) {
      const host = session.world.hosts[name];
      const li = document.createElement("li");
      if (name === session.currentHost) li.classList.add("active");
      const ip = (function () {
        for (const iface of Object.values(host.interfaces)) {
          if (iface.ip !== null) return LearnNetworking.formatIPv4(iface.ip);
        }
        return "-";
      })();
      li.innerHTML =
        '<div><div class="host-name">' +
        escapeHtml(name) +
        '</div><div class="host-meta">' +
        escapeHtml(ip + " · " + host.role) +
        "</div></div>" +
        '<span class="os-tag ' +
        host.os +
        '">' +
        host.os +
        "</span>";
      li.addEventListener("click", () => {
        const r = session.execute("ssh " + name);
        appendLine("you@local$ ssh " + name, "line-cmd");
        if (r.output) appendBlock(r.output);
        if (r.error) appendBlock(r.error, "line-err");
        refreshChrome();
        termInput.focus();
      });
      hostList.appendChild(li);
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function runCommand(raw) {
    const line = raw.trim();
    if (!line) return;
    appendLine(session.prompt() + " " + line, "line-cmd");
    history.push(line);
    historyIdx = history.length;
    const result = session.execute(line);
    if (result.clear) {
      termOut.innerHTML = "";
    } else {
      if (result.output) appendBlock(result.output);
      if (result.error) appendBlock(result.error, "line-err");
    }
    refreshChrome();
  }

  termForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const value = termInput.value;
    termInput.value = "";
    runCommand(value);
  });

  termInput.addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (historyIdx > 0) {
        historyIdx -= 1;
        termInput.value = history[historyIdx] || "";
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIdx < history.length - 1) {
        historyIdx += 1;
        termInput.value = history[historyIdx] || "";
      } else {
        historyIdx = history.length;
        termInput.value = "";
      }
    }
  });

  function openLevels() {
    const seqs = {};
    for (const level of Object.values(session.catalog)) {
      (seqs[level.sequence] = seqs[level.sequence] || []).push(level);
    }
    const order = [
      ["link", "Link & Addressing", "Interfaces, IPs, CIDR, same-subnet reachability"],
      ["route", "Routing", "Default gateways and static routes across subnets"],
      ["dns", "DNS", "A records, hosts file, service names"],
      ["ports", "Ports & HTTP", "Listeners, TCP, health checks"],
      ["firewall", "Firewall & Security Groups", "Default-deny and allow-listing"],
      ["containers", "Container Networks", "Docker-style publish"],
      ["discovery", "Service Discovery & LB", "ClusterIP DNS and backends"],
      ["troubleshoot", "Incident Drill", "Layered debugging"],
    ];
    levelsBody.innerHTML = "";
    for (const [key, title, about] of order) {
      const list = (seqs[key] || []).sort((a, b) => a.id.localeCompare(b.id));
      if (!list.length) continue;
      const sec = document.createElement("section");
      sec.className = "sequence";
      sec.innerHTML =
        "<h3>" +
        escapeHtml(title) +
        '</h3><p class="about">' +
        escapeHtml(about) +
        "</p>";
      for (const level of list) {
        const p = session.progress[level.id];
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "level-row";
        btn.innerHTML =
          "<div><div class=\"id\">" +
          escapeHtml(level.id) +
          '</div><div class="name">' +
          escapeHtml(level.name) +
          '</div></div><div class="meta">' +
          (p && p.solved ? '<span class="solved-chip">solved</span> · ' : "") +
          "par " +
          (level.par || "?") +
          (p && p.best_commands != null ? " · best " + p.best_commands : "") +
          "</div>";
        btn.addEventListener("click", () => {
          levelsDialog.close();
          runCommand("level " + level.id);
        });
        sec.appendChild(btn);
      }
      levelsBody.appendChild(sec);
    }
    levelsDialog.showModal();
  }

  document.getElementById("btn-levels").addEventListener("click", openLevels);
  document.getElementById("btn-close-levels").addEventListener("click", () => {
    levelsDialog.close();
  });
  document.getElementById("btn-sandbox").addEventListener("click", () => {
    runCommand("sandbox");
  });
  document.getElementById("btn-topo").addEventListener("click", () => {
    runCommand("topo");
  });
  document.getElementById("btn-help").addEventListener("click", () => {
    runCommand("help");
  });
  document.getElementById("btn-hint").addEventListener("click", () => {
    runCommand("hint");
  });
  document.getElementById("btn-refresh-topo").addEventListener("click", () => {
    refreshChrome();
  });

  async function boot() {
    appendLine("learn-networking — interactive lab for data & DevOps networking", "line-meta");
    appendLine("Type 'help' for commands, 'levels' for challenges, 'topo' for the map.", "line-meta");
    appendLine("");

    try {
      const ids = Object.values(session.catalog).length;
      if (!ids) {
        // load levels from JSON files
        const manifest = [
          "levels/link-01-address.json",
          "levels/link-02-ping.json",
          "levels/route-01-default-gw.json",
          "levels/route-02-cross-subnet.json",
          "levels/dns-01-a-record.json",
          "levels/dns-02-hosts-file.json",
          "levels/ports-01-listen.json",
          "levels/ports-02-http-health.json",
          "levels/firewall-01-open-port.json",
          "levels/firewall-02-default-deny.json",
          "levels/containers-01-publish.json",
          "levels/discovery-01-service-dns.json",
          "levels/discovery-02-lb.json",
          "levels/troubleshoot-01-etl-postgres.json",
        ];
        for (const path of manifest) {
          const res = await fetch(path);
          if (!res.ok) continue;
          const level = await res.json();
          session.catalog[level.id] = level;
        }
      }
    } catch (e) {
      appendLine("Failed to load levels: " + e.message, "line-err");
    }

    appendBlock(session.renderTopology(), "line-meta");
    appendLine("");
    refreshChrome();
    termInput.focus();
  }

  boot();
})();
