# Linux desktop client

Build on Linux with Python 3.12+ in an isolated venv:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]' pyinstaller
.venv/bin/python -m pytest
.venv/bin/python scripts/check_agent_desktop.py
.venv/bin/python scripts/build_agent.py
```

Extract `Delta-Agent-linux.tar.gz`, then run `./Delta Agent/Delta Agent` in the
user's graphical session. Keep `_internal` beside the executable. Requires a
compatible Linux/glibc system, desktop session and host `gio` / `xdg-open`.
This build targets Nobara x86_64; it is not a universal distro package.

The initial server URL is http://localhost:8081; change it under Settings →
connection when connecting to a different machine. Sign in with a Delta account.
No Core environment files, database credentials or saved sessions are packaged.

Installed applications come from XDG_DATA_HOME/applications followed by
XDG_DATA_DIRS/applications, with the freedesktop defaults when unset. User entries
override system entries including Hidden tombstones. NoDisplay, TryExec,
OnlyShowIn and NotShowIn are respected. Exported Flatpak symlinks are supported;
IDs use the export path so upgrades do not change them. Steam game shortcuts
work when installed as .desktop entries; no private Steam library is scraped.

The Agent publishes opaque IDs, names and aliases, never launch paths or Exec
commands. Launches re-resolve the local catalogue and use `gio launch` with an
argument vector and shell=False. GIO handles desktop Exec field codes, working
directory, terminal and D-Bus activation. A desktop file is locally installed
code: trust in installed launchers remains the responsibility of the local user.
Remote callers cannot supply command lines, paths or additional arguments.
Local deny/ask/allow, expiry and disconnect cancellation remain enforced.
Reconnecting refreshes the published catalogue after app installation/removal.

Frozen Linux builds remove PyInstaller library/Qt environment overrides before
invoking host tools, preventing bundled Qt libraries from leaking into apps.

Specification: https://specifications.freedesktop.org/desktop-entry/latest/recognized-keys.html

VS Code is registered with cross-platform aliases `vscode`, `vs code`,
`Visual Studio Code`, `Microsoft Visual Studio Code`, `вскод`, `вс код`,
`вижуал студио код`. Legacy entries are suppressed when an installed app already
advertises that alias, avoiding ambiguous resolution. Matching remains explicit;
no executable path or arbitrary command is inferred from a chat message.

The confirm access mode automatically opens the local approval dialog when a
permitted action arrives on any platform. An explicit deny remains a deny.
Operating-system permissions are separate: the Agent cannot grant itself macOS
privacy access, Windows elevation or Flatpak sandbox permissions. Those must be
approved by the user when the operating system requests them.

## Application inventory

The Applications tab audits registered GUI launchers without executing them.
It lists visible, hidden, overridden and unavailable entries, checks launcher
availability on Linux, and shows effective local access. These are launcher
checks, not a guarantee that every application can successfully start. CLI-only
packages and applications without registered launchers are outside this inventory.

Search accepts names and aliases. Refreshing the server catalogue reconnects the
Agent (and cancels pending approvals). Reconnection now rebuilds registration from
the current installed application catalogue. Export for a model includes only
permitted catalogue IDs, names, aliases and whether confirmation is required;
it excludes local paths, Exec lines, settings, credentials and hidden entries.

For LLM integration use the existing Core tools devices.list_apps and
devices.open_app. Supply catalogue metadata as untrusted data, not instructions.
The model selects a target and an existing app ID/name; the Core resolves it and
Agent applies local policy. Unknown/ambiguous apps should result in clarification,
not invented executables or shell commands. Extend the tool registry with explicit
schemas for future actions. This client change does not configure or replace the
Core model or upload data to an additional model provider.
