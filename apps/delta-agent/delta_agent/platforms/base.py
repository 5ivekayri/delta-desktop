from abc import ABC, abstractmethod
import getpass
import os
import platform
import socket
import subprocess
import sys
import webbrowser


class BasePlatformAdapter(ABC):
    os_name = "unknown"
    capabilities = ["system_info", "open_url", "open_path", "open_app"]

    def get_system_info(self) -> dict:
        return {"hostname": socket.gethostname(), "os": self.os_name,
                "architecture": platform.machine(), "username": getpass.getuser(), "agent_version": "0.1.0"}

    def open_url(self, url: str):
        if not webbrowser.open(url):
            raise RuntimeError("Browser could not be opened")

    def run(self, arguments: list[str]):
        env = os.environ.copy()
        if getattr(sys, 'frozen', False):
            for key in ('QT_PLUGIN_PATH', 'QML2_IMPORT_PATH'):
                env.pop(key, None)
            if sys.platform.startswith('linux'):
                if 'LD_LIBRARY_PATH_ORIG' in env:
                    env['LD_LIBRARY_PATH'] = env['LD_LIBRARY_PATH_ORIG']
                else:
                    env.pop('LD_LIBRARY_PATH', None)
        subprocess.run(arguments, check=True, timeout=10, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False, env=env)

    @abstractmethod
    def open_path(self, path: str):
        pass

    @abstractmethod
    def open_app(self, app_id: str):
        pass
