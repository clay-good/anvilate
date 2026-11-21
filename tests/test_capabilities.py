"""Optional capabilities: one install command per platform and channel, one sentence everywhere."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from anvilate.capabilities import CAPABILITIES, capability, install_command, install_remedy
from anvilate.refusal import RefusalError
from conftest import parsed_source

_SRC = Path(__file__).parents[1] / "src" / "anvilate"


@pytest.mark.parametrize(("platform", "prefix", "expected"), [
    ("darwin", "/Users/a/.venv", "pip install 'anvilate[geometry]'"),
    ("win32", "C:\\\\Users\\\\a\\\\venv", 'pip install "anvilate[geometry]"'),
    ("linux", "/home/a/.local/share/uv/tools/anvilate",
     "uv tool install --force 'anvilate[geometry]'"),
    ("linux", "/home/a/.local/pipx/venvs/anvilate", "pipx install --force 'anvilate[geometry]'"),
])  # fmt: skip
def test_the_install_command_follows_the_platform_and_the_channel(platform, prefix, expected):
    assert install_command("geometry", platform=platform, prefix=prefix) == expected


def test_every_capability_is_an_extra_the_package_declares():
    import tomllib

    extras = tomllib.loads((_SRC.parents[1] / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert {c.extra for c in CAPABILITIES} <= set(extras)
    with pytest.raises(RefusalError, match="no optional capability"):
        capability("teleport")


def test_no_install_instruction_is_written_out_beside_the_shared_one():
    """Every message that tells a user to install an extra comes from `install_remedy`, so
    `doctor` and the tool that needs the capability say the same thing."""
    written = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name == "capabilities.py":
            continue
        for node in ast.walk(parsed_source(path)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "pip install" in node.value and "anvilate[" in node.value:
                    written.append(f"{path.relative_to(_SRC)}:{node.lineno}")
    assert not written, written
    assert install_remedy("pdf").startswith("PDF reader is an optional capability, not installed")
