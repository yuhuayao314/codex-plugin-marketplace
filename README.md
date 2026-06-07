# yuhuayao314 Codex Plugin Marketplace

Public Codex plugin marketplace maintained by `yuhuayao314`.

## Plugins

- `codex-powershell-guardrails`: PowerShell and Windows guardrails for Codex agents.
- `codex-error-memory`: local SQLite-backed memory for recurring technical errors.

## Install

Add this marketplace to Codex:

```powershell
codex plugin marketplace add https://github.com/yuhuayao314/codex-plugin-marketplace
```

Then install the plugin you want from `yuhuayao314 Plugins`.

## Source Repositories

- https://github.com/yuhuayao314/codex-powershell-guardrails
- https://github.com/yuhuayao314/codex-error-memory

The marketplace keeps installable plugin snapshots under `plugins/` so Codex can load them reliably.
