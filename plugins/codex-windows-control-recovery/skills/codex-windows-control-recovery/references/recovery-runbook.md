# Recovery runbook

## 1. Establish evidence

Record:

- installed Codex package full name, version and install location
- current Codex executable paths and process identifiers
- writable runtime locations and SHA256 values
- presence of Computer Use and node_repl in the current task
- current named-pipe observations
- exact browser or Chrome extension error
- recent Codex log excerpts around relocation, pipe and tool registration

Run the read-only diagnostic script first. Do not mutate while evidence is incomplete.

## 2. Classify the failure

### Settings page missing

Likely package availability gate regression. Confirm the installed build changed. Package work is version-specific; follow package-gate-rebuild.md.

### Settings page present, tool absent

Likely live-process schema or writable runtime failure. Check logs and runtime hashes. Repair only an identified runtime, then restart safely.

### node_repl call reports not a function

If runtime verification passes, the old desktop process probably retained a stale schema. Save state, perform a scoped restart, and create a fresh task.

### bundled executable relocation failed

The packaged source may be encrypted or unreadable. Do not weaken WindowsApps permissions. Locate an unencrypted source for the exact same build and compare its SHA256 with the expected build artifact before copying.

### named pipe does not connect

Check whether stale SKY_CUA entries were persisted. Remove only those exact keys. Then restart and observe the newly generated pipe.

### Browser refuses a URL

Read the actual error. Destination policy is separate from installation. Test an allowed public destination and preserve the proxy and enterprise policy.

### Chrome says extension not connected

Treat it as an external Chrome extension issue. Confirm installation, enablement and connection in Chrome. Do not use Computer Use success as proof of Chrome extension success.

## 3. Repair narrowly

All changes need:

- an explicit target
- a dry-run or preview
- containment checks
- exact version and hash preconditions where files are replaced
- backup or staging before atomic replacement
- postcondition verification

Never delete the installed package. Never run uninstall-first instructions from an older workaround.

## 4. Restart without losing the task

The current Codex task can disappear when its hosting desktop process exits. Before restart, save:

- diagnosis
- files changed
- remaining verification steps
- exact success criteria

Run preflight first. The restart helper must select only current-package executables, launch a hidden detached delay, stop those processes, and start the registered application identity.

## 5. Acceptance test

Success requires all of the following in a new post-restart task:

- Computer Use is exposed
- node_repl is exposed when browser control needs it
- no stale pipe variables are persisted
- the live Computer Use pipe is created
- actual Computer Use opens Notepad
- actual Computer Use types a unique nonce
- visible Notepad content is read back and matches the nonce

Terminal-created files, SendKeys, PowerShell UI Automation and screenshots without an actual tool call are not acceptable substitutes.

## 6. After the next update

Start again at evidence collection. The installed version, bundle anchors, integrity metadata and runtime hashes may all have changed. Reusing a previous version-specific patch without validation is unsafe.
