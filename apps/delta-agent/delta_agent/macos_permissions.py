"""Request macOS screen recording during local setup, never on each command.

The OS alone grants access. A marker records an attempted prompt, not permission;
CGPreflightScreenCaptureAccess is always the source of truth.
"""
import ctypes
from pathlib import Path
import subprocess


def core_graphics():
    library = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    for name in ('CGPreflightScreenCaptureAccess', 'CGRequestScreenCaptureAccess'):
        function = getattr(library, name)
        function.argtypes = []
        function.restype = ctypes.c_bool
    return library


def screen_recording_allowed():
    return bool(core_graphics().CGPreflightScreenCaptureAccess())


def request_screen_recording_once(directory: Path, retry=False):
    library = core_graphics()
    if library.CGPreflightScreenCaptureAccess():
        return True
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory/'macos-screen-permission-requested'
    if retry:
        marker.unlink(missing_ok=True)
    try:
        with marker.open('x') as file:
            file.write('Screen permission was requested; actual status is managed by macOS.\n')
    except FileExistsError:
        return False
    library.CGRequestScreenCaptureAccess()
    return bool(library.CGPreflightScreenCaptureAccess())


def open_screen_settings():
    subprocess.run(['/usr/bin/open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'],
                   check=True, timeout=10, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
