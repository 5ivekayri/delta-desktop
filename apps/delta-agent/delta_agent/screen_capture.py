"""One-shot bounded screen capture, called only after explicit local approval."""
import base64
import json
from pathlib import Path
import os
import subprocess
import tempfile
import time
from .window_actions import host_environment, command


def encode_image(image):
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
    if image.isNull():
        raise PermissionError('Screen capture unavailable; check OS screen recording permission')
    image = image.scaled(1280, 960, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    data = QByteArray(); buffer = QBuffer(data); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'JPEG', 70):
        raise RuntimeError('Image encoding failed')
    raw = bytes(data)
    if len(raw)>500_000:
        raise ValueError('Screen image exceeds transfer limit')
    return {'image_url':'data:image/jpeg;base64,'+base64.b64encode(raw).decode(),
            'width':image.width(),'height':image.height()}


def capture_screen(os_name):
    from PySide6.QtGui import QImage
    time.sleep(.25)  # Let the approval dialog disappear before capturing.
    if os_name == 'linux' and os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        args = ['grim','-t','png']
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            monitors=json.loads(command(['hyprctl','monitors','-j']))
            monitor=next((m for m in monitors if m.get('focused')),None)
            if monitor:args.extend(['-o',monitor['name']])
        args.append('-')
        result=subprocess.run(args,check=True,timeout=10,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,env=host_environment(),shell=False)
        return encode_image(QImage.fromData(result.stdout))
    if os_name == 'macos':
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'screen.png'
            subprocess.run(['/usr/sbin/screencapture','-x','-t','png','-D','1',str(path)],
                           check=True,timeout=10,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return encode_image(QImage(str(path)))
    raise NotImplementedError('Capture requires a Qt GUI dispatcher or a supported Wayland compositor')
