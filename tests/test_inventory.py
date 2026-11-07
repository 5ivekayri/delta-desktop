import pytest

from delta_agent.inventory import inspect_applications, model_catalogue
from delta_agent.settings import DesktopSettings


@pytest.fixture(autouse=True)
def linux_executables(monkeypatch):
    # The fixture describes Linux entries, even when the test host is Windows.
    monkeypatch.setattr("delta_agent.inventory.shutil.which",
                        lambda command: "/usr/bin/true" if command == "/usr/bin/true" else None)


def entry(root, name, extra=''):
    root.mkdir(exist_ok=True)
    (root/name).write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/true %U\n'+extra, encoding='utf-8')


def test_audit_includes_excluded_and_missing_without_executing(tmp_path):
    user, system = tmp_path/'user', tmp_path/'system'
    entry(user, 'valid.desktop')
    entry(user, 'hidden.desktop', 'Hidden=true\n')
    entry(system, 'hidden.desktop')
    entry(user, 'missing.desktop', 'TryExec=delta-no-such-command\n')
    entry(user, 'service.desktop', 'NoDisplay=true\n')
    rows = inspect_applications('linux', roots=[user, system])
    assert len(rows) == 5
    assert sum(row['status'] == 'catalogued' for row in rows) == 1
    exported = model_catalogue(rows)
    assert len(exported) == 1
    assert exported[0]['confirmation_required']
    assert set(exported[0]) == {'id', 'name', 'aliases', 'confirmation_required'}


def test_export_obeys_denied_policy_and_disabled_catalogue(tmp_path):
    entry(tmp_path, 'valid.desktop')
    settings = DesktopSettings(server='http://localhost:8081', token='test-token-only-123456', name='test')
    assert len(model_catalogue(inspect_applications('linux', settings, [tmp_path]))) == 1
    settings.command_permissions['open_app'] = 'deny'
    assert model_catalogue(inspect_applications('linux', settings, [tmp_path])) == []
    settings.command_permissions.clear()
    settings.allow_installed_apps = False
    assert model_catalogue(inspect_applications('linux', settings, [tmp_path])) == []
