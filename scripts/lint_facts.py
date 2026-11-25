#!/usr/bin/env python3
"""
Check that tables copied into the documentation still match the code.

Why this exists
---------------
Some facts are written in a document *and* decided in code. The document is
for reading; the code is what actually runs. When someone changes the code
and forgets the document, the document starts lying — quietly, because
nothing breaks. That is how the review found four wrong copies of the login
URL and a lifecycle table missing an action (INSTRUCTION-HIERARCHY.md,
"Single-owner table").

Most copies can simply become a link. Two cannot without making a page
useless — a cheat sheet that says "see elsewhere" for every value is not a
cheat sheet. For those two, the code is the owner and this script checks
every copy against it:

    Table header in a .md file                    Owner in the code
    --------------------------------------------  ------------------------------
    | Action | From | To | Who |                  shared/lifecycle.py
                                                    TRANSITIONS, ACTION_ROLES
    | Role | Access TTL | Refresh TTL |           shared/config.py defaults
      Max sessions | Idle ... |                     jwt_*_ttl_*, jwt_*_jitter_*,
                                                    session_limit_*, session_idle_*

Any markdown table whose header starts like one of these is checked, wherever
it is, so a new copy is checked from the day it is written.

It also checks setting NAMES, because a wrong name fails silently (the
settings loader ignores names it does not know): every setting in
shared/config.py has a line in .env.example, every name in .env.example is a
setting, and a backticked name in the docs that looks like a setting is one.
See "Setting names" below for what counts and what is exempt.

How it reads the code
---------------------
It parses the two Python files with `ast` instead of importing them, so it
needs only the standard library (no pydantic, no database) and never runs
project code.

Run:  python scripts/lint_facts.py [ROOT]
Exit: 0 every copy matches, 1 at least one differs, 2 the code could not be read.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROLES = ("citizen", "provider", "coordinator", "admin")

# Folders never searched for markdown (tools, caches, dependencies).
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".pytest_cache", ".ruff_cache", "htmlcov"}


class CodeError(Exception):
    """The owner file is missing or no longer has the expected shape."""


# ---------------------------------------------------------------------------
#  Reading the owners (the code)
# ---------------------------------------------------------------------------

def _module(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise CodeError(f"cannot read {path}: {exc}") from exc


def _assigned_dict(tree: ast.Module, name: str) -> ast.Dict:
    """The dict literal assigned to a top-level `name` (plain or annotated)."""
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        else:
            continue
        if target == name and isinstance(value, ast.Dict):
            return value
    raise CodeError(f"no dict literal named {name}")


def _state(node: ast.expr) -> str:
    """`S.created` → "created"."""
    if isinstance(node, ast.Attribute):
        return node.attr
    raise CodeError(f"unexpected state expression: {ast.dump(node)}")


def _string_set(node: ast.expr) -> set[str]:
    """`frozenset({...})` of states or of role strings → a set of names."""
    if not (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Set)):
        raise CodeError(f"expected frozenset({{...}}), got {ast.dump(node)}")
    out: set[str] = set()
    for elt in node.args[0].elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.add(elt.value)
        else:
            out.add(_state(elt))
    return out


def lifecycle_rules(root: Path) -> dict[str, tuple[set[str], str, set[str]]]:
    """action → (from states, to state, roles), read from shared/lifecycle.py."""
    tree = _module(root / "shared" / "lifecycle.py")
    transitions = _assigned_dict(tree, "TRANSITIONS")
    roles = _assigned_dict(tree, "ACTION_ROLES")

    role_map: dict[str, set[str]] = {}
    for key, value in zip(roles.keys, roles.values, strict=True):
        role_map[ast.literal_eval(key)] = _string_set(value)

    rules: dict[str, tuple[set[str], str, set[str]]] = {}
    for key, value in zip(transitions.keys, transitions.values, strict=True):
        action = ast.literal_eval(key)
        if not (isinstance(value, ast.Tuple) and len(value.elts) == 2):
            raise CodeError(f"TRANSITIONS[{action!r}] is not a (from, to) pair")
        rules[action] = (_string_set(value.elts[0]), _state(value.elts[1]), role_map.get(action, set()))
    return rules


def _settings_class(root: Path) -> ast.ClassDef:
    tree = _module(root / "shared" / "config.py")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return node
    raise CodeError("shared/config.py has no class Settings")


def settings_names(root: Path) -> set[str]:
    """Every setting, as the upper-case name read from the environment."""
    return {
        stmt.target.id.upper()
        for stmt in _settings_class(root).body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }


def settings_defaults(root: Path) -> dict[str, int]:
    """Integer defaults of the Settings class in shared/config.py."""
    out: dict[str, int] = {}
    for stmt in _settings_class(root).body:
        if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value):
            continue
        value = stmt.value
        if isinstance(value, ast.Call):  # Field(default=..., ...)
            value = next((kw.value for kw in value.keywords if kw.arg == "default"), None)
        if isinstance(value, ast.Constant) and type(value.value) is int:
            out[stmt.target.id] = value.value
    return out


def session_rules(root: Path) -> dict[str, tuple[int, int, int, int, int, int]]:
    """role → (access min, access jitter, refresh days, refresh jitter, max sessions, idle hours)."""
    d = settings_defaults(root)
    out = {}
    for role in ROLES:
        names = (
            f"jwt_access_ttl_{role}_min", f"jwt_access_jitter_{role}_min",
            f"jwt_refresh_ttl_{role}_days", f"jwt_refresh_jitter_{role}_days",
            f"session_limit_{role}", f"session_idle_{role}_hours",
        )
        missing = [n for n in names if n not in d]
        if missing:
            raise CodeError(f"shared/config.py has no integer default for {', '.join(missing)}")
        out[role] = tuple(d[n] for n in names)
    return out


# ---------------------------------------------------------------------------
#  Reading the copies (markdown tables)
# ---------------------------------------------------------------------------

def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def tables(text: str):
    """Yield (line number of header, header cells, body rows) for each table, outside code fences."""
    lines = text.splitlines()
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif (not in_fence and line.lstrip().startswith("|") and i + 1 < len(lines)
              and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])):
            header = _cells(line)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, _cells(lines[j])))
                j += 1
            yield i + 1, header, rows
            i = j
            continue
        i += 1


def _names(cell: str) -> set[str]:
    """"`created`, approved" → {"created", "approved"}."""
    return {p.strip(" `*") for p in cell.split(",") if p.strip(" `*")}


_DURATION = re.compile(r"^(\d+)\s*(min|minutes?|hours?|h|days?)(?:\s*±\s*(\d+))?$")


def _duration(cell: str) -> tuple[int, str, int | None]:
    m = _DURATION.match(cell.strip())
    if not m:
        raise ValueError(f"cannot read duration {cell!r}")
    unit = {"min": "min", "minute": "min", "minutes": "min", "h": "hours", "hour": "hours",
            "hours": "hours", "day": "days", "days": "days"}[m.group(2)]
    return int(m.group(1)), unit, int(m.group(3)) if m.group(3) else None


def _idle_hours(cell: str) -> int:
    n, unit, _ = _duration(cell)
    if unit == "days":
        return n * 24
    if unit == "hours":
        return n
    raise ValueError(f"idle time {cell!r} must be in hours or days")


def check_lifecycle(path: str, line: int, rows, rules) -> list[str]:
    problems = []
    seen = set()
    for row_line, cells in rows:
        if len(cells) < 4:
            problems.append(f"{path}:{row_line}: expected 4 cells, found {len(cells)}")
            continue
        action = cells[0].strip(" `*")
        seen.add(action)
        if action not in rules:
            problems.append(f"{path}:{row_line}: action `{action}` is not in shared/lifecycle.py")
            continue
        want_from, want_to, want_roles = rules[action]
        got_from, got_to, got_roles = _names(cells[1]), cells[2].strip(" `*"), _names(cells[3])
        if got_from != want_from:
            problems.append(f"{path}:{row_line}: `{action}` from {sorted(got_from)}, code says {sorted(want_from)}")
        if got_to != want_to:
            problems.append(f"{path}:{row_line}: `{action}` to {got_to!r}, code says {want_to!r}")
        if got_roles != want_roles:
            problems.append(f"{path}:{row_line}: `{action}` who {sorted(got_roles)}, code says {sorted(want_roles)}")
    for action in sorted(set(rules) - seen):
        problems.append(f"{path}:{line}: table is missing action `{action}` (in shared/lifecycle.py)")
    return problems


def check_sessions(path: str, line: int, rows, rules) -> list[str]:
    problems = []
    seen = set()
    for row_line, cells in rows:
        role = cells[0].strip(" `*")
        seen.add(role)
        if role not in rules:
            problems.append(f"{path}:{row_line}: role {role!r} is not one of {', '.join(ROLES)}")
            continue
        acc, acc_j, ref, ref_j, limit, idle = rules[role]
        try:
            got_acc = _duration(cells[1])
            got_ref = _duration(cells[2])
            got_limit = int(cells[3])
            got_idle = _idle_hours(cells[4])
        except (ValueError, IndexError) as exc:
            problems.append(f"{path}:{row_line}: {exc}")
            continue
        if got_acc != (acc, "min", acc_j):
            problems.append(f"{path}:{row_line}: {role} access {cells[1]!r}, code says {acc} min ± {acc_j}")
        if got_ref != (ref, "days", ref_j):
            problems.append(f"{path}:{row_line}: {role} refresh {cells[2]!r}, code says {ref} days ± {ref_j}")
        if got_limit != limit:
            problems.append(f"{path}:{row_line}: {role} max sessions {got_limit}, code says {limit}")
        if got_idle != idle:
            problems.append(f"{path}:{row_line}: {role} idle {cells[4]!r} = {got_idle} h, code says {idle} h")
    for role in ROLES:
        if role not in seen:
            problems.append(f"{path}:{line}: table is missing role {role!r}")
    return problems


# ---------------------------------------------------------------------------
#  Setting names
# ---------------------------------------------------------------------------
#
# pydantic-settings silently IGNORES an environment variable it does not know.
# A misspelt `PRIVACY_GRACE_HOURS=24` in .env changes nothing and raises no
# error, so a wrong name in a document or in .env.example is a trap: the
# reader follows it, nothing happens, and nobody is told. Three rules:
#
#   1. every setting has a line in .env.example (so it can be discovered);
#   2. every name in .env.example is a setting (so copying it does something);
#   3. a backticked name in the docs that looks like a setting is one.
#
# "Looks like a setting" = its first word is the first word of some setting
# (JWT_, SESSION_, PRIVACY_, FILE_, ...). That keeps out shell variables,
# document names and warehouse tables, which are not settings at all.

# Records of past states quote old, wrong names on purpose.
HISTORY = ("docs/review/", "docs/adr/", "CHANGELOG.md")

# Put this at the end of a line that names a non-setting on purpose
# (a Flask config key, a deliberately misspelt example).
NOT_A_SETTING = "<!-- not a setting -->"

_ENV_LINE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=")
_DOC_NAME = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)(?:=[^`]*)?`")


def env_example_names(root: Path) -> dict[str, int]:
    """name → line number, for each `NAME=` (also `# NAME=`) in .env.example."""
    path = root / ".env.example"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CodeError(f"cannot read {path}: {exc}") from exc
    out: dict[str, int] = {}
    for n, line in enumerate(text.splitlines(), 1):
        m = _ENV_LINE.match(line)
        if m:
            out.setdefault(m.group(1), n)
    return out


def check_env_example(settings: set[str], env: dict[str, int]) -> list[str]:
    problems = [
        f".env.example: no line for {name} (a setting in shared/config.py)"
        for name in sorted(settings - set(env))
    ]
    problems += [
        f".env.example:{line}: {name} is not a setting in shared/config.py, so it is ignored"
        for name, line in sorted(env.items(), key=lambda kv: kv[1])
        if name not in settings
    ]
    return problems


def check_doc_names(rel: str, text: str, settings: set[str], doc_names: frozenset[str] = frozenset()) -> list[str]:
    """`doc_names`: stems of the repository's .md files (`SEED_REFERENCE`), which are not settings."""
    if rel.startswith(HISTORY):
        return []
    prefixes = {name.split("_", 1)[0] for name in settings}
    problems = []
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence or NOT_A_SETTING in line:
            continue
        for name in _DOC_NAME.findall(line):
            if name.split("_", 1)[0] in prefixes and name not in settings and name not in doc_names:
                problems.append(f"{rel}:{n}: `{name}` looks like a setting but shared/config.py has none by that name")
    return problems


