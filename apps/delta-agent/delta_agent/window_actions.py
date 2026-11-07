"""OS window actions for locally discovered application IDs; no process killing."""
import configparser
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys


class WindowNotFoundError(LookupError):
    pass


def host_environment():
    env = os.environ.copy()
    if getattr(sys, 'frozen', False):
        original = env.pop('LD_LIBRARY_PATH_ORIG', None)
        if original is None:
            env.pop('LD_LIBRARY_PATH', None)
        else:
            env['LD_LIBRARY_PATH'] = original
        for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
            env.pop(key, None)
    return env


def command(args):
    result = subprocess.run(args, check=True, timeout=10, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False, env=host_environment())
    return result.stdout


def window_classes(app):
    values = {app.path.stem, app.name, *app.aliases}
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.read(app.path, encoding='utf-8')
    section = config['Desktop Entry']
    values.update(section.get(key, '') for key in ('StartupWMClass', 'X-Flatpak'))
    return {v.casefold().removesuffix('.desktop') for v in values if v}


def linux_windows(app):
    identities = window_classes(app)
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        windows = json.loads(command(['hyprctl', 'clients', '-j']))
        return 'hyprland', [w for w in windows if
            {str(w.get('class', '')).casefold(), str(w.get('initialClass', '')).casefold()} & identities
            and re.fullmatch(r'0x[0-9a-fA-F]+', str(w.get('address', '')))]
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        raise NotImplementedError('Window actions currently require Hyprland or X11 on Linux')
    windows = []
    for line in command(['wmctrl', '-lx']).splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4 and re.fullmatch(r'0x[0-9a-fA-F]+', parts[0]):
            if {v.casefold() for v in parts[2].split('.')} & identities or parts[2].casefold() in identities:
                windows.append({'address': parts[0]})
    return 'x11', windows


def restore_linux_app(app):
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        return False
    backend, windows = linux_windows(app)
    hidden = [w for w in windows if w.get('workspace', {}).get('name') == 'special:delta-minimized']
    if not hidden:
        return False
    workspace = int(json.loads(command(['hyprctl', 'activeworkspace', '-j']))['id'])
    if workspace < 1:
        workspace = 1
    for window in hidden:
        result = command(['hyprctl', 'dispatch', 'movetoworkspace', f"{workspace},address:{window['address']}"])
        if result.strip() != 'ok':
            raise RuntimeError('Compositor rejected restoring the window')
    return True


def manage_app(os_name, app, action):
    if action not in {'close_app', 'minimize_app'}:
        raise ValueError('Unsupported window action')
    if os_name == 'linux':
        backend, windows = linux_windows(app)
        if not windows:
            raise WindowNotFoundError('No matching running window')
        for window in windows:
            address = window['address']
            if backend == 'hyprland':
                args = ['hyprctl', 'dispatch', 'closewindow', 'address:'+address] if action == 'close_app' else [
                    'hyprctl', 'dispatch', 'movetoworkspacesilent', 'special:delta-minimized,address:'+address]
                if command(args).strip() != 'ok':
                    raise RuntimeError('Compositor rejected window action')
            elif action == 'close_app':
                command(['wmctrl', '-ic', address])
            else:
                import ctypes
                x11 = ctypes.CDLL('libX11.so.6')
                x11.XOpenDisplay.argtypes = [ctypes.c_char_p]; x11.XOpenDisplay.restype = ctypes.c_void_p
                x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
                x11.XIconifyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int]
                x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
                display = x11.XOpenDisplay(None)
                if not display:
                    raise RuntimeError('Cannot open X display')
                try:
                    if not x11.XIconifyWindow(display, int(address, 16), x11.XDefaultScreen(display)):
                        raise RuntimeError('Window manager rejected minimization')
                finally:
                    x11.XCloseDisplay(display)
        return {'requested_windows': len(windows), 'operation': action}
    if os_name == 'macos':
        from AppKit import NSRunningApplication
        with (app.path/'Contents/Info.plist').open('rb') as file:
            bundle = plistlib.load(file).get('CFBundleIdentifier')
        if not bundle:
            raise ValueError('Application bundle identity is missing')
        running = NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle)
        if not running:
            raise WindowNotFoundError('Application is not running')
        accepted = [process.terminate() if action == 'close_app' else process.hide() for process in running]
        if not all(accepted):
            raise PermissionError('Operating system rejected application request')
        return {'requested_windows':len(accepted), 'operation':action}
    if os_name == 'windows':
        import ctypes
        from ctypes import wintypes
        import win32com.client
        import win32gui
        import win32process
        import pythoncom
        pythoncom.CoInitialize()
        try:
            shortcut = win32com.client.Dispatch('WScript.Shell').CreateShortCut(str(app.path))
            target = Path(os.path.expandvars(shortcut.TargetPath)).resolve()
        finally:
            pythoncom.CoUninitialize()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        windows=[]
        def visit(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):return
            _,pid=win32process.GetWindowThreadProcessId(hwnd)
            process=kernel.OpenProcess(0x1000,False,pid)
            if not process:return
            try:
                buffer=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(buffer))
                if kernel.QueryFullProcessImageNameW(process,0,buffer,ctypes.byref(size)) and Path(buffer.value).resolve()==target:
                    windows.append(hwnd)
            finally:kernel.CloseHandle(process)
        win32gui.EnumWindows(visit,None)
        if not windows:raise WindowNotFoundError('No matching running window')
        for hwnd in windows:
            if action=='close_app':win32gui.PostMessage(hwnd,0x0010,0,0)  # WM_CLOSE; never TerminateProcess
            else:win32gui.ShowWindow(hwnd,6)  # SW_MINIMIZE
        return {'requested_windows':len(windows),'operation':action}
    raise NotImplementedError('Unsupported platform')
