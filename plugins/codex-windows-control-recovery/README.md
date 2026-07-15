# Codex Windows Control Recovery

A public Codex plugin and skill for diagnosing and safely recovering Computer Use and browser-control plumbing in Codex Desktop on Windows.

The project exists because several different failures can look identical in the UI. Store updates can replace package gates, WindowsApps encryption can prevent runtime relocation, a still-running desktop process can retain an old tool schema, and browser policy can block navigation even when the backend is healthy.

## Safety promise

This project does not uninstall Codex, remove its AppX package, reset app data, change language settings, clear the complete plugin cache, or bypass enterprise browser policy.

Every mutating helper is narrow, previewable, and fail-closed. Runtime replacement requires an exact expected SHA256. Process restart is scoped to executables under the detected Codex package path.

## Install

Install from the personal marketplace:

    /plugin marketplace add yuhuayao314/codex-plugin-marketplace

Then install Windows Control Recovery from the plugin browser.

The independent source repository is also a valid plugin root and can be inspected before installation.

## After a Store update

Run the skill again from Phase 1. Store updates replace the signed application package, so package-level changes can be lost even when user configuration and this plugin remain.

## What this repository intentionally does not contain

It does not contain a blind, permanent ASAR patcher. Upstream bundles change frequently. Package-gate work must identify semantic anchors in the currently installed build, assert expected match counts, rebuild integrity metadata, sign a higher-version MSIX, and stop if any assumption changes.

## For maintainers

The skill entry point is skills/codex-windows-control-recovery/SKILL.md. Architecture and the detailed decision tree are in its references directory.

Licensed under MIT.
