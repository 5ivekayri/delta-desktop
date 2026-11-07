"""Local installed-app catalogue. Remote callers receive IDs, never launch paths."""
from dataclasses import dataclass
from pathlib import Path
import configparser
import hashlib
import os
import plistlib
import shutil


@dataclass(frozen=True)
class InstalledApp:
    id: str
    name: str
    path: Path
    aliases: tuple[str, ...] = ()

    def public(self):
        return {'id': self.id, 'name': self.name, 'aliases': list(self.aliases)}


def app_id(path):
    return 'installed-' + hashlib.sha256(str(path).encode()).hexdigest()[:24]


def application_aliases(name, aliases):
    """Cross-platform product names; never infer executable commands from user text."""
    identities = {value.casefold() for value in [name, *aliases]}
    vscode = {'visual studio code', 'microsoft visual studio code', 'com.microsoft.vscode',
              'com.visualstudio.code', 'com.visualstudio.code.desktop', 'code.desktop'}
    extra = []
    if identities & vscode:
        extra = ['vscode', 'vs code', 'Visual Studio Code', 'Microsoft Visual Studio Code',
                 'вскод', 'вс код', 'вижуал студио код']
    return tuple(dict.fromkeys(extra + list(aliases)))[:20]


def application_roots(os_name):
    if os_name == 'macos':
        roots = [Path('/Applications'), Path.home()/'Applications', Path('/System/Applications'),
                 Path('/System/Library/CoreServices')]
    elif os_name == 'linux':
        roots = [Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'applications']
        roots += [Path(p)/'applications' for p in (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share').split(':') if p]
    elif os_name == 'windows':
        roots = [Path(os.environ[k])/'Microsoft/Windows/Start Menu/Programs' for k in ('APPDATA','PROGRAMDATA') if os.environ.get(k)]
    else:
        return []
    return roots


def discover(os_name, roots=None):
    roots = application_roots(os_name) if roots is None else roots
    result = {}
    desktop_ids = set()
    for root in roots:
        root = Path(root).resolve()
        if not root.is_dir():
            continue
        # Do not traverse app internals or symlinked directories.
        for directory, folders, files in os.walk(root, followlinks=False):
            candidates = []
            if os_name == 'macos':
                candidates = [Path(directory)/name for name in folders if name.endswith('.app')]
                folders[:] = [name for name in folders if not name.endswith('.app')]
            else:
                suffix = '.desktop' if os_name == 'linux' else '.lnk'
                candidates = [Path(directory)/name for name in files if name.lower().endswith(suffix)]
            for path in sorted(candidates):
                try:
                    resolved = path.resolve(strict=True)
                    if os_name != 'linux' and not resolved.is_relative_to(root):
                        continue
                    if os_name == 'linux' and not resolved.is_file():
                        continue
                    name = path.stem
                    aliases = [name]
                    if os_name == 'macos':
                        with (resolved/'Contents/Info.plist').open('rb') as f:
                            info = plistlib.load(f)
                        name = info.get('CFBundleDisplayName') or info.get('CFBundleName') or name
                        bundle = info.get('CFBundleIdentifier', '')
                        if bundle == 'com.apple.finder':
                            aliases += ['Finder', 'файндер', 'файндэр']
                        if bundle:
                            aliases.append(bundle)
                    elif os_name == 'linux':
                        desktop_id = str(path.relative_to(root)).replace('/', '-')
                        if desktop_id in desktop_ids:
                            continue
                        desktop_ids.add(desktop_id)
                        config = configparser.ConfigParser(interpolation=None, strict=False)
                        config.read(resolved, encoding='utf-8')
                        section = config['Desktop Entry']
                        if section.get('Type') != 'Application' or section.get('Hidden','false').lower() == 'true' or section.get('NoDisplay','false').lower() == 'true' or not (section.get('Exec') or section.get('DBusActivatable', 'false').lower() == 'true'):
                            continue
                        try_exec = section.get('TryExec')
                        if try_exec and not shutil.which(try_exec):
                            continue
                        desktops = os.environ.get('XDG_CURRENT_DESKTOP', '').split(':')
                        only = section.get('OnlyShowIn', '').split(';')
                        excluded = section.get('NotShowIn', '').split(';')
                        visible = not section.get('OnlyShowIn')
                        for desktop in filter(None, desktops):
                            if desktop in only or desktop in excluded:
                                visible = desktop in only
                                break
                        if not visible:
                            continue
                        aliases.append(desktop_id)
                        name = section.get('Name', name)
                        aliases += [v for k,v in section.items() if k.startswith('name[')]
                    if not isinstance(name, str) or not name.strip():
                        continue
                    item_path = path if os_name == 'linux' else resolved
                    item = InstalledApp(app_id(item_path), name[:255], item_path,
                                        application_aliases(name, [a[:255] for a in aliases if isinstance(a,str) and a]))
                    result[item.id] = item
                    if len(result) >= 1024:
                        return result
                except (OSError, ValueError, KeyError, configparser.Error, plistlib.InvalidFileException):
                    continue
    return result
