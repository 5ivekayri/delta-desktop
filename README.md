# Δ Delta Desktop

Кроссплатформенный клиент Delta: Python 3.12+, PySide6 / Qt Widgets.
Сервер находится в [delta-eco-system](https://github.com/5ivekayri/delta-eco-system).
Этот репозиторий — основное место разработки настольного клиента.

## Разработка

```sh
python3.12 -m venv .venv
# Активируйте .venv для своей ОС
python -m pip install -e '.[test]'
python -m delta_agent.desktop
python -m pytest -q
python scripts/check_agent_desktop.py
```

## Сборка

```sh
python -m pip install -r requirements-agent-build.txt
python scripts/build_agent.py
```

Собирать на целевой ОС: macOS → DMG, Windows → ZIP, Linux → tar.gz.
Workflow GitHub Actions запускается вручную. Windows runtime пока не проверен.
Публичная дистрибуция требует подписания; macOS сейчас использует ad-hoc подпись.

[Настройки и команды](docs/DESKTOP_AGENT.md) · [Протокол Core](docs/DEVICE_PROTOCOL.md)

Клиент общается с Core только через HTTP/WebSocket. Серверные БД, ключи и .env
сюда не входят. Минимальный модуль delta_contracts.devices содержит wire-схемы;
его изменения должны согласовываться с серверным репозиторием. В одном Python
окружении не устанавливайте сервер и клиент: у них есть общий namespace контрактов.

Пользовательские настройки и UID остаются в ~/.delta-agent-desktop. Перенос
репозитория не требует переустановки или повторной регистрации устройства.
