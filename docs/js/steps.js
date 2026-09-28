/**
 * Dual-track step instruction data helpers and guide rendering.
 */
"use strict";

(function (root) {
  const TRACKS = {
    linux: {
      id: "linux",
      label: "Linux",
      os: "linux",
      promptStyle: "bash",
    },
    windows: {
      id: "windows",
      label: "Windows",
      os: "windows",
      promptStyle: "ps",
    },
  };

  /**
   * Normalize a level's steps for a track.
   * Accepts: steps.linux / steps.windows / steps.both / solutionCommands
   */
  function stepsForTrack(level, track) {
    if (!level) return [];
    const s = level.steps || {};
    const list =
      s[track] ||
      s.both ||
      s.shared ||
      (track === "windows"
        ? level.solution_commands_windows
        : level.solution_commands_linux) ||
      level.solution_commands ||
      [];
    return list.map((step, i) => {
      if (typeof step === "string") {
        return {
          title: "Step " + (i + 1),
          command: step,
          note: "",
          optional: false,
        };
      }
      return {
        title: step.title || "Step " + (i + 1),
        command: step.command || "",
        note: step.note || step.why || "",
        optional: !!step.optional,
        check: step.check || null,
      };
    });
  }

  /**
   * Split levels into track buckets.
   * A level with track "both" appears in both lists.
   */
  function levelsByTrack(catalog) {
    const linux = [];
    const windows = [];
    const shared = [];
    for (const level of Object.values(catalog)) {
      const track = (level.track || level.os_focus || ["linux", "windows"]);
      const tracks = Array.isArray(track) ? track : [track];
      const hasLinux = tracks.some((t) => String(t).toLowerCase().includes("linux"));
      const hasWindows = tracks.some((t) => String(t).toLowerCase().includes("win"));
      if (hasLinux && hasWindows) {
        shared.push(level);
        linux.push(level);
        windows.push(level);
      } else if (hasWindows) {
        windows.push(level);
      } else {
        linux.push(level);
        if (!hasWindows) {
          /* linux-only */
        }
      }
    }
    return { linux, windows, shared };
  }

  root.LNSteps = { TRACKS, stepsForTrack, levelsByTrack };
})(typeof window !== "undefined" ? window : globalThis);
