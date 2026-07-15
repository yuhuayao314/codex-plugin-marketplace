---
name: codex-windows-control-recovery
description: Diagnose and safely recover Codex Desktop Computer Use, in-app browser control, Chrome connection plumbing, writable runtimes, tool injection, and named-pipe state on Windows after Store or app updates. Use when Computer Use or browser settings are visible but tools are missing, node_repl is unavailable, the Chrome extension is disconnected, bundled executable relocation fails, or a previously working Windows patch stops after an update. Never uninstall Codex.
---

# Codex Windows Control Recovery

Recover the Windows control stack with a fail-closed, evidence-first workflow. Preserve the installed app, user data, language, proxy, and unrelated plugin state.

## Absolute safety rules

1. Never uninstall Codex and never remove its AppX package.
2. Never reset app data, clear the whole plugin cache, or change the language.
3. Never edit files in WindowsApps in place.
4. Never persist SKY_CUA_NATIVE_PIPE or SKY_CUA_NATIVE_PIPE_DIRECTORY. Pipe identifiers are process-specific.
5. Never copy a runtime from a different Codex build. Match version and SHA256.
6. Never use PowerShell SendKeys, UI Automation, or another substitute as proof that Computer Use works.
7. Never bypass browser enterprise policy or silently change the proxy.
8. Stop before every mutating phase if preconditions or semantic anchors do not match.

If a proposed command contains Remove-AppxPackage, Get-AppxPackage piped to removal, winget uninstall, or a recursive delete of the Codex package or profile, refuse to run it.

## Required workflow

### Phase 1: Read-only diagnosis

Run scripts/diagnose-control-stack.ps1. Save its JSON report. Determine which layer is failing:

- Package gate: UI or Windows availability is hidden after a Store update.
- Writable runtime: node_repl or Computer Use runtime is absent, unreadable, or mismatched.
- Live process: files are repaired but the current desktop process still has an old tool schema or stale pipe state.
- Browser policy or extension: in-app navigation is blocked by policy, or external Chrome reports an unconnected extension.

Read references/architecture.md before attributing all failures to networking.

### Phase 2: Choose the smallest repair

- If only stale native-pipe entries exist, run scripts/clear-stale-cua-pipe-config.ps1 after reviewing its exact preview.
- If a writable runtime is missing, use scripts/repair-writable-runtime.ps1 with an exact-build source and expected SHA256.
- If package gates were replaced, read references/package-gate-rebuild.md. A programmer must adapt and validate the gate patch for the installed build. Do not apply blind string replacements from an older version.
- If only live process state is stale, use scripts/restart-codex-safe.ps1 -PreflightOnly, then schedule the actual restart only after saving the current plan.
- If browser policy blocks a destination, report the policy boundary. Do not call it an installation failure.

### Phase 3: Restart safely

Before restarting:

1. Persist the diagnosis and next action.
2. Verify the selected processes belong to the current Codex package install root.
3. Run scripts/restart-codex-safe.ps1 -PreflightOnly.
4. Run the actual restart from a detached hidden process so the current task can terminate cleanly.

Do not kill every process named Codex. Scope by executable path and current package.

### Phase 4: Verify in a fresh task

Strict verification requires a newly created task after the desktop process restarts:

1. Confirm the Computer Use tool is present in the new task schema.
2. Confirm node_repl is callable when browser control requires it.
3. Confirm the current Computer Use named pipe exists and belongs to the live process.
4. Use actual Computer Use to open Notepad.
5. Type a unique nonce.
6. Read the nonce back from the visible app.

PowerShell, SendKeys, UI Automation, and terminal commands do not satisfy this test.

For external Chrome, separately verify that its extension is installed, enabled, and connected. External Chrome, the in-app browser, and Computer Use are three distinct control paths.

## Store update behavior

A Store update replaces signed package files and therefore removes package-level gate changes. User configuration and the independently installed plugin usually remain. After every Store update, rerun the full diagnostic workflow; do not assume only one layer changed.

## Error handling

If tools.mcp__node_repl__js is not a function appears after files were repaired, treat it first as cached desktop-process state and restart safely.

If bundled_executable_relocation_failed appears, suspect encrypted or unreadable WindowsApps source files. Obtain an unencrypted source from the exact same build and verify SHA256 before copying.

If strict verification reports stale pipe configuration, remove only the two exact SKY_CUA keys and preserve every other configuration line.

If restart terminates the current task, resume from the saved plan. Do not improvise an uninstall or reinstall.

## Resources

- references/architecture.md explains the four-layer control stack.
- references/recovery-runbook.md gives programmers the full decision tree and acceptance tests.
- references/package-gate-rebuild.md defines the safe boundary for version-specific package work.
- scripts contain read-only diagnosis and narrowly scoped recovery helpers.
