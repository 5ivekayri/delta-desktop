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

## Запуск приложений (0.2.0)

После обновления Core и клиента: «открой Finder», «открой Finder на Mac»,
«запусти Safari на Mac — kayri». Выбор текущего компьютера задаёт цель, а явно
указанное имя компьютера её переопределяет. При режиме подтверждения разрешите
запуск на целевом Mac. Общий режим «Полный доступ» оставляет запуск без диалога,
если действие отдельно не запрещено. Клиент 0.1.0 необходимо заменить новой
сборкой. UID, аккаунт и сохранённые настройки остаются на месте.

Каталог macOS: /Applications, ~/Applications, /System/Applications и
/System/Library/CoreServices (включая Finder). Подтверждены контрактные тесты
маршрутизации на другой Agent, тесты macOS-адаптера и Qt smoke на Linux; реальное
окно Finder проверяется после установки новой сборки на Mac.
