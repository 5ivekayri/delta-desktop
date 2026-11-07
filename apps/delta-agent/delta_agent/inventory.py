"""Read-only launcher audit; never execute entries while scanning."""
import configparser
import os
from pathlib import Path
import shlex
import shutil

from .applications import application_roots, discover


def inspect_applications(os_name, settings=None, roots=None):
    roots = application_roots(os_name) if roots is None else roots
    catalogue = discover(os_name, roots)
    by_path = {str(app.path): app for app in catalogue.values()}
    seen = set()
    rows = []
    for root in roots:
        root = Path(root).resolve()
        for directory, folders, files in os.walk(root, followlinks=False):
            if os_name == 'macos':
                candidates = [Path(directory)/n for n in folders if n.endswith('.app')]
                folders[:] = [n for n in folders if not n.endswith('.app')]
            else:
                suffix = '.desktop' if os_name == 'linux' else '.lnk'
                candidates = [Path(directory)/n for n in files if n.lower().endswith(suffix)]
            for path in sorted(candidates):
                app = by_path.get(str(path)) or by_path.get(str(path.resolve()))
                row = {'name': app.name if app else path.stem, 'id': app.id if app else None,
                       'aliases': list(app.aliases) if app else [], 'path': str(path),
                       'status': 'catalogued' if app else 'excluded',
                       'reason': 'Есть в каталоге' if app else 'Скрыто, несовместимо или некорректно',
                       'access': 'deny', 'launch_check': 'not_run'}
                if app:
                    permitted = settings is None or (settings.allow_installed_apps or app.id in settings.allowed_apps)
                    row['access'] = settings.permission('open_app') if settings and permitted else ('ask' if permitted else 'deny')
                if os_name == 'linux':
                    desktop_id = str(path.relative_to(root)).replace('/', '-')
                    if desktop_id in seen:
                        row.update(status='excluded', reason='Переопределено записью с более высоким приоритетом', access='deny', id=None)
                    else:
                        seen.add(desktop_id)
                        _inspect_desktop(path, row)
                rows.append(row)
    return rows


def _inspect_desktop(path, row):
    try:
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read(path, encoding='utf-8')
        section = config['Desktop Entry']
        row['name'] = section.get('Name', row['name'])
        if not path.is_file():
            row.update(status='unavailable', reason='Файл запуска отсутствует', access='deny')
        elif section.get('Hidden', 'false').lower() == 'true':
            row.update(status='excluded', reason='Hidden: скрыто пользователем', access='deny')
        elif section.get('NoDisplay', 'false').lower() == 'true':
            row.update(status='excluded', reason='NoDisplay: служебная запись', access='deny')
        elif section.get('TryExec') and not shutil.which(section['TryExec']):
            row.update(status='unavailable', reason='TryExec: исполняемый файл не найден', access='deny')
        elif row['status'] == 'catalogued':
            if section.get('DBusActivatable', 'false').lower() == 'true':
                row['reason'] = 'Запуск через D-Bus; фактический старт не проверялся'
            else:
                # Diagnostic only. GIO remains the only Exec interpreter at launch time.
                command = shlex.split(section.get('Exec', ''), posix=True)
                if not command or not shutil.which(command[0]):
                    row.update(status='unavailable', reason='Exec: программа запуска не найдена', access='deny')
                else:
                    row['reason'] = 'Программа запуска найдена; фактический старт не проверялся'
    except (OSError, ValueError, KeyError, configparser.Error, UnicodeError):
        row.update(status='unavailable', reason='Не удалось прочитать файл запуска', access='deny')


def model_catalogue(rows):
    """Only names and IDs of usable, locally permitted entries; no paths or Exec."""
    return [{'id': row['id'], 'name': row['name'], 'aliases': row['aliases'],
             'confirmation_required': row['access'] == 'ask'}
            for row in rows if row['status'] == 'catalogued' and row['access'] != 'deny']
