# Codex Windows Computer Use Recovery

A public Codex plugin containing the codex-windows-computer-use-recovery skill. It diagnoses and safely recovers Computer Use in Codex Desktop on Windows.

The project focuses only on Computer Use.

## Safety promise

This project does not uninstall Codex, remove its AppX package, reset app data, change language settings, or clear the complete plugin cache.

Every mutating helper is narrow, previewable, and fail-closed. Runtime replacement requires an exact expected SHA256. Process restart is scoped to executables under the detected Codex package path.

## Install

Add the public marketplace:

    /plugin marketplace add yuhuayao314/codex-plugin-marketplace

Then install Windows Computer Use Recovery from the plugin list.

## After a Store update

Run the skill again from Phase 1. Store updates replace the signed application package, so package-level changes can be lost even when user configuration and this plugin remain.

## What this repository intentionally does not contain

It does not contain a blind, permanent ASAR patcher. Upstream bundles change frequently. Package-gate work must identify semantic anchors in the currently installed build, assert expected match counts, rebuild integrity metadata, sign a higher-version MSIX, and stop if any assumption changes.

Licensed under MIT.
