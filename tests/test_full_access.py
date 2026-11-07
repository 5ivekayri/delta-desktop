from unittest.mock import Mock
import threading
import pytest
from delta_agent.commands import CommandExecutor
from delta_agent.settings import DesktopSettings,save_settings,load_settings
from delta_agent import macos_permissions

ACTIONS=['system_info','open_url','open_path','open_app','close_app','minimize_app','capture_screen']


def test_full_access_persists_and_explicit_overrides_survive(tmp_path):
    settings=DesktopSettings(server='http://localhost:8081',token='test-token-only-123456',name='pc',
        command_permissions={'system_info':'ask','capture_screen':'ask','open_url':'deny'})
    settings.enable_full_access();save_settings(settings,tmp_path)
    loaded=load_settings(tmp_path)
    assert loaded.access_mode=='full'
    assert all(loaded.permission(a)=='allow' for a in ACTIONS if a!='open_url')
    assert loaded.permission('open_url')=='deny'
    loaded.command_permissions['close_app']='ask'
    assert loaded.permission('close_app')=='ask'
    loaded.access_mode='confirm'
    assert loaded.permission('capture_screen')=='ask'


@pytest.mark.parametrize('action',['system_info','close_app','minimize_app','capture_screen'])
def test_full_mode_repeated_commands_never_prompt(action):
    adapter=Mock();adapter.capabilities=ACTIONS;adapter.get_system_info.return_value={};adapter.capture_screen.return_value={};adapter.manage_app.return_value={}
    app=Mock(name='installed app');app.name='Example';adapter.installed_applications.return_value={'installed-'+'a'*24:app}
    settings=DesktopSettings(server='http://localhost:8081',token='test-token-only-123456',name='pc',access_mode='full')
    confirm=Mock(side_effect=AssertionError('No recurring permission prompt'))
    executor=CommandExecutor(adapter,[],permission=settings.permission,confirm=confirm)
    payload={'app_id':'installed-'+'a'*24} if action in {'close_app','minimize_app'} else {}
    for _ in range(3):assert executor.execute({'command_id':'one','action':action,'payload':payload})['success']
    confirm.assert_not_called()
    cancelled=threading.Event();cancelled.set()
    assert executor.execute({'command_id':'one','action':action,'payload':payload},cancelled)['error_code']=='COMMAND_EXPIRED'


def test_macos_request_once_and_recheck_real_os_permission(tmp_path,monkeypatch):
    native=Mock();native.CGPreflightScreenCaptureAccess.return_value=False
    monkeypatch.setattr(macos_permissions,'core_graphics',lambda:native)
    assert not macos_permissions.request_screen_recording_once(tmp_path)
    assert not macos_permissions.request_screen_recording_once(tmp_path)
    native.CGRequestScreenCaptureAccess.assert_called_once()
    assert not macos_permissions.screen_recording_allowed()
    native.CGPreflightScreenCaptureAccess.return_value=True
    assert macos_permissions.request_screen_recording_once(tmp_path)
    assert macos_permissions.screen_recording_allowed()
    assert native.CGRequestScreenCaptureAccess.call_count==1
    native.CGPreflightScreenCaptureAccess.return_value=False
    assert not macos_permissions.request_screen_recording_once(tmp_path,retry=True)
    assert native.CGRequestScreenCaptureAccess.call_count==2
