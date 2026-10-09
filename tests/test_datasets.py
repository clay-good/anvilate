"""The bundled tables are the dataset: self-describing, versioned, and pinned in evidence.

Anvilate is one product, so its open data lives in this repository (docs/datasets.md) rather
than in a repository beside it. What the standards-data requirement asks of a published
dataset still has to hold: a reader can use a table without Anvilate, a version means fixed
bytes, and the evidence names the version each build read.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from anvilate.standards.datasets import bundled_datasets

_REPO = pathlib.Path(__file__).resolve().parents[1]
_DATA = _REPO / "src" / "anvilate" / "standards" / "data"
_LOCK = pathlib.Path(__file__).with_name("dataset_versions.json")


def test_a_dataset_version_means_fixed_bytes():
    """Changing a table without bumping its version fails here, so a version is a pin.

    To change a table: bump `dataset.version` in its header, then record the new version's
    digest in tests/dataset_versions.json. Earlier versions stay in the file.
    """
    lock = json.loads(_LOCK.read_text(encoding="utf-8"))
    pins = bundled_datasets()
    assert {pin.file for pin in pins} == set(lock), "a table was added or removed: update the lock"
    for pin in pins:
        recorded = lock[pin.file].get(pin.version)
        assert recorded is not None, (
            f"{pin.file} declares version {pin.version}, which the lock does not record: "
            f"add {pin.version!r}: {pin.sha256!r} to tests/dataset_versions.json"
        )
        assert recorded == pin.sha256, (
            f"{pin.file} changed without a version bump: its bytes are not version "
            f"{pin.version}'s. Bump dataset.version in the file and record the new digest"
        )


def test_every_table_is_usable_without_anvilate():
    """A third party reads a table with a YAML parser alone and finds what it is and its terms."""
    script = (
        "import sys, pathlib, yaml\n"
        "for path in sorted(pathlib.Path(sys.argv[1]).glob('*.yaml')):\n"
        "    doc = yaml.safe_load(path.read_text(encoding='utf-8'))\n"
        "    head = doc['dataset']\n"
        "    for key in ('name', 'version', 'license', 'retrieved'):\n"
        "        assert str(head.get(key) or '').strip(), (path.name, key)\n"
        "    assert len(doc) > 1, (path.name, 'no records')\n"
        "assert not [m for m in sys.modules if m.startswith('anvilate')]\n"
        "print('ok')\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", script, str(_DATA)], capture_output=True, text=True
    )
    assert done.returncode == 0 and done.stdout.strip() == "ok", done.stderr


def test_both_export_doors_pin_the_datasets_in_the_bundle(tmp_path):
    """The CLI and MCP bundles record every table's version and digest."""

    from anvilate.mcp import handle_request
    from cli_output import run_cli

    _code, out, _err = run_cli(
        "export", str(_REPO / "examples" / "padeye.spec.yaml"), "--format", "json"
    )
    exported = json.loads(out)
    bundle = exported["bundles"][0]["bundle"] if "bundles" in exported else exported["bundle"]
    expected = [pin.model_dump(mode="json") for pin in bundled_datasets()]
    assert bundle["datasets"] == expected

    import yaml

    document = yaml.safe_load((_REPO / "examples" / "padeye.spec.yaml").read_text())
    screened = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "run_validation", "arguments": {"spec": document}},
        }
    )["result"]["structuredContent"]
    served = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "export_artifact",
                "arguments": {"subject": screened["subject"], "format": "evidence_bundle"},
            },
        }
    )["result"]["structuredContent"]
    assert served["bundle"]["datasets"] == expected
