/**
 * learn-networking web UI controller — dual-track guide + terminal.
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
  const trackPill = document.getElementById("track-pill");
  const guideBody = document.getElementById("guide-body");
  const levelsDialog = document.getElementById("levels-dialog");
  const levelsBody = document.getElementById("levels-body");
  const levelsTrackLabel = document.getElementById("levels-track-label");

  let track = localStorage.getItem("ln-track") || "linux";
  let activeStep = 0;
  const history = [];
  let historyIdx = -1;

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function appendLine(text, cls) {
    const div = document.createElement("div");
    div.className = cls || "line-ok";
    div.textContent = text;
    termOut.appendChild(div);
    termOut.scrollTop = termOut.scrollHeight;
  }

  function appendBlock(text, cls) {
    for (const line of String(text).split("\n")) appendLine(line, cls);
  }

  function currentSteps() {
    return LNSteps.stepsForTrack(session.level, track);
  }

  function markStepDone(step) {
    if (!step.command) return true;
    const cmd = step.command.trim().toLowerCase();
    const optional = !!step.optional;
    // done if the command appears in history (or goal checks all pass at end)
    const hit = session.commandLog.some((c) => {
      const a = c.trim().toLowerCase();
      return a === cmd || a.startsWith(cmd) || cmd.startsWith(a) && a.length > 4;
    });
    return hit || (optional && session.solved);
  }

  function renderGuide() {
    const steps = currentSteps();
    if (!session.level || !steps.length) {
      guideBody.innerHTML =
        '<p class="muted guide-intro">Pick a level to get a numbered walkthrough for the <strong>' +
        escapeHtml(LNSteps.TRACKS[track].label) +
        "</strong> track.<br/>Each step explains <em>why</em>, then gives the exact command.<br/>Click a command to copy it into the terminal.</p>";
      return;
    }

    // auto-advance active step while earlier ones complete
    let firstPending = steps.findIndex((s) => !markStepDone(s));
    if (firstPending === -1) firstPending = steps.length - 1;
    if (activeStep > steps.length - 1) activeStep = firstPending;

    guideBody.innerHTML = "";
    const header = document.createElement("div");
    header.className = "muted";
    header.style.marginBottom = "0.65rem";
    header.innerHTML =
      "<strong>" +
      escapeHtml(session.level.name) +
      "</strong> · " +
      escapeHtml(LNSteps.TRACKS[track].label) +
      " track · follow the steps in order.";
    guideBody.appendChild(header);

    steps.forEach((step, i) => {
      const done = markStepDone(step);
      const el = document.createElement("div");
      el.className =
        "step" +
        (done ? " done" : "") +
        (i === activeStep ? " active" : "") +
        (step.optional ? " optional" : "");
      el.innerHTML =
        '<div class="step-num">' +
        (done ? "✓" : i + 1) +
        "</div><div><div class=\"step-title\">" +
        escapeHtml(step.title) +
        "</div>" +
        (step.command
          ? '<code class="step-cmd" data-cmd="' +
            escapeHtml(step.command) +
            '" title="Click to run">' +
            escapeHtml(step.command) +
            "</code>"
          : "") +
        (step.note
          ? '<div class="step-note">' + escapeHtml(step.note) + "</div>"
          : "") +
        "</div>";
      el.addEventListener("click", (e) => {
        if (e.target.classList.contains("step-cmd")) return;
        activeStep = i;
        renderGuide();
      });
      guideBody.appendChild(el);
    });

    guideBody.querySelectorAll(".step-cmd").forEach((code) => {
      code.addEventListener("click", () => {
        const cmd = code.getAttribute("data-cmd");
        termInput.value = cmd;
        termInput.focus();
        // run immediately for faster follow-along
        termInput.value = "";
        runCommand(cmd);
      });
    });

    // scroll active into view
    const active = guideBody.querySelector(".step.active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  function refreshChrome() {
    termPrompt.textContent = session.prompt();
    const h = session.host();
    hostLabel.textContent = session.currentHost + " · " + h.os;
    modePill.textContent = session.level ? session.level.id : "sandbox";
    scoreLabel.textContent = "commands " + session.commandsIssued;
    trackPill.textContent = track + " track";
    trackPill.classList.toggle("windows-track", track === "windows");

    if (session.level) {
      objectiveTitle.textContent = session.level.name;
      objectiveText.textContent = session.level.objective;
    } else {
      objectiveTitle.textContent = "Sandbox";
      objectiveText.innerHTML =
        "Free-play lab. Type <code>levels</code> or press <strong>Steps</strong> after loading a level.";
    }

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
          '</div><div><div class="goal-title">' +
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
      let ip = "-";
      for (const iface of Object.values(host.interfaces)) {
        if (iface.ip !== null) {
          ip = LearnNetworking.formatIPv4(iface.ip);
          break;
        }
      }
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
        runCommand("ssh " + name);
      });
      hostList.appendChild(li);
    }

    renderGuide();
  }

  function runCommand(raw) {
    const line = (raw || "").trim();
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

    // advance guide to next incomplete step
    const steps = currentSteps();
    if (steps.length) {
      let next = steps.findIndex((s) => !markStepDone(s));
      if (next === -1) next = steps.length - 1;
      activeStep = next;
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

  function setTrack(next) {
    track = next === "windows" ? "windows" : "linux";
    localStorage.setItem("ln-track", track);
    document.querySelectorAll(".track-btn").forEach((btn) => {
      const on = btn.getAttribute("data-track") === track;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    // prefer the track OS on current host for a cleaner prompt
    if (session.world && session.currentHost) {
      const host = session.host();
      const desired = track === "windows" ? "windows" : "linux";
      if (host.os !== desired && session.level && session.level.track === "both") {
        // leave host OS alone — commands are dual
      }
    }
    activeStep = 0;
    if (levelsDialog.open) openLevels();
    refreshChrome();
  }

  function openLevels() {
    levelsTrackLabel.textContent = LNSteps.TRACKS[track].label;
    const buckets = LNSteps.levelsByTrack(session.catalog);
    const list = (buckets[track] || []).slice().sort((a, b) => a.id.localeCompare(b.id));
    const seqs = {};
    for (const level of list) {
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
    levelsBody.innerHTML =
      '<p class="muted" style="margin:0 0 0.85rem">Levels available on the <strong>' +
      escapeHtml(LNSteps.TRACKS[track].label) +
      "</strong> track. Shared drills appear on both tracks with dual commands.</p>";
    for (const [key, title, about] of order) {
      const group = seqs[key] || [];
      if (!group.length) continue;
      const sec = document.createElement("section");
      sec.className = "sequence";
      sec.innerHTML =
        "<h3>" + escapeHtml(title) + '</h3><p class="about">' + escapeHtml(about) + "</p>";
      for (const level of group) {
        const p = session.progress[level.id];
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "level-row";
        btn.innerHTML =
          '<div><div class="id">' +
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
          activeStep = 0;
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
    activeStep = 0;
  });
  document.getElementById("btn-steps").addEventListener("click", () => {
    renderGuide();
    document.getElementById("guide-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
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
  document.getElementById("btn-prev-step").addEventListener("click", () => {
    activeStep = Math.max(0, activeStep - 1);
    renderGuide();
  });
  document.getElementById("btn-next-step").addEventListener("click", () => {
    const steps = currentSteps();
    activeStep = Math.min(steps.length ? steps.length - 1 : 0, activeStep + 1);
    renderGuide();
  });

  document.querySelectorAll(".track-btn").forEach((btn) => {
    btn.addEventListener("click", () => setTrack(btn.getAttribute("data-track")));
  });

  async function boot() {
    appendLine("learn-networking — interactive lab for data & DevOps networking", "line-meta");
    appendLine("Pick a track (Linux / Windows), open Levels, then follow the step-by-step guide.", "line-meta");
    appendLine("");

    try {
      if (!Object.keys(session.catalog).length) {
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
    setTrack(track);
    refreshChrome();
    termInput.focus();
  }

  boot();
})();
