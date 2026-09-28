"""Meta commands shared across OS dialects (LGB-style game controls)."""

from __future__ import annotations

from learn_networking.commands.router import CommandContext, CommandResult


def cmd_levels(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """List level sequences and progress."""
    return CommandResult.out(ctx.session.render_levels())


def cmd_level(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Load a level by id."""
    if len(argv) < 2:
        return CommandResult.fail("usage: level <id>")
    return ctx.session.load_level(argv[1])


def cmd_hint(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Show the current level hint."""
    return CommandResult.out(ctx.session.render_hint())


def cmd_goal(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Show goal and per-check status."""
    return CommandResult.out(ctx.session.render_goal())


def cmd_objective(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Show the objective blurb."""
    return CommandResult.out(ctx.session.render_objective())


def cmd_reset(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Reset the world to the level start (or sandbox default)."""
    return ctx.session.reset()


def cmd_undo(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Undo the last mutating command."""
    return ctx.session.undo()


def cmd_topo(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Render ASCII topology."""
    return CommandResult.out(ctx.session.render_topology())


def cmd_hosts(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """List hosts and primary IPs."""
    return CommandResult.out(ctx.session.render_hosts())


def cmd_hostinfo(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Show detail for one host."""
    name = argv[1] if len(argv) > 1 else ctx.session.current_host().name
    return CommandResult.out(ctx.session.render_hostinfo(name))


def cmd_ssh(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Switch the active host context (passwordless ops login)."""
    if len(argv) < 2:
        return CommandResult.fail("usage: ssh <hostname>")
    return ctx.session.ssh(argv[1])


def cmd_os(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Switch the command dialect on the current host."""
    if len(argv) < 2 or argv[1].lower() not in ("linux", "windows"):
        return CommandResult.fail("usage: os linux|windows")
    return ctx.session.set_os(argv[1].lower())


def cmd_solution(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Run or print the reference solution (marks level as non-best)."""
    track = None
    if "--windows" in argv or "-w" in argv:
        track = "windows"
    elif "--linux" in argv:
        track = "linux"
    return ctx.session.show_solution(run="--run" in argv or "-r" in argv, track=track)


def cmd_help(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Show command help."""
    return CommandResult.out(HELP_TEXT)


def cmd_sandbox(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Enter free-play sandbox."""
    return ctx.session.enter_sandbox()


def cmd_clear(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Ask the UI to clear the screen (prints ANSI clear)."""
    return CommandResult.out("\033[2J\033[H")


def cmd_whoami(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Show current user@host."""
    host = ctx.session.current_host()
    user = "you" if host.os.value == "linux" else "Administrator"
    return CommandResult.out(f"{user}@{host.name}")


def cmd_man(ctx: CommandContext, argv: list[str]) -> CommandResult:
    """Show a short man-page-style help for a command family."""
    topic = argv[1].lower() if len(argv) > 1 else ""
    page = MAN_PAGES.get(topic)
    if not page:
        return CommandResult.fail(f"man: no entry for {topic!r}")
    return CommandResult.out(page)


HELP_TEXT = """\
learn-networking — meta commands
  levels              list sequences and solve status
  level <id>          load a level
  sandbox             free-play mode
  hint                level hint
  goal | show goal    goal checks and status
  objective           level objective
  topo | topology     ASCII topology map
  hosts               host inventory
  hostinfo [host]     host detail
  ssh <host>          switch context
  os linux|windows    switch command dialect
  undo                undo last mutating command
  reset               restore start world
  solution [--run]    print (or run) reference solution
  whoami              current user@host
  help | ?            this help
  man <topic>         short manual (ip, dns, firewall, docker, win)

Linux surface (on a linux host):   ip, ss, dig, ping, curl, iptables, docker
Windows surface (windows host):    ipconfig, Get-Net*, Test-NetConnection,
                                   Resolve-DnsName, New-Net*, netsh, route
"""

MAN_PAGES = {
    "ip": """\
ip(8) — Linux network configuration

  ip a                         show addresses
  ip addr add A/P dev IF       add address
  ip link set IF up|down       admin state
  ip r                         show routes
  ip route add CIDR via HOP    add static route
""",
    "dns": """\
DNS inspection

  dig <name>                   query A record (linux)
  nslookup <name>              either OS
  Resolve-DnsName <name>       windows
Resolution order: hosts file → zones → search domains.
""",
    "firewall": """\
Host firewall (default deny when enabled)

  iptables -L                  list (linux)
  iptables -A INPUT -p tcp --dport N -j ACCEPT
  iptables -F                  flush
  netsh advfirewall firewall add rule name="..." protocol=tcp localport=N action=allow
  Set-NetFirewallProfile -Enabled False
""",
    "docker": """\
Container networking (simplified)

  docker ps
  docker run -d --name N -p HOST:CONTAINER image
Published ports appear as host listeners forwarding to the container port.
""",
    "win": """\
Windows surfaces

  ipconfig | ipconfig /all
  Get-NetAdapter
  Enable-NetAdapter / Disable-NetAdapter -Name X
  New-NetIPAddress -InterfaceAlias X -IPAddress A -PrefixLength N
  New-NetRoute -DestinationPrefix CIDR -NextHop IP
  Test-NetConnection [-Port N] host
  Resolve-DnsName name
  Invoke-WebRequest url
""",
}

META_HANDLERS = {
    "meta_levels": cmd_levels,
    "meta_level": cmd_level,
    "meta_hint": cmd_hint,
    "meta_goal": cmd_goal,
    "meta_objective": cmd_objective,
    "meta_reset": cmd_reset,
    "meta_undo": cmd_undo,
    "meta_topo": cmd_topo,
    "meta_hosts": cmd_hosts,
    "meta_hostinfo": cmd_hostinfo,
    "meta_ssh": cmd_ssh,
    "meta_os": cmd_os,
    "meta_solution": cmd_solution,
    "meta_help": cmd_help,
    "meta_sandbox": cmd_sandbox,
    "meta_clear": cmd_clear,
    "meta_whoami": cmd_whoami,
    "meta_man": cmd_man,
}
