import plistlib
from unittest.mock import Mock
import pytest
from delta_agent.applications import discover
from delta_agent.commands import CommandExecutor
from delta_agent.platforms.macos import MacOSPlatformAdapter


def make_app(root,name='Finder',bundle='com.apple.finder'):
    path=root/(name+'.app')
    (path/'Contents').mkdir(parents=True)
    (path/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleName':name,'CFBundleIdentifier':bundle}))
    return path


def test_macos_catalogue_and_native_open_use_local_path_only(tmp_path):
    path=make_app(tmp_path)
    catalogue=discover('macos',[tmp_path])
    assert len(catalogue)==1
    app=next(iter(catalogue.values()))
    assert 'файндер' in app.aliases and app.name=='Finder'
    assert 'path' not in app.public()
    adapter=MacOSPlatformAdapter()
    adapter.installed_applications=Mock(return_value=catalogue)
    adapter.run=Mock()
    result=CommandExecutor(adapter,[],allowed_apps=['*']).execute({'command_id':'1','action':'open_app','payload':{'app_id':app.id}})
    assert result['success']
    adapter.run.assert_called_once_with(['/usr/bin/open','-a',str(path)])
    for app_id in ['/bin/sh','Finder; touch /tmp/x','installed-unknown']:
        assert not CommandExecutor(adapter,[],allowed_apps=['*']).execute({'command_id':'2','action':'open_app','payload':{'app_id':app_id}})['success']
    assert adapter.run.call_count==1


def test_catalogue_does_not_follow_symlinks_outside_install_roots(tmp_path):
    root=tmp_path/'Applications';root.mkdir()
    private=tmp_path/'private';private.mkdir()
    path=make_app(private)
    (root/'Finder.app').symlink_to(path,target_is_directory=True)
    assert discover('macos',[root])=={}


@pytest.mark.parametrize('permission,confirmed,expected', [('deny',True,False),('ask',False,False),('ask',True,True)])
def test_installed_app_preserves_local_policy(tmp_path,permission,confirmed,expected):
    make_app(tmp_path)
    apps=discover('macos',[tmp_path]);app=next(iter(apps.values()))
    adapter=MacOSPlatformAdapter();adapter.installed_applications=Mock(return_value=apps);adapter.run=Mock()
    confirm=Mock(return_value=confirmed)
    executor=CommandExecutor(adapter,[],allowed_apps=['*'],permission=lambda _:permission,confirm=confirm)
    result=executor.execute({'command_id':'1','action':'open_app','payload':{'app_id':app.id}})
    assert result['success']==expected
    assert adapter.run.call_count==int(expected)
    if permission=='ask':assert confirm.call_args.args[1]['app_name']=='Finder'


def test_removed_app_is_not_launched_after_approval(tmp_path):
    make_app(tmp_path);apps=discover('macos',[tmp_path]);app=next(iter(apps.values()))
    adapter=MacOSPlatformAdapter();adapter.installed_applications=Mock(side_effect=[apps,{}]);adapter.run=Mock()
    executor=CommandExecutor(adapter,[],allowed_apps=['*'],permission=lambda _:'ask',confirm=lambda *args:True)
    assert not executor.execute({'command_id':'1','action':'open_app','payload':{'app_id':app.id}})['success']
    adapter.run.assert_not_called()


@pytest.mark.parametrize('os_name', ['linux', 'macos', 'windows'])
def test_vscode_common_names_across_platforms(tmp_path, os_name):
    if os_name == 'macos':
        make_app(tmp_path, 'Visual Studio Code', 'com.microsoft.VSCode')
    elif os_name == 'windows':
        (tmp_path/'Visual Studio Code.lnk').touch()
    else:
        (tmp_path/'com.visualstudio.code.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=flatpak run com.visualstudio.code %U\n')
    app = next(iter(discover(os_name, [tmp_path]).values()))
    for name in ['vscode', 'vs code', 'вс код']:
        assert name in app.public()['aliases']
    adapter = Mock()
    adapter.capabilities = ['open_app']
    adapter.installed_applications.return_value = {app.id: app}
    confirm = Mock(return_value=True)
    result = CommandExecutor(adapter, [], allowed_apps=['*'], permission=lambda _: 'ask', confirm=confirm).execute(
        {'command_id': 'alias', 'action': 'open_app', 'payload': {'app_id': app.id}})
    assert result['success']
    assert confirm.call_args.args[1]['app_name'] == 'Visual Studio Code'
    adapter.open_installed_app.assert_called_once_with(app.id)