def markdown_files(root: Path):
    for p in sorted(root.rglob("*.md")):
        if not any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            yield p


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    try:
        lifecycle = lifecycle_rules(root)
        sessions = session_rules(root)
        settings = settings_names(root)
        env = env_example_names(root)
    except CodeError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    problems: list[str] = check_env_example(settings, env)
    checked = 0
    md_files = list(markdown_files(root))
    doc_names = frozenset(p.stem for p in md_files)
    for md in md_files:
        rel = md.relative_to(root).as_posix()
        text = md.read_text(encoding="utf-8")
        problems += check_doc_names(rel, text, settings, doc_names)
        for line, header, rows in tables(text):
            h = [c.lower() for c in header]
            if h[:4] == ["action", "from", "to", "who"]:
                checked += 1
                problems += check_lifecycle(rel, line, rows, lifecycle)
            elif h[:4] == ["role", "access ttl", "refresh ttl", "max sessions"] and len(h) > 4 and h[4].startswith("idle"):
                checked += 1
                problems += check_sessions(rel, line, rows, sessions)

    for p in problems:
        print(p)
    if problems:
        print(f"FAIL {len(problems)} difference(s) between the documents and the code", file=sys.stderr)
        return 1
    print(f"OK {checked} copied table(s) match shared/lifecycle.py and shared/config.py; "
          f"{len(settings)} settings agree with .env.example and the docs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
