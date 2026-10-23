"""Opt-in user-session startup; no system service or elevated permissions."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys


def startup_command():
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--background']
    return [sys.executable, '-m', 'delta_agent.desktop', '--background']


def set_autostart(enabled: bool, *, platform=None, home=None, command=None):
    platform = platform or sys.platform
    home = home or Path.home()
    command = command or startup_command()
    if platform == 'darwin':
        file = home / 'Library/LaunchAgents/org.delta.agent.plist'
        content = plistlib.dumps({'Label': 'org.delta.agent', 'ProgramArguments': command,
                                 'RunAtLoad': True, 'ProcessType': 'Interactive'})
    elif platform == 'win32':
        # Registry Run launches a fixed local program; no shell or credentials.
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if enabled:
                winreg.SetValueEx(key, 'DeltaAgent', 0, winreg.REG_SZ, subprocess.list2cmdline(command))
            else:
                try:
                    winreg.DeleteValue(key, 'DeltaAgent')
                except FileNotFoundError:
                    pass
        return
    else:
        file = home / '.config/autostart/delta-agent.desktop'
        # Desktop Entry specification quoting, not shell quoting.
        def quote(arg):
            if any(c in arg for c in '\n\r'):
                raise ValueError('Invalid startup path')
            return '"' + arg.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
        content = ('[Desktop Entry]\nType=Application\nName=Delta Agent\nExec=' +
                   ' '.join(map(quote, command)) + '\nTerminal=false\n').encode()
    if enabled:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
        os.chmod(file, 0o600)
    else:
        file.unlink(missing_ok=True)
