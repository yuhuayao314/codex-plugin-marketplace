# yuhuayao314 Codex Plugin Marketplace

Public Codex plugin marketplace maintained by `yuhuayao314`.

## Plugins

- `codex-powershell-guardrails`: PowerShell and Windows guardrails for Codex agents.
- `codex-error-memory`: local SQLite-backed memory for recurring technical errors.
- `codex-windows-control-recovery`: fail-closed recovery for Windows Computer Use and browser-control plumbing without uninstalling Codex.

## Install

Add this marketplace to Codex:

```powershell
codex plugin marketplace add https://github.com/yuhuayao314/codex-plugin-marketplace
```

Then install the plugin you want from `yuhuayao314 Plugins`.

## Source Repositories

- https://github.com/yuhuayao314/codex-powershell-guardrails
- https://github.com/yuhuayao314/codex-error-memory
- https://github.com/yuhuayao314/codex-windows-control-recovery

The marketplace keeps installable plugin snapshots under `plugins/` so Codex can load them reliably.

## Maintenance

The `plugins/` folders are installable snapshots. A scheduled GitHub Actions workflow checks all independent source repositories every six hours and commits changed snapshots. Maintainers can also run the Sync plugin snapshots workflow manually for immediate refresh.

This zero-secret design is eventually consistent. The default token of one repository cannot immediately dispatch a workflow in another repository. Immediate cross-repository dispatch would require a dedicated GitHub App or narrowly scoped token.

These plugins are local skills/scripts and do not require an external account authorization flow during installation.
