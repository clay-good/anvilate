"""The analysis-library contract gates (openspec: analysis-library).

Three promises the library makes are enforced here rather than by convention:

- the public surface is explicitly enumerated (``docs/api/analysis-public-surface.txt``),
  so an addition is a deliberate act and a removal has to face the deprecation policy;
- the package aggregate ``__all__`` and the per-module ``__all__`` lists agree, so a
  symbol cannot be public in a module yet silently missing from ``anvilate.analysis``;
- every analysis module is exercised by at least one runnable example under
  ``examples/``, so no module ships as bare API with no demonstrated decision.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import anvilate.analysis as analysis_pkg

_REPO = Path(__file__).resolve().parent.parent
_MANIFEST = _REPO / "docs" / "api" / "analysis-public-surface.txt"
_EXAMPLES = _REPO / "examples"


def _module_names() -> list[str]:
    return sorted(m.name for m in pkgutil.iter_modules(analysis_pkg.__path__))


def _live_surface() -> set[str]:
    """The public surface as ``module.symbol`` lines, from each module's __all__."""
    surface = set()
    for name in _module_names():
        module = importlib.import_module(f"anvilate.analysis.{name}")
        for symbol in module.__all__:
            surface.add(f"{name}.{symbol}")
    return surface


def _manifest_surface() -> set[str]:
    lines = _MANIFEST.read_text().splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def test_every_module_declares_its_public_surface():
    for name in _module_names():
        module = importlib.import_module(f"anvilate.analysis.{name}")
        assert hasattr(module, "__all__"), (
            f"anvilate.analysis.{name} has no __all__; every analysis module must "
            "declare its public surface explicitly"
        )


def test_package_aggregate_matches_module_alls():
    per_module = set()
    for name in _module_names():
        per_module |= set(importlib.import_module(f"anvilate.analysis.{name}").__all__)
    aggregate = set(analysis_pkg.__all__)
    missing = sorted(per_module - aggregate)
    stray = sorted(aggregate - per_module)
    assert not missing, (
        f"public in a module __all__ but not re-exported by anvilate.analysis: {missing}"
    )
    assert not stray, f"in anvilate.analysis.__all__ but no module claims them: {stray}"


def test_every_aggregate_symbol_resolves():
    for symbol in analysis_pkg.__all__:
        assert getattr(analysis_pkg, symbol, None) is not None, (
            f"anvilate.analysis.__all__ names {symbol!r} but it does not resolve"
        )


def test_public_surface_matches_manifest():
    live = _live_surface()
    manifest = _manifest_surface()
    added = sorted(live - manifest)
    removed = sorted(manifest - live)
    message = []
    if added:
        message.append(f"new public symbols not in the manifest (add them deliberately): {added}")
    if removed:
        message.append(
            "symbols in the manifest but gone from the code (removals require a "
            f"deprecation path per the analysis-library spec): {removed}"
        )
    assert not message, (
        "public surface drifted from docs/api/analysis-public-surface.txt\n" + "\n".join(message)
    )


def test_every_module_has_a_runnable_example():
    example_text = "\n".join(p.read_text() for p in _EXAMPLES.glob("*.py"))
    uncovered = []
    for name in _module_names():
        symbols = importlib.import_module(f"anvilate.analysis.{name}").__all__
        pattern = re.compile(r"\b(" + "|".join(map(re.escape, symbols)) + r")\b")
        if not pattern.search(example_text):
            uncovered.append(name)
    assert not uncovered, f"analysis modules with no runnable example under examples/: {uncovered}"


def test_every_public_callable_has_a_docstring():
    for symbol in analysis_pkg.__all__:
        obj = getattr(analysis_pkg, symbol)
        if callable(obj):
            assert obj.__doc__, f"public callable anvilate.analysis.{symbol} has no docstring"
