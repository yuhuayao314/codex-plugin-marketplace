# Codex Error Memory

A local SQLite-backed memory plugin for recurring technical errors. It helps Codex search previous fixes before debugging and record new lessons after a problem is resolved.

## Install

Install directly:

```powershell
codex plugin install https://github.com/yuhuayao314/codex-error-memory
```

Or install it from the public marketplace repository:

```powershell
codex plugin marketplace add https://github.com/yuhuayao314/codex-plugin-marketplace
```

## Use

Search prior memories:

```powershell
python scripts\memory_cli.py search --project E:\path\to\project --text "error text"
```

Add a memory:

```powershell
python scripts\memory_cli.py add --project E:\path\to\project --title "Short title" --text "error text" --root-cause "Cause" --fix-steps "Fix" --verification-steps "Checks"
```

Export memories:

```powershell
python scripts\export_memory.py --project E:\path\to\project --out memory.md
```

The database is created automatically outside the plugin cache at:

```text
%USERPROFILE%\.codex\error-memory\error_memory.sqlite
```

You can override it with `CODEX_ERROR_MEMORY_DB`. If an older plugin-cache database exists at `data/error_memory.sqlite`, the CLI copies it to the new stable location on first use.

Read-only commands such as `search`, `list`, and `export` do not create project rows. Project paths stored in occurrences are reduced to a local project label plus hash instead of the full absolute path.
