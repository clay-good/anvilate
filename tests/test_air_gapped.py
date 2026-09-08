"""The pipeline under a closed socket layer, and the one door that can open.

`sandbox-security` asks for this in as many words: in air-gapped mode the whole pipeline
completes with **zero network calls**, and the property is held by an automated test that
fails on any attempted access rather than by anybody's recollection of what the code does.
Until `anvilate.fetch` shipped there was nothing in the package that could open a socket,
which made the claim easy and unwatched. Now there is exactly one line that can, so the
claim is worth stating and worth attacking.

Three things are asserted here, and the second is the one that gives the first any value.

* **The golden path runs with the socket layer closed.** Spec bytes to scorecard to DXF to
  evidence bundle to a signed attestation and back through verification, plus a rendered
  calculation report and a compile over the MCP request handler — all under a block that
  raises on any outbound attempt.
* **The block is real.** A deliberate connection, a `urlopen`, and a bare DNS lookup are
  each made under it and each must raise. A canary that cannot catch a network call
  passes every run and means nothing, and this shape of test is the easiest one in the
  repository to write wrong: patch a name nothing calls, and the golden path goes green
  because it was never going to make a call anyway.
* **The one door stays shut unless a caller opens it.** `fetch_dataset` refuses without
  consent *before* it reaches the transport, so nothing implicit can trip it — and with
  consent it really does try the network, which the block catches. That is the difference
  between a library that does not phone home and a library nobody has checked.

The last three tests are the ratchet, and they are three because naming clients is not a
job that finishes. `fetch` is the only module that imports a network client; the package's
third-party imports are exactly its declared dependencies, so a client nobody thought to
blocklist fails anyway; and no import is smuggled past both as a string.
"""

from __future__ import annotations

import ast
import pathlib
import re
import socket
import sys
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from anvilate.fetch import ConsentRequired, DatasetRecipe, fetch_dataset
from conftest import parsed_source

_REPO = pathlib.Path(__file__).resolve().parents[1]
# A distribution's name on PyPI is not the name it is imported by.
_IMPORT_NAME = {"pyyaml": "yaml"}


class NetworkAttempted(AssertionError):
    """Raised in place of any outbound call while the socket layer is closed."""


@contextmanager
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Close every way out of the process, at the layer they all pass through.

    The patch is on `socket.socket` itself rather than on a module's imported alias,
    because a module that did `from socket import create_connection` at import time holds
    its own reference and a patch of the module attribute would miss it. Name resolution
    for `connect` goes through the class on every call, so a socket already constructed is
    caught too. `getaddrinfo` is included because a DNS lookup is an outbound call in its
    own right — a resolver query leaves the machine whether or not a connection follows.
    """

    def _refuse(*args: object, **kwargs: object) -> object:
        raise NetworkAttempted("the air-gapped pipeline attempted a network call")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)
    yield


def test_the_block_catches_a_call_that_is_really_made(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every way out is tried, under the block, and every one of them raises.

    This is the test that makes the rest of the file mean something. A canary written
    against a name the runtime does not call is indistinguishable from a clean run: the
    golden path would pass because it makes no calls, not because the block works. So the
    calls are made here on purpose, at all three layers a caller might reach for — the raw
    socket, the convenience constructor, and the URL opener the fetch transport uses.
    """
    from urllib.request import urlopen

    with _no_network(monkeypatch):
        with pytest.raises(NetworkAttempted):
            socket.create_connection(("example.invalid", 80), timeout=0.1)
        with pytest.raises(NetworkAttempted):
            # Closed on the way out even though `connect` raises: an un-context-managed
            # socket here leaked one per run, and the `ResourceWarning` it raised was the
            # only thing standing between this suite and warnings-as-errors.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw:
                raw.connect(("127.0.0.1", 9))
        with pytest.raises(NetworkAttempted):
            socket.getaddrinfo("example.invalid", 80)
        with pytest.raises(NetworkAttempted):
            urlopen("https://example.invalid/dataset.json")  # noqa: S310 - refused, not fetched


