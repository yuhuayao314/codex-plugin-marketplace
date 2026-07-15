from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path


SOURCES = {
    "codex-powershell-guardrails": "https://github.com/yuhuayao314/codex-powershell-guardrails.git",
    "codex-error-memory": "https://github.com/yuhuayao314/codex-error-memory.git",
    "codex-windows-control-recovery": "https://github.com/yuhuayao314/codex-windows-control-recovery.git",
}


def parse_local_sources(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit("--local-source must use plugin-name=absolute-path")
        name, raw_path = value.split("=", 1)
        result[name] = Path(raw_path).expanduser().resolve()
    return result


def validate_plugin(root: Path, expected_name: str) -> None:
    manifest_path = root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Missing plugin manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != expected_name:
        raise RuntimeError(
            f"Manifest name mismatch for {expected_name}: {manifest.get('name')}"
        )
    if not manifest.get("version"):
        raise RuntimeError(f"Manifest version is missing for {expected_name}")
    skills_root = root / "skills"
    if not skills_root.is_dir() or not any(skills_root.rglob("SKILL.md")):
        raise RuntimeError(f"No SKILL.md found for {expected_name}")


def ensure_child(path: Path, parent: Path) -> None:
    path = path.resolve()
    parent = parent.resolve()
    if path.parent != parent:
        raise RuntimeError(f"Refusing path outside snapshot root: {path}")


def copy_snapshot(source: Path, target: Path, plugins_root: Path) -> None:
    validate_plugin(source, target.name)
    ensure_child(target, plugins_root)

    staging = plugins_root / f".sync-staging-{target.name}-{uuid.uuid4().hex}"
    backup = plugins_root / f".sync-backup-{target.name}-{uuid.uuid4().hex}"
    ensure_child(staging, plugins_root)
    ensure_child(backup, plugins_root)

    ignore = shutil.ignore_patterns(
        ".git",
        ".github",
        "__pycache__",
        "*.pyc",
        "*.log",
        "*.db",
        "diagnostics",
        "staging",
        "artifacts",
    )
    shutil.copytree(source, staging, ignore=ignore)
    validate_plugin(staging, target.name)

    moved_old = False
    try:
        if target.exists():
            target.rename(backup)
            moved_old = True
        staging.rename(target)
        validate_plugin(target, target.name)
    except Exception:
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
        if moved_old and backup.exists():
            backup.rename(target)
        if staging.exists():
            shutil.rmtree(staging)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def checkout_source(name: str, url: str, temp_root: Path) -> Path:
    destination = temp_root / name
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(destination)],
        check=True,
    )
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely refresh marketplace plugin snapshots."
    )
    parser.add_argument(
        "--plugin",
        action="append",
        choices=sorted(SOURCES),
        help="Sync only this plugin. Repeat to select more than one.",
    )
    parser.add_argument(
        "--local-source",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Use an already checked out source for a selected plugin.",
    )
    args = parser.parse_args()

    marketplace_root = Path(__file__).resolve().parents[1]
    plugins_root = (marketplace_root / "plugins").resolve()
    if not plugins_root.is_dir():
        raise RuntimeError(f"Snapshot root not found: {plugins_root}")

    selected = args.plugin or sorted(SOURCES)
    local_sources = parse_local_sources(args.local_source)
    unknown_local = sorted(set(local_sources) - set(selected))
    if unknown_local:
        raise RuntimeError(
            "Local source supplied for an unselected plugin: "
            + ", ".join(unknown_local)
        )

    with tempfile.TemporaryDirectory(prefix="codex-marketplace-sync-") as raw_temp:
        temp_root = Path(raw_temp)
        for name in selected:
            source = local_sources.get(name)
            if source is None:
                source = checkout_source(name, SOURCES[name], temp_root)
            validate_plugin(source, name)
            copy_snapshot(source, plugins_root / name, plugins_root)
            print(f"Synced {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
