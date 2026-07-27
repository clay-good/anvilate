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


# -- derivation coverage ---------------------------------------------------
#
# The calculation-report spec requires a check to declare the work behind its
# verdict. Coverage is being backfilled pack by pack, so the gate below pins the
# checks that already declare a derivation: adding one is free, and dropping one
# fails the build. The pending list is the remaining work, named rather than
# silently absent.

_CHECKS_WITH_DERIVATIONS = {
    "bolt shear",
    "bolt tension",
    "buckling",
    "combined tension+shear",
    "concrete bearing",
    "edge tear-out",
    "gross yielding",
    "net rupture",
    "net tension",
    "pin bearing",
    "plate bearing",
    "weld shear",
}


def _structural_entries():
    """One scorecard entry per structural-pack check, from a screened assembly."""
    from anvilate.analysis import CrossSection
    from anvilate.packs.structural import (
        BoltedConnection,
        ColumnMember,
        ConcreteBearing,
        LiftingLug,
        TensionMember,
        WeldedConnection,
        screen_bolted_connection,
        screen_column_member,
        screen_concrete_bearing,
        screen_lifting_lug,
        screen_tension_member,
        screen_welded_connection,
    )
    from anvilate.units import Quantity

    section = CrossSection.rectangular(
        width=Quantity.parse("50 mm"), height=Quantity.parse("50 mm")
    )
    entries = []
    entries.extend(
        screen_lifting_lug(
            LiftingLug(
                name="lug",
                width=Quantity.parse("80 mm"),
                hole_diameter=Quantity.parse("25 mm"),
                thickness=Quantity.parse("12 mm"),
                load=Quantity.parse("50 kN"),
                material="ASTM-A36",
            ),
            required_safety_factor=2.0,
        ).entries
    )
    entries.extend(
        screen_column_member(
            ColumnMember(
                name="post",
                section=section,
                length=Quantity.parse("3000 mm"),
                axial_load=Quantity.parse("40 kN"),
                material="ASTM-A36",
            ),
            required_safety_factor=2.0,
        ).entries
    )
    entries.extend(
        screen_concrete_bearing(
            ConcreteBearing(
                name="pedestal",
                bearing_area=Quantity.parse("40000 mm^2"),
                support_area=Quantity.parse("250000 mm^2"),
                concrete_strength=Quantity.parse("28 MPa"),
                load=Quantity.parse("600 kN"),
            ),
            required_safety_factor=2.0,
        ).entries
    )
    entries.extend(
        screen_bolted_connection(
            BoltedConnection(
                name="clevis",
                bolt_diameter=Quantity.parse("16 mm"),
                shear_planes=2,
                plate_thickness=Quantity.parse("10 mm"),
                load=Quantity.parse("60 kN"),
                edge_distance=Quantity.parse("30 mm"),
                tension=Quantity.parse("25 kN"),
                bolt_material="ASTM-A36",
                plate_material="ASTM-A36",
            ),
            required_safety_factor=1.5,
        ).entries
    )
    entries.extend(
        screen_welded_connection(
            WeldedConnection(
                name="seam",
                leg_size=Quantity.parse("8 mm"),
                weld_length=Quantity.parse("160 mm"),
                load=Quantity.parse("50 kN"),
                electrode_strength=Quantity.parse("483 MPa"),
            ),
            required_safety_factor=2.0,
        ).entries
    )
    entries.extend(
        screen_tension_member(
            TensionMember(
                name="tie",
                gross_area=Quantity.parse("1200 mm^2"),
                net_area=Quantity.parse("1000 mm^2"),
                shear_lag_factor=0.85,
                load=Quantity.parse("200 kN"),
                material="ASTM-A36",
            ),
            required_safety_factor=1.5,
        ).entries
    )
    return entries


def test_checks_that_declare_a_derivation_keep_declaring_one():
    missing = [
        entry.name
        for entry in _structural_entries()
        if entry.derivation is None
        and any(check in entry.name for check in _CHECKS_WITH_DERIVATIONS)
    ]
    assert not missing, (
        f"these checks used to carry a worked derivation and no longer do: {missing}"
    )


def test_declared_derivations_are_fully_substitutable():
    # A derivation whose formula names a symbol it never declares would render a
    # bare symbol where a value belongs, so the report would refuse to show it as
    # worked. Catch that here rather than in a silently-degraded report.
    for entry in _structural_entries():
        if entry.derivation is None:
            continue
        assert entry.derivation.unresolved_symbols() == (), (
            f"{entry.name} declares a formula using symbols it never supplies: "
            f"{entry.derivation.unresolved_symbols()}"
        )


def test_declared_derivations_cite_their_source():
    for entry in _structural_entries():
        if entry.derivation is not None:
            assert entry.derivation.citation, f"{entry.name} has a derivation with no citation"
