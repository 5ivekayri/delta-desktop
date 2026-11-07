import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from delta_agent.applications import InstalledApp
from delta_agent.commands import CommandExecutor
from delta_agent.settings import DesktopSettings
from delta_agent.window_actions import manage_app, WindowNotFoundError


def app_entry(tmp_path):
    path=tmp_path/'com.visualstudio.code.desktop'
    path.write_text('[Desktop Entry]\nName=Visual Studio Code\nStartupWMClass=Code\n')
    return InstalledApp('installed-'+'a'*24,'Visual Studio Code',path)


@pytest.mark.parametrize('action,dispatcher', [('close_app','closewindow'),('minimize_app','movetoworkspacesilent')])
def test_hyprland_targets_only_exact_local_window(tmp_path,monkeypatch,action,dispatcher):
    app=app_entry(tmp_path);monkeypatch.setenv('HYPRLAND_INSTANCE_SIGNATURE','test')
    calls=[]
    def run(args):
        calls.append(args)
        if args==['hyprctl','clients','-j']:
            return json.dumps([{'address':'0x123','class':'Code'}, {'address':'0x456','class':'Other Code'},
                               {'address':'0xBAD;evil','class':'Code'}])
        return 'ok\n'
    monkeypatch.setattr('delta_agent.window_actions.command',run)
    assert manage_app('linux',app,action)['requested_windows']==1
    assert calls[-1][2]==dispatcher and calls[-1][-1].endswith('address:0x123')
    assert len(calls)==2


def test_close_missing_and_unpermitted_never_runs(tmp_path):
    adapter=Mock();adapter.capabilities=['close_app','minimize_app'];adapter.installed_applications.return_value={}
    result=CommandExecutor(adapter,[]).execute({'command_id':'1','action':'close_app','payload':{'app_id':'installed-'+'a'*24}})
    assert result['error_code']=='APP_NOT_AVAILABLE'
    adapter.manage_app.assert_not_called()


def test_capture_always_requires_consent_and_honors_deny():
    adapter=Mock();adapter.capabilities=['capture_screen'];adapter.capture_screen.return_value={'image_url':'test'}
    message={'command_id':'1','action':'capture_screen','payload':{}}
    for policy in ['allow','ask','deny']:
        confirm=Mock(return_value=False)
        result=CommandExecutor(adapter,[],permission=lambda _:policy,confirm=confirm).execute(message)
        assert not result['success']
        adapter.capture_screen.assert_not_called()
        assert confirm.call_count==(0 if policy=='deny' else 1)
    confirm=Mock(return_value=True)
    assert CommandExecutor(adapter,[],permission=lambda _:'allow',confirm=confirm).execute(message)['success']
    adapter.capture_screen.assert_called_once()
    s=DesktopSettings(server='http://localhost:8081',token='test-token-123456789',name='pc',access_mode='full',command_permissions={'capture_screen':'allow'})
    assert s.permission('capture_screen')=='ask' and s.permission('close_app')=='ask'


def test_capture_encoding_is_bounded():
    from PySide6.QtGui import QImage
    from delta_agent.screen_capture import encode_image
    image=QImage(1920,1080,QImage.Format.Format_RGB32);image.fill(0xff00ff00)
    result=encode_image(image)
    assert result['width']<=1280 and result['height']<=960
    assert len(result['image_url'])<700_000
