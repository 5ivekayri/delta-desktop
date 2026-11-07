# Workspace files — Agent 0.4.0

New actions: workspace_files (managed workspace list/read/write/history), search_files
(filename lookup in allowed folders), read_file (copy an allowed file to Core).
Local workspaces live in the Agent configuration directory under workspaces/<UUID>.
No shell execution or arbitrary destination paths. Writes preserve previous versions,
require the previous SHA-256 and use atomic replacement. DOCX limit 10 MB, text 512 KB.

Search/import requires configured folders. Settings can add Documents / Downloads /
Desktop in one click; Full Access adds them when no folders were previously selected.
Search skips hidden directories and caches, is bounded to five seconds/30,000 entries
and returns up to 50 matches with a truncation flag. Explicit deny/ask policies and
command cancellation apply to these capabilities just like existing actions.

Core and shared contracts must be updated first. Core redacts file data from device
activity. Local workspace content passes through Core for the editor and chosen LLM.
Workspace preview is a sandboxed HTML frame in Control Center, not native execution.
Tests cover local copies, sources unchanged, conflict, traversal, deny/ask/cancellation.
