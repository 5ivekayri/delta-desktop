# Delta Desktop

Python 3.12+, PySide6 Qt Widgets. Neutral black/white/grayscale palette only.
Keep login minimal; advanced controls belong in Settings. Windows/macOS/Linux
platform adapters, explicit registered actions only. Never add arbitrary shell,
Python evaluation, executable paths, destructive filesystem actions or credential access.
Preserve local deny/ask/allow policy, expiry and disconnect cancellation.
Do not commit .env, tokens, user settings, generated packages or server credentials.
Maintain docs alongside protocol/behavior changes; coordinate wire schema changes
with delta-eco-system. Run pytest and scripts/check_agent_desktop.py. Build on target OS.