def test_the_golden_path_completes_with_the_socket_layer_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec bytes to a verified, attested evidence bundle, with no way out of the process.

    The worked lug is the longest path the package has today: a scorecard, a DXF artifact,
    an evidence bundle, an in-toto attestation over both subjects, and a verification pass
    over the result. Everything the requirement names that exists is in it. Geometry and
    STEP export are not, because no writer ships yet — see `docs/export-targets.md`; when
    one lands it belongs in this call rather than in a second test.
    """
    from examples.attested_evidence_bundle import attest_the_lug

    from anvilate.scorecard import CheckStatus

    with _no_network(monkeypatch):
        bundle, rebuilt, bumped, verified, tampered, _unkeyed, _unread = attest_the_lug()

    # Asserted rather than merely run: an offline pipeline that produced nothing, or that
    # silently degraded to an unverified seal, would satisfy "made no network call".
    assert bundle.digest == rebuilt.digest, "the same inputs did not rebuild the same bundle"
    assert bundle.digest != bumped.digest, "a materials-database bump left the digest alone"
    assert verified.status is CheckStatus.PASS
    assert tampered.status is CheckStatus.FAIL


def test_a_report_renders_and_a_spec_compiles_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two surfaces most likely to reach for the network, and neither does.

    A rendered document is where a stylesheet or a web font would be fetched — this one
    inlines everything, which is why it stays one air-gapped file. The MCP handler is
    where a server would resolve a schema `$ref` over https; it validates against what it
    ships instead. Both claims are made in the README, and neither had a gate at the
    package's edge.
    """
    from anvilate.mcp import handle_request
    from test_mcp import _spec_document  # the suite's own valid Design Spec document
    from test_report import _report  # the suite's own worked calculation report

    with _no_network(monkeypatch):
        html = _report().to_html()
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "compile_spec", "arguments": {"document": _spec_document()}},
            }
        )

    assert "<html" in html.lower()
    assert response is not None
    assert response["result"]["isError"] is False, response
    assert response["result"]["structuredContent"]["errors"] == []


def test_the_one_network_capable_path_refuses_before_it_reaches_the_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """`fetch_dataset` without consent never touches the socket layer.

    The ordering is the whole point. If consent were checked after the download — or
    logged and then ignored — the refusal would still be raised and this test would still
    see a `ConsentRequired`, so the block is what separates the two: an implementation
    that fetched first would raise `NetworkAttempted` here instead.
    """
    recipe = DatasetRecipe(
        name="offline-probe.json",
        url="https://example.invalid/offline-probe.json",
        sha256="0" * 64,
        license="CC-BY-4.0",
        source="a recipe that exists to not be fetched",
    )

    with _no_network(monkeypatch), pytest.raises(ConsentRequired):
        fetch_dataset(recipe, retrieved="2026-08-28", consent=False, cache_dir=tmp_path)


def test_consent_opens_the_door_and_the_block_is_what_shuts_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """With consent the default transport really does go out, and nothing else does.

    Stated as a positive, because "no network calls" is only interesting alongside proof
    that a call would have been observed. The same recipe that raised `ConsentRequired`
    above reaches the socket layer the moment a caller says yes.
    """
    recipe = DatasetRecipe(
        name="consented-probe.json",
        url="https://example.invalid/consented-probe.json",
        sha256="0" * 64,
        license="CC-BY-4.0",
        source="a recipe that exists to be refused at the socket",
    )

    with _no_network(monkeypatch), pytest.raises(NetworkAttempted):
        fetch_dataset(recipe, retrieved="2026-08-28", consent=True, cache_dir=tmp_path)

    # And nothing was cached, because nothing arrived.
    assert not (tmp_path / "consented-probe.json").exists()


