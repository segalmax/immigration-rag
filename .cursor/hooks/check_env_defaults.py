#!/usr/bin/env python3
"""
afterFileEdit hook: block os.environ.get(KEY, default) pattern in Python files.
Fires after every agent file edit. Injects a warning if violations are found.
"""
import json
import re
import sys
from pathlib import Path

PATTERN = re.compile(r'os\.environ\.get\([^)]+,[^)]+\)|os\.getenv\([^)]+,[^)]+\)')


def check(file_path: str) -> "list[str]":
    path = Path(file_path)
    if path.suffix != ".py" or not path.exists():
        return []
    lines = path.read_text().splitlines()
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if PATTERN.search(line):
            violations.append(f"  line {i}: {stripped}")
    return violations


def main():
    payload = json.load(sys.stdin)
    file_path = payload.get("file_path") or payload.get("path") or ""
    violations = check(file_path)

    if not violations:
        print(json.dumps({}))
        return

    msg = (
        f"⚠️ no-env-defaults violation in {file_path}:\n"
        + "\n".join(violations)
        + "\n\nUse os.environ[\"KEY\"] (fails loudly) or a plain constant. Never pass a default to os.environ.get()."
    )
    print(json.dumps({"followup_message": msg}))


main()
