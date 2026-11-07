import os
import subprocess
import sys

from .base import BasePlatformAdapter


class LinuxPlatformAdapter(BasePlatformAdapter):
    os_name = "linux"

    def run(self, arguments: list[str]):
        # PyInstaller's Qt libraries must not leak into host gio / launched apps.
        env = os.environ.copy()
        if getattr(sys, 'frozen', False):
            original = env.pop('LD_LIBRARY_PATH_ORIG', None)
            if original is None:
                env.pop('LD_LIBRARY_PATH', None)
            else:
                env['LD_LIBRARY_PATH'] = original
            for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
                env.pop(key, None)
        subprocess.run(arguments, check=True, timeout=10, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       shell=False, env=env)

    def open_installed_app(self, app_id: str):
        from delta_agent.window_actions import restore_linux_app
        app = self.installed_applications().get(app_id)
        if app is None:
            raise ValueError('Application no longer installed')
        if not restore_linux_app(app):
            super().open_installed_app(app_id)

    def open_path(self, path: str):
        self.run(["xdg-open", path])

    def open_app(self, app_id: str):
        if app_id == "browser":
            self.open_url("https://example.com")
        elif app_id == "vscode":
            self.run(["code", "--new-window"])
        else:
            raise ValueError("Unsupported application")
