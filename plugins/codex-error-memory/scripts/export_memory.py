#!/usr/bin/env python3
"""Export Codex error memories to Markdown."""

from __future__ import annotations

import argparse
from pathlib import Path

from memory_cli import DEFAULT_DB, connect, get_project, init_db, markdown_safe


def main() -> int:
    parser = argparse.ArgumentParser(description="Export error memory as Markdown.")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--project", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with connect(Path(args.db)) as conn:
        init_db(conn)
        project_id = get_project(conn, args.project, create=False)
        rows = conn.execute(
            """
            SELECT p.*, s.root_cause, s.fix_steps, s.prevention_rule, s.verification_steps,
                   s.files_often_involved, s.commands_often_used
            FROM error_patterns p
            LEFT JOIN solutions s ON s.pattern_id = p.id
            WHERE p.project_id IS NULL OR p.project_id = ?
            ORDER BY p.category, p.title
            """,
            (project_id,),
        ).fetchall()

    parts = ["# Codex Error Memory", ""]
    for row in rows:
        parts.extend(
            [
                f"## {markdown_safe(row['title'], max_len=120)}",
                "",
                f"- Category: `{markdown_safe(row['category'], max_len=80)}`",
                f"- Severity: `{markdown_safe(row['severity'], max_len=80)}`",
                f"- Confidence: `{row['confidence']}`",
                "",
                "### Signature",
                "",
                markdown_safe(row["signature"]),
                "",
                "### Root Cause",
                "",
                markdown_safe(row["root_cause"]),
                "",
                "### Fix Steps",
                "",
                markdown_safe(row["fix_steps"]),
                "",
                "### Prevention",
                "",
                markdown_safe(row["prevention_rule"]),
                "",
                "### Verification",
                "",
                markdown_safe(row["verification_steps"]),
                "",
            ]
        )
    Path(args.out).write_text("\n".join(parts), encoding="utf-8")
    print(f"Exported {len(rows)} memories to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
