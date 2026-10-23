"""
Enforce the dashboard→app import boundary.

Run:
    python scripts/lint_boundaries.py

Exits 0 if no violations, 1 otherwise.

Invoked by:
    - `make lint`
    - the pre-commit hook `.pre-commit-config.yaml`
    - the CI workflow `.github/workflows/ci.yml`
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

FORBIDDEN_PATTERNS = [
    re.compile(r"^\s*from\s+app(\.|\s+import)"),
    re.compile(r"^\s*import\s+app(\.|\s|$)"),
]

# Files to check.  Only .py files inside dashboard/.
TARGET_DIR = ROOT / "dashboard"


def find_violations() -> list[tuple[pathlib.Path, int, str]]:
    violations: list[tuple[pathlib.Path, int, str]] = []
    for path in TARGET_DIR.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pat in FORBIDDEN_PATTERNS:
                if pat.match(line):
                    violations.append((path.relative_to(ROOT), lineno, line.strip()))
    return violations


def main() -> int:
    violations = find_violations()

    if not violations:
        print("✔ no dashboard→app imports")
        return 0

    print("✖ dashboard/ imports from app/:")
    print()
    for path, lineno, line in violations:
        print(f"  {path}:{lineno}")
        print(f"      {line}")
    print()
    print("The dashboard and the API are peers.  Neither may import the other.")
    print("Move the code you need into shared/ instead.")
    print()
    print("See docs/adr/0009-shared-code.md for the reasoning.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
