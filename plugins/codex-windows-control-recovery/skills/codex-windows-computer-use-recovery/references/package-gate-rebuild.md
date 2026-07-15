# Package gate rebuild boundary

Package-gate recovery is for programmers who understand MSIX packaging, Electron ASAR layout and code-signing trust. This skill deliberately does not ship an old-build blind patcher.

## Required properties

1. Work from a copy of the installed package, never in WindowsApps.
2. Record the original package identity, version and hashes.
3. Locate gates by current semantic behavior, not only an old minified token.
4. Assert an exact expected match count before replacement.
5. Stop when a target is missing, duplicated or structurally changed.
6. Rebuild the ASAR and repair every integrity record that covers it.
7. assign a higher package version without changing identity fields unexpectedly.
8. Sign with a certificate trusted on the local machine.
9. Validate package manifest, signature and payload before installation.
10. Install transactionally with Add-AppxPackage update semantics. Do not uninstall first.
11. Verify registration before deleting staging or backup material.

## Forbidden recovery patterns

- Remove-AppxPackage
- winget uninstall
- deleting the Codex package directory
- resetting the Codex profile
- changing package ACLs to force in-place edits
- copying an ASAR from another build
- replacing a runtime without a supplied expected SHA256
- installing an unsigned or identity-mismatched package

## Why updates require a rerun

The Store replaces the package as a complete signed unit. Package-level changes are therefore expected to disappear. This plugin and user configuration live outside that unit, but the full four-layer diagnostic still needs to run because upstream runtime and tool behavior can also change.
