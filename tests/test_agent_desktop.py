import json
import plistlib
from unittest.mock import Mock

import pytest
from delta_agent.settings import DesktopSettings, load_settings, save_settings, websocket_url
from delta_agent.autostart import set_autostart
from delta_agent.commands import CommandExecutor


@pytest.mark.parametrize('url,expected', [
    ('http://192.168.0.28:8081', 'ws://192.168.0.28:8081/core/ws/agents'),
    ('https://delta.example/core/', 'wss://delta.example/core/ws/agents'),
    ('ws://localhost:8000/ws/agents', 'ws://localhost:8000/ws/agents'),
    ('https://delta.example/ws/agents', 'wss://delta.example/ws/agents'),
])
def test_server_url(url, expected):
    assert websocket_url(url) == expected


@pytest.mark.parametrize('url', ['file:///tmp/x', 'http://user:pass@host',
    'http://host/?token=secret', 'ws://host', 'http://host:invalid', 'http://host/other', 'http://ho\nst'])
def test_invalid_server_url(url):
    with pytest.raises(ValueError):
        websocket_url(url)


def test_settings_roundtrip_and_default_permissions(tmp_path):
    s = DesktopSettings(server='http://localhost:8081', token='test-token-only-123456', name='My Mac')
    assert s.capabilities == ['system_info', 'open_app', 'close_app', 'minimize_app', 'capture_screen']
    assert s.permission('open_app') == 'ask'
    assert not s.model_copy(update={'allow_installed_apps':False}).allow_installed_apps
    assert 'test-token' not in repr(s)
    save_settings(s, tmp_path)
    assert load_settings(tmp_path) == s
    import os
    if os.name != 'nt':
        assert (tmp_path/'settings.json').stat().st_mode & 0o777 == 0o600


def test_permissions_are_enforced_even_for_valid_server_commands(tmp_path):
    adapter = Mock()
    executor = CommandExecutor(adapter, [str(tmp_path)], ['system_info'], [])
    def execute(action, payload):
        return executor.execute({'type':'command','command_id':'id','action':action,'payload':payload})
    assert not execute('open_url', {'url':'https://example.com'})['success']
    assert not execute('open_path', {'path':str(tmp_path)})['success']
    assert not execute('open_app', {'app_id':'vscode'})['success']
    adapter.open_url.assert_not_called()
    adapter.open_path.assert_not_called()
    adapter.open_app.assert_not_called()
    executor.capabilities.add('open_app')
    assert not execute('open_app', {'app_id':'vscode'})['success']
    executor.allowed_apps.add('vscode')
    assert execute('open_app', {'app_id':'vscode'})['success']


def test_symlink_escape_rejected(tmp_path):
    allowed = tmp_path/'allowed'; allowed.mkdir()
    other = tmp_path/'private'; other.mkdir()
    (allowed/'link').symlink_to(other, target_is_directory=True)
    adapter = Mock()
    executor = CommandExecutor(adapter, [str(allowed)], ['open_path'], [])
    result = executor.execute({'type':'command','command_id':'id','action':'open_path',
                               'payload':{'path':str(allowed/'link')}})
    assert not result['success']
    adapter.open_path.assert_not_called()


def test_macos_autostart_preserves_space_in_path(tmp_path):
    command = ['/Applications/Delta Agent.app/Contents/MacOS/Delta Agent', '--background']
    set_autostart(True, platform='darwin', home=tmp_path, command=command)
    file = tmp_path/'Library/LaunchAgents/org.delta.agent.plist'
    assert plistlib.loads(file.read_bytes())['ProgramArguments'] == command
    set_autostart(False, platform='darwin', home=tmp_path, command=command)
    assert not file.exists()


def test_linux_autostart_quotes_fixed_executable(tmp_path):
    set_autostart(True, platform='linux', home=tmp_path, command=['/home/me/Delta Agent', '--background'])
    file = tmp_path/'.config/autostart/delta-agent.desktop'
    assert 'Exec="/home/me/Delta Agent" "--background"' in file.read_text()
    set_autostart(False, platform='linux', home=tmp_path)
    assert not file.exists()


def test_desktop_timeout_is_not_reported_as_success(tmp_path):
    from subprocess import TimeoutExpired
    adapter = Mock()
    adapter.open_path.side_effect = TimeoutExpired('open', 10)
    result = CommandExecutor(adapter, [str(tmp_path)], ['open_path'], []).execute({
        'type':'command','command_id':'id','action':'open_path','payload':{'path':str(tmp_path)}})
    assert not result['success'] and result['error_code'] == 'ACTION_TIMEOUT'
    adapter.open_path.assert_called_once()


