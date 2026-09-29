from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def _metadata() -> tuple[dict[str, object], dict[str, object]]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    server = json.loads((ROOT / "server.json").read_text())
    return project, server


def test_registry_metadata_matches_the_python_release() -> None:
    project, server = _metadata()
    package = server["packages"][0]
    version = project["project"]["version"]

    assert server["name"] == "io.github.clay-good/anvilate"
    assert server["version"] == version
    assert package["identifier"] == project["project"]["name"]
    assert package["version"] == version
    assert package["registryType"] == "pypi"
    assert package["runtimeHint"] == "uvx"
    assert package["transport"] == {"type": "stdio"}


def test_registry_install_command_selects_the_mcp_entry_point() -> None:
    project, server = _metadata()
    package = server["packages"][0]
    version = project["project"]["version"]

    assert package["runtimeArguments"] == [
        {
            "type": "named",
            "name": "--from",
            "value": f"anvilate=={version}",
            "description": "Install the exact Anvilate release.",
        },
        {
            "type": "positional",
            "value": "anvilate-mcp",
            "description": "Run the MCP server over stdio.",
        },
    ]
    assert project["project"]["scripts"]["anvilate-mcp"] == "anvilate.mcp:main"


def test_readme_proves_registry_namespace_ownership() -> None:
    _, server = _metadata()

    marker = f"<!-- mcp-name: {server['name']} -->"
    assert marker in (ROOT / "README.md").read_text()


def test_registry_workflow_pins_and_verifies_the_publisher() -> None:
    workflow_text = (ROOT / ".github/workflows/publish-mcp-registry.yml").read_text()
    workflow = yaml.load(workflow_text, Loader=yaml.BaseLoader)

    assert workflow["on"]["release"]["types"] == ["published"]
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["permissions"]["id-token"] == "write"
    assert "login github-oidc" in workflow_text
    assert "releases/latest" not in workflow_text
    assert "MCP_PUBLISHER_VERSION: v1.8.1" in workflow_text
    checksum = re.search(r"MCP_PUBLISHER_SHA256: ([0-9a-f]+)", workflow_text)
    assert checksum is not None and len(checksum.group(1)) == 64
    assert "sha256sum --check --strict" in workflow_text
    assert workflow_text.index("validate server.json") < workflow_text.index("login github-oidc")
    assert workflow_text.index("login github-oidc") < workflow_text.index("publish server.json")
