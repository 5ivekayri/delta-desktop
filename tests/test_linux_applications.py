from unittest.mock import Mock
import threading
import time

from delta_agent.applications import discover
from delta_agent.commands import CommandExecutor
from delta_agent.platforms.linux import LinuxPlatformAdapter


def entry(root, name, extra=''):
    root.mkdir(parents=True, exist_ok=True)
    file = root / name
    file.write_text('[Desktop Entry]\nType=Application\nName=Test App\nExec=/usr/bin/true %U\n' + extra)
    return file


def test_precedence_visibility_and_tryexec(tmp_path, monkeypatch):
    user, system = tmp_path/'user', tmp_path/'system'
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'KDE')
    entry(system, 'hidden.desktop')
    entry(user, 'hidden.desktop', 'Hidden=true\n')
    entry(system, 'missing.desktop', 'TryExec=delta-nonexistent-program\n')
    entry(system, 'gnome.desktop', 'OnlyShowIn=GNOME;\n')
    entry(system, 'excluded.desktop', 'NotShowIn=KDE;\n')
    entry(system, 'nodisplay.desktop', 'NoDisplay=true\n')
    entry(system, 'kde.desktop', 'OnlyShowIn=KDE;\nName[ru]=Приложение\n')
    apps = list(discover('linux', [user, system]).values())
    assert len(apps) == 1
    assert 'Приложение' in apps[0].aliases


def test_flatpak_symlink_stable_id_and_steam(tmp_path):
    exports = tmp_path/'exports'
    exports.mkdir()
    target = entry(tmp_path/'version1', 'org.test.App.desktop')
    link = exports/'org.test.App.desktop'
    link.symlink_to(target)
    first = next(iter(discover('linux', [exports]).values()))
    link.unlink()
    link.symlink_to(entry(tmp_path/'version2', target.name))
    assert next(iter(discover('linux', [exports]))) == first.id
    assert first.path == link
    entry(exports, 'steam-game.desktop', 'X-Steam-AppId=123\n')
    assert len(discover('linux', [exports])) == 2
    link.unlink()
    assert first.id not in discover('linux', [exports])


def test_launch_and_policy(tmp_path):
    entry(tmp_path, 'test.desktop')
    adapter = LinuxPlatformAdapter()
    adapter.installed_applications = lambda: discover('linux', [tmp_path])
    adapter.run = Mock()
    app = next(iter(adapter.installed_applications().values()))
    message = dict(type='command', command_id='linux-test', action='open_app', payload={'app_id':app.id})
    for policy in ['deny', 'ask', 'allow']:
        adapter.run.reset_mock()
        executor = CommandExecutor(adapter, [], permission=lambda _: policy, confirm=lambda *args: False)
        result = executor.execute(message)
        assert result['success'] == (policy == 'allow')
        if policy == 'allow':
            adapter.run.assert_called_once_with(['gio', 'launch', str(app.path)])
        else:
            adapter.run.assert_not_called()
    adapter.run.reset_mock()
    executor = CommandExecutor(adapter, [])
    assert not executor.execute({**message, 'expires_at': time.time()-1})['success']
    cancel = threading.Event(); cancel.set()
    assert not executor.execute(message, cancel)['success']
    assert not executor.execute({**message, 'payload': {'app_id':'/bin/sh'}})['success']
    assert not executor.execute({**message, 'payload': {'app_id': app.id, 'args':['-c', 'true']}})['success']
    adapter.run.assert_not_called()


def test_frozen_launch_uses_host_libraries(monkeypatch):
    from unittest.mock import patch
    import sys
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/bundle/_internal')
    monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', '/host/lib')
    monkeypatch.setenv('QT_PLUGIN_PATH', '/bundle/plugins')
    with patch('delta_agent.platforms.linux.subprocess.run') as run:
        LinuxPlatformAdapter().run(['gio', 'launch', '/local/app.desktop'])
    env = run.call_args.kwargs['env']
    assert env['LD_LIBRARY_PATH'] == '/host/lib'
    assert 'QT_PLUGIN_PATH' not in env
    assert run.call_args.kwargs['shell'] is False
