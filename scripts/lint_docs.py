"""
Check the instruction tree: CLAUDE.md -> docs/index/*.md -> leaf documents.

Why: a new reader (or an AI session) starts at CLAUDE.md, opens ONE index file,
then ONE leaf. That only works if the root and index files stay small, every
leaf can be reached, every leaf says what it covers, and links are not broken.
The design is docs/review/INSTRUCTION-HIERARCHY.md (PENDING-TASKS H-7).

Checks:
  1. size     CLAUDE.md <= ROOT_MAX_TOKENS; each docs/index/*.md <= BRANCH_MAX_TOKENS
              (tokens estimated as characters / 4)
  2. reach    every leaf is linked from at least one docs/index/*.md
  3. header   every leaf has "Scope:", "Owner of:" and "See also:" lines in its
              first HEADER_WINDOW lines
  4. links    every relative link in every tracked .md file points at a file
              that exists (links inside ``` code blocks are ignored; #anchors
              are not checked)

Leaves are all .md files under docs/ plus CONTRIBUTING.md, except:
  - the index files themselves;
  - documents for people, read only on request (CLAUDE.md says so):
    README / TUTORIAL / DEMO_SCRIPT / DIAGRAMS / MANIFEST;
  - accepted ADRs (docs/adr/0*.md): they are never edited, so they cannot be
    given a header (CLAUDE.md, "How to work here").

Run:
    python scripts/lint_docs.py          # check the repository
    python scripts/lint_docs.py ROOT     # check another tree (tests)

Exit 0 if every check passes, 1 otherwise. Standard library only.
Invoked by `make lint` and the CI workflow.
"""

from __future__ import annotations

import pathlib
import re
import sys

DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The proposal said 400 / 250. CLAUDE.md deliberately carries the standing
# rules too (INSTRUCTION-HIERARCHY.md, status table), so the root limit
# follows that decision; index files get room for one line per document.
ROOT_MAX_TOKENS = 900
BRANCH_MAX_TOKENS = 350
HEADER_WINDOW = 15
HEADER_FIELDS = ("Scope:", "Owner of:", "See also:")

FOR_PEOPLE = {"README.md", "TUTORIAL.md", "DEMO_SCRIPT.md", "DIAGRAMS.md", "MANIFEST.md"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}

LINK = re.compile(r"\]\(([^)\s]+)\)")


def tokens(path: pathlib.Path) -> int:
    return len(path.read_text(encoding="utf-8")) // 4


def links_outside_code(text: str) -> list[tuple[int, str]]:
    found, in_code = [], False
    for n, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = re.sub(r"`[^`]*`", "", line)          # inline code is not a link
        found.extend((n, m) for m in LINK.findall(line))
    return found


def is_local(target: str) -> bool:
    return not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) and not target.startswith("#")


def resolve(source: pathlib.Path, target: str) -> pathlib.Path:
    path = target.split("#", 1)[0].split("?", 1)[0]
    return (source.parent / path).resolve()


def markdown_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in root.rglob("*.md") if not SKIP_DIRS.intersection(p.parts))


def leaves(root: pathlib.Path) -> list[pathlib.Path]:
    docs = root / "docs"
    out = []
    for p in sorted(docs.rglob("*.md")) if docs.is_dir() else []:
        rel = p.relative_to(docs)
        if rel.parts[0] == "index":
            continue
        if len(rel.parts) == 1 and p.name in FOR_PEOPLE:
            continue
        if rel.parts[0] == "adr" and re.match(r"\d{4}-", p.name):
            continue
        out.append(p)
    if (root / "CONTRIBUTING.md").is_file():
        out.append(root / "CONTRIBUTING.md")
    return out


def check(root: pathlib.Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    notes: list[str] = []
    rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731

    # 1. size
    claude = root / "CLAUDE.md"
    if claude.is_file() and (t := tokens(claude)) > ROOT_MAX_TOKENS:
        problems.append(f"size    CLAUDE.md is ~{t} tokens (limit {ROOT_MAX_TOKENS})")
    branches = sorted((root / "docs" / "index").glob("*.md"))
    for b in branches:
        if (t := tokens(b)) > BRANCH_MAX_TOKENS:
            problems.append(f"size    {rel(b)} is ~{t} tokens (limit {BRANCH_MAX_TOKENS})")

    # 2. reach
    parents: dict[pathlib.Path, list[str]] = {}
    for b in branches:
        for _, target in links_outside_code(b.read_text(encoding="utf-8")):
            if is_local(target):
                parents.setdefault(resolve(b, target), []).append(b.stem)
    for leaf in leaves(root):
        owners = parents.get(leaf.resolve(), [])
        if not owners:
            problems.append(f"reach   {rel(leaf)} is not linked from any docs/index/*.md")
        elif len(owners) > 1:
            notes.append(f"{rel(leaf)} is linked from {len(owners)} index files: {', '.join(owners)}")

    # 3. header
    for leaf in leaves(root):
        head = "\n".join(leaf.read_text(encoding="utf-8").splitlines()[:HEADER_WINDOW])
        missing = [f for f in HEADER_FIELDS if f not in head]
        if missing:
            problems.append(f"header  {rel(leaf)} lacks {', '.join(missing)} "
                            f"in its first {HEADER_WINDOW} lines")

    # 4. links
    for md in markdown_files(root):
        for n, target in links_outside_code(md.read_text(encoding="utf-8")):
            if is_local(target) and not resolve(md, target).exists():
                problems.append(f"link    {rel(md)}:{n} -> {target} (no such file)")

    return problems, notes


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_ROOT
    problems, notes = check(root)
    for note in notes:
        print(f"note    {note}")
    if problems:
        print(f"FAIL  {len(problems)} documentation problem(s):")
        for p in problems:
            print(f"  {p}")
        print("Rules and reasons: docs/review/INSTRUCTION-HIERARCHY.md")
        return 1
    print(f"OK  docs tree: root <= {ROOT_MAX_TOKENS} tokens, index files <= "
          f"{BRANCH_MAX_TOKENS}, every leaf reachable with a Scope/Owner of/See also "
          f"header, no broken links")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