def test_fetch_is_the_only_module_that_imports_a_network_client() -> None:
    """Derived from the source, so a second door fails here rather than being noticed.

    The tests above run the paths that exist today; this one is about the paths that do
    not. A new module importing `urllib`, `http.client`, `socket` or a third-party client
    is how a local-first tool acquires a phone-home line without anyone deciding to — the
    import is the decision, and it should be visible at the moment it is made.
    """
    clients = {
        # stdlib: everything that can open a socket, not only the ones this package would
        # plausibly reach for. `ssl` and `asyncio` are here because `asyncio.open_connection`
        # is a socket and `ssl` is only ever wrapped around one.
        "socket",
        "urllib",
        "http",
        "ftplib",
        "smtplib",
        "telnetlib",
        "poplib",
        "imaplib",
        "nntplib",
        "xmlrpc",
        "ssl",
        "asyncio",
        "webbrowser",  # not a socket in this process, and it still opens the URL
        # third party. The docstring above said "or a third-party client" while this set
        # named two of them, so `import aiohttp` in any module passed the whole suite.
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "websockets",
        "grpc",
        "paramiko",
        "boto3",
        "botocore",
        "pycurl",
    }
    offenders: dict[str, set[str]] = {}
    package = pathlib.Path(__file__).resolve().parents[1] / "src" / "anvilate"
    for path in sorted(package.rglob("*.py")):
        tree = parsed_source(path)
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {a.name.split(".")[0] for a in node.names} & clients
            elif isinstance(node, ast.ImportFrom) and node.module:
                found |= {node.module.split(".")[0]} & clients
        if found:
            offenders[str(path.relative_to(package))] = found

    assert offenders == {"fetch.py": {"urllib"}}, (
        f"the package's network surface has moved: {offenders}. One module imports a "
        "network client, it is the fetch-on-first-use flow, and the import is inside the "
        "transport function rather than at module scope."
    )

    # SECURITY.md argues from the size of this set, and a number in prose has nothing
    # holding it. The word is the claim a reader acts on, so it is the thing to check.
    spelled = {"twenty-one": 21, "twenty-two": 22, "twenty-three": 23, "twenty-four": 24}
    claim = re.search(
        r"importing any of ([a-z-]+) stdlib or third-party clients fails the build",
        (_REPO / "SECURITY.md").read_text(encoding="utf-8"),
    )
    assert claim is not None, "the network-client row in SECURITY.md has moved"
    assert spelled[claim.group(1)] == len(clients)


def test_the_packages_third_party_imports_are_exactly_its_declared_dependencies() -> None:
    """The allowlist half, and the reason the blocklist above stops being load-bearing.

    A blocklist of client names is a list somebody has to keep up with a world that keeps
    publishing HTTP libraries, and the cost of missing one is silent: `import aiohttp` in
    any module passed all 5,126 tests. This asks the other question — what does the package
    import that Python did not ship? — and the answer has to be the dependencies declared in
    `pyproject.toml`. A network client cannot be added without either being declared, which
    is a diff somebody reads, or failing here.
    """
    project = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = [
        *project["dependencies"],
        *(entry for group in project["optional-dependencies"].values() for entry in group),
    ]
    distributions = {
        re.split(r"[<>=!~\[; ]", entry, maxsplit=1)[0].lower() for entry in requirements
    }
    # A distribution's name is not its import name. Only the runtime ones matter — a dev
    # dependency imported by the package would itself be the finding.
    declared = {_IMPORT_NAME.get(name, name) for name in distributions}
    assert "yaml" in declared, "the pyyaml -> yaml mapping stopped resolving"

    standard = set(sys.stdlib_module_names)
    imported: dict[str, set[str]] = {}
    for path in sorted((_REPO / "src" / "anvilate").rglob("*.py")):
        for node in ast.walk(parsed_source(path)):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = {node.module.split(".")[0]}
            else:
                continue
            for name in names - standard - {"anvilate"}:
                imported.setdefault(name, set()).add(path.name)

    # Attack the gate: a scan that found no third-party imports would pass in silence.
    assert len(imported) >= 4, f"the scan found only {sorted(imported)}"
    assert set(imported) <= declared, (
        "the package imports a distribution pyproject.toml does not declare: "
        + ", ".join(
            f"{name} in {sorted(imported[name])}" for name in sorted(set(imported) - declared)
        )
    )


def test_no_module_is_imported_by_a_name_assembled_at_run_time() -> None:
    """Both sweeps above read `import` statements, and a string is not one.

    `importlib.import_module("urllib.request").urlopen(...)` imports a network client
    without an import node anywhere in the file, and passed both. The one legitimate
    dynamic import in the package walks `anvilate.packs` with a name it computes, so the
    rule is about *literals*: a constant string handed to `import_module` names a module
    somebody chose, and it belongs in an `import` statement where the sweeps can see it.
    """
    literals: list[str] = []
    for path in sorted((_REPO / "src" / "anvilate").rglob("*.py")):
        for node in ast.walk(parsed_source(path)):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = (
                function.attr
                if isinstance(function, ast.Attribute)
                else getattr(function, "id", "")
            )
            if name not in {"import_module", "__import__"}:
                continue
            for argument in node.args[:1]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    literals.append(f"{path.name}: {name}({argument.value!r})")
    assert literals == [], (
        f"a module is imported by a literal string rather than an import statement: "
        f"{literals}. Every import sweep in this suite reads import nodes."
    )
