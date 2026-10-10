"""Write the docs-page inventory: who each page is for, what links to it, what it names.

    python tools/audit/pages.py            # rewrite docs/api/docs-pages.txt
    python tools/audit/pages.py --check    # exit 1 if the file is not what this writes

audit-agent-surface 1.4. One line per page under `docs/`:

    page | the index section it is filed under | pages that link to it | what it names that is gone

The section is who the page is for: the index (`docs/README.md`) files every page under
what its reader is trying to do. "Gone" is what can be checked without reading the page: a
relative link whose file is missing, an `anvilate <command>` the parser does not have, an
MCP tool the catalog does not list, and an `--option` no command takes. Whether a page's
prose is still true is a person's reading; this narrows where to look.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
PAGE = DOCS / "api" / "docs-pages.txt"

_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
_FENCE = re.compile(r"```.*?```", re.DOTALL)


def _surface() -> tuple[set[str], set[str], set[str]]:
    """The commands, every option any command takes, and the MCP tool names."""
    from anvilate.cli import _build_parser
    from anvilate.mcp import tool_catalog

    parser = _build_parser()
    commands = parser._subparsers._group_actions[0].choices  # noqa: SLF001
    options = {
        option
        for sub in (parser, *commands.values())
        for action in sub._actions  # noqa: SLF001
        for option in action.option_strings
        if option.startswith("--")
    }
    return set(commands), options, {tool.name for tool in tool_catalog()}


def _sections() -> dict[str, str]:
    """Each page's section in the index, by file name."""
    filed: dict[str, str] = {}
    section = ""
    for line in (DOCS / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        for target in _LINK.findall(line):
            if "/" not in target and target.endswith(".md"):
                filed.setdefault(target, section)
    return filed


def inventory() -> list[tuple[str, str, list[str], list[str]]]:
    """Every page as ``(name, section, linked from, gone)``, in name order."""
    commands, options, tools = _surface()
    pages = sorted(path for path in DOCS.glob("*.md") if path.name != "README.md")
    texts = {path.name: path.read_text(encoding="utf-8") for path in pages}
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    filed = _sections()
    rows = []
    for path in pages:
        text = texts[path.name]
        linked = sorted(
            other.removesuffix(".md")
            for other, body in texts.items()
            if other != path.name and f"]({path.name}" in body
        )
        if f"](docs/{path.name}" in readme:
            linked.insert(0, "README")
        gone: list[str] = []
        for target in sorted(set(_LINK.findall(text))):
            if "://" in target or target.startswith("mailto:"):
                continue
            if not (DOCS / target).resolve().exists():
                gone.append(f"link {target}")
        prose = _FENCE.sub("", text)
        for command in sorted(set(re.findall(r"`anvilate ([a-z][a-z-]*)\b", text))):
            if command not in commands and command != "mcp":
                gone.append(f"command {command}")
        spans = " ".join(re.findall(r"`([^`\n]+)`", prose))
        for option in sorted(set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", spans))):
            if option not in options and option not in _NOT_OURS:
                gone.append(f"option {option}")
        for tool in sorted(set(re.findall(r"`([a-z]+_[a-z_]+)` tool\b", prose))):
            if tool not in tools:
                gone.append(f"tool {tool}")
        gone = [what for what in gone if (path.name, what) not in _NAMED_AS_ABSENT]
        rows.append((path.name, filed.get(path.name, "not in the index"), linked, gone))
    return rows


# What a page names in order to say it does not exist. Each is read where it stands.
_NAMED_AS_ABSENT = frozenset(
    {
        ("headless-cli.md", "command frobnicate"),  # the example of a command nobody has
        ("headless-cli.md", "option --override"),  # "There is no `--override`."
        ("quality-interchange.md", "option --override"),  # "and there is no `--override`."
    }
)

# Options a page names that belong to another program: pip, pytest, the MCP launcher, git.
_NOT_OURS = frozenset(
    {
        "--context",
        "--out",
        "--no-index",
        "--no-deps",
        "--wheel",
        "--durations",
        "--port",
        "--check",
        "--first-part",
        "--expected-failures",
    }
)


def page() -> str:
    rows = inventory()
    lines = [
        "# Every page under docs/, as: page | filed under | linked from | names something gone",
        "# Generated by tools/audit/pages.py; do not edit. The section a page is filed under",
        "# in docs/README.md is who it is for. The last column is empty when every relative",
        "# link, command, option and tool the page names still exists.",
        f"# {len(rows)} pages.",
        "",
    ]
    for name, section, linked, gone in rows:
        lines.append(
            f"{name} | {section} | {', '.join(linked) or 'nothing'} | {'; '.join(gone) or '-'}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if "--check" in argv:
        if not PAGE.is_file() or PAGE.read_text(encoding="utf-8") != page():
            print(f"{PAGE.relative_to(REPO)} is stale; run tools/audit/pages.py")
            return 1
        return 0
    PAGE.write_text(page(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
