"""Build on each target OS; never bundles .env, Core, Tasks or server credentials."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    import os, struct
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    sys.path[:0] = [str(ROOT/'apps/delta-agent'), str(ROOT/'shared/contracts')]
    from PySide6.QtWidgets import QApplication
    from delta_agent.desktop import app_icon
    qt = QApplication.instance() or QApplication([])
    icons = ROOT/'build/Delta.iconset'
    icons.mkdir(parents=True, exist_ok=True)
    icon = app_icon()
    for size in [16,32,128,256,512]:
        icon.pixmap(size,size).save(str(icons/f'icon_{size}x{size}.png'))
        icon.pixmap(size*2,size*2).save(str(icons/f'icon_{size}x{size}@2x.png'))
    icon_path = ROOT/'build/Delta.ico'
    png=(icons/'icon_256x256.png').read_bytes()
    icon_path.write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22)+png)
    if sys.platform == 'darwin':
        icon_path=ROOT/'build/Delta.icns'
        subprocess.run(['iconutil','-c','icns',str(icons),'-o',str(icon_path)],check=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--icon', str(icon_path), '--windowed', '--onedir', '--name', 'Delta Agent',
        '--osx-bundle-identifier', 'org.delta.agent',
        '--distpath', str(ROOT/'dist/agent'), '--workpath', str(ROOT/'build/agent'),
        '--specpath', str(ROOT/'build'),
        '--paths', str(ROOT/'apps/delta-agent'), '--paths', str(ROOT/'shared/contracts'),
        str(ROOT/'scripts/agent_desktop_entry.py')], check=True, cwd=ROOT)
    if sys.platform == 'darwin':
        import plistlib
        bundle = ROOT/'dist/agent/Delta Agent.app'
        info = bundle/'Contents/Info.plist'
        data = plistlib.loads(info.read_bytes())
        data.update(NSDesktopFolderUsageDescription='Delta opens only folders you allow in Agent settings.',
                    NSDocumentsFolderUsageDescription='Delta opens only folders you allow in Agent settings.',
                    NSAppleEventsUsageDescription='Delta opens allowed folders and applications on your request.')
        info.write_bytes(plistlib.dumps(data))
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(bundle)], check=True)
        stage = ROOT/'build/agent-dmg'
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        shutil.copytree(ROOT/'dist/agent/Delta Agent.app', stage/'Delta Agent.app', symlinks=True)
        (stage/'Applications').symlink_to('/Applications')
        subprocess.run(['hdiutil', 'create', '-volname', 'Delta Agent', '-srcfolder', str(stage),
                        '-ov', '-format', 'UDZO', str(ROOT/'dist/agent/Delta-Agent-macOS.dmg')], check=True)
    elif sys.platform.startswith('linux'):
        import tarfile
        with tarfile.open(ROOT/'dist/agent/Delta-Agent-linux.tar.gz', 'w:gz') as archive:
            archive.add(ROOT/'dist/agent/Delta Agent', arcname='Delta Agent')
    else:
        shutil.make_archive(str(ROOT/f'dist/agent/Delta-Agent-{sys.platform}'), 'zip',
                            ROOT/'dist/agent', 'Delta Agent')


if __name__ == '__main__':
    main()