async def test_desktop_protocol_registers_local_policy_and_rejects_remote_override(tmp_path, monkeypatch):
    import asyncio
    from contextlib import suppress
    from websockets.asyncio.server import serve
    from delta_agent.main import run_agent
    adapter = Mock()
    adapter.get_system_info.return_value = dict(hostname='test', os='macos', architecture='arm64', username='test', agent_version='0.1.0')
    monkeypatch.setattr('delta_agent.main.get_platform', lambda: adapter)
    results = asyncio.Queue()
    registrations = []
    events = []
    async def server(socket):
        registrations.append(json.loads(await socket.recv()))
        await socket.send(json.dumps({'type':'register_ack','device_id':'test-device','heartbeat_interval':1}))
        await socket.send(json.dumps({'type':'command','command_id':'remote','action':'open_app','payload':{'app_id':'vscode'}}))
        async for raw in socket:
            item = json.loads(raw)
            if item['type'] == 'command_result':
                await results.put(item)
                await socket.close()
                break
    async with serve(server, '127.0.0.1', 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        task = asyncio.create_task(run_agent(f'ws://127.0.0.1:{port}/ws/agents', 'test-token-only-123456',
            'My Mac', tmp_path, [], capabilities=['system_info'], allowed_apps=[], on_event=events.append))
        try:
            for _ in range(2):
                result = await asyncio.wait_for(results.get(), 5)
                assert not result['success'] and result['error_code'] == 'INVALID_COMMAND'
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
    assert registrations[0]['device_uid'] == registrations[1]['device_uid']
    assert registrations[0]['capabilities'] == ['system_info']
    assert any(event['event'] == 'connected' for event in events)
    adapter.open_app.assert_not_called()


@pytest.mark.parametrize('mode,override,expected', [
    ('confirm', None, 'ask'), ('full', None, 'allow'),
    ('full', 'deny', 'deny'), ('full', 'ask', 'ask'), ('confirm', 'allow', 'allow')])
def test_command_modes_and_overrides(mode, override, expected, tmp_path):
    settings = DesktopSettings(server='http://localhost:8081', token='test-token-only-123456', name='PC',
        access_mode=mode, allow_urls=True,
        command_permissions={'open_url':override} if override else {})
    assert settings.permission('open_url') == expected
    assert ('open_url' in settings.capabilities) == (expected != 'deny')
    save_settings(settings, tmp_path)
    assert load_settings(tmp_path) == settings


@pytest.mark.parametrize('policy,approved,success', [
    ('deny',True,False),('ask',False,False),('ask',True,True),('allow',False,True)])
def test_command_approval_before_os_execution(policy, approved, success):
    adapter = Mock()
    confirm = Mock(return_value=approved)
    executor = CommandExecutor(adapter, [], ['open_url'], [], lambda _:policy, confirm)
    result = executor.execute({'type':'command','command_id':'id','action':'open_url','payload':{'url':'https://example.com'}})
    assert result['success'] == success
    assert adapter.open_url.call_count == int(success)
    assert confirm.call_count == int(policy == 'ask')


def test_approval_cannot_bypass_validation_or_missing_ui(tmp_path):
    adapter = Mock()
    confirm = Mock(return_value=True)
    executor = CommandExecutor(adapter, [], ['open_url','open_path'], [], lambda _:'ask', confirm)
    for action,payload in [('open_url',{'url':'file:///tmp/private'}),('open_path',{'path':str(tmp_path)})]:
        assert not executor.execute({'type':'command','command_id':'id','action':action,'payload':payload})['success']
    confirm.assert_not_called()
    executor.confirm = None
    assert not executor.execute({'type':'command','command_id':'id','action':'open_url','payload':{'url':'https://example.com'}})['success']
    adapter.open_url.assert_not_called()


def test_approval_expiry_disconnect_and_path_revalidation(tmp_path):
    import time
    from threading import Event
    adapter = Mock()
    cancelled = Event()
    def approve(*args):
        cancelled.set()
        return True
    executor = CommandExecutor(adapter, [], ['open_url'], [], lambda _:'ask', approve)
    message={'type':'command','command_id':'id','action':'open_url','payload':{'url':'https://example.com'}}
    assert executor.execute(message,cancelled)['error_code'] == 'COMMAND_EXPIRED'
    cancelled.clear()
    message['expires_at'] = time.time()-1
    assert executor.execute(message,cancelled)['error_code'] == 'COMMAND_EXPIRED'
    adapter.open_url.assert_not_called()
    allowed=tmp_path/'allowed'; allowed.mkdir()
    target=allowed/'target'; target.mkdir()
    private=tmp_path/'private'; private.mkdir()
    def swap(*args):
        target.rmdir(); target.symlink_to(private, target_is_directory=True)
        return True
    executor = CommandExecutor(adapter, [str(allowed)], ['open_path'], [], lambda _:'ask', swap)
    assert not executor.execute({'type':'command','command_id':'id','action':'open_path','payload':{'path':str(target)}})['success']
    adapter.open_path.assert_not_called()


async def test_disconnect_cancels_approval_while_heartbeats_continue(tmp_path):
    import asyncio
    import threading
    from websockets.asyncio.server import serve
    from delta_agent.main import run_agent
    from delta_agent.platforms.base import BasePlatformAdapter
    adapter=Mock()
    adapter.capabilities=['open_url']
    adapter.get_system_info.return_value={'hostname':'test','os':'linux','architecture':'test','username':'test','agent_version':'0.1.0'}
    entered=threading.Event()
    stopped=threading.Event()
    received_heartbeat=asyncio.Event()
    def confirm(action,payload,expires,cancelled):
        entered.set()
        cancelled.wait(3)
        stopped.set()
        return True  # Even a late approval cannot run after the disconnect.
    async def server(socket):
        registration=json.loads(await socket.recv())
        assert registration['approval_timeout']==60
        await socket.send(json.dumps({'type':'register_ack','device_id':'test','heartbeat_interval':.05}))
        await socket.send(json.dumps({'type':'command','command_id':'test','action':'open_url','payload':{'url':'https://example.com'}}))
        while not entered.is_set():
            await asyncio.sleep(.01)
        assert json.loads(await socket.recv())['type']=='heartbeat'
        received_heartbeat.set()
        await socket.close()
    async with serve(server,'127.0.0.1',0) as host:
        port=host.sockets[0].getsockname()[1]
        task=asyncio.create_task(run_agent(f'ws://127.0.0.1:{port}', 'test-token-only-123456', 'test', tmp_path, [],
            adapter=adapter, permission=lambda _:'ask', confirm=confirm))
        try:
            await asyncio.wait_for(received_heartbeat.wait(),3)
            assert await asyncio.to_thread(stopped.wait,2)
            adapter.open_url.assert_not_called()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
