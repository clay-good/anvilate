"""The analysis-library contract gates (openspec: analysis-library).

Four promises the library makes are enforced here rather than by convention:

- the public surface is explicitly enumerated (``docs/api/analysis-public-surface.txt``),
  so an addition is a deliberate act and a removal has to face the deprecation policy;
- every analysis module is listed in the package docstring's module index, so a module
  cannot ship without appearing in the API docs;
- the package aggregate ``__all__`` and the per-module ``__all__`` lists agree, so a
  symbol cannot be public in a module yet silently missing from ``anvilate.analysis``;
- every analysis module is exercised by at least one runnable example under
  ``examples/``, so no module ships as bare API with no demonstrated decision.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import anvilate.analysis as analysis_pkg

_REPO = Path(__file__).resolve().parent.parent
_MANIFEST = _REPO / "docs" / "api" / "analysis-public-surface.txt"
_EXAMPLES = _REPO / "examples"
_TESTS = Path(__file__).resolve().parent


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


def test_every_module_is_listed_in_the_package_docstring():
    # The package docstring is the library's table of contents: one ``- :mod:`` bullet
    # per analysis module. A module that ships without its bullet is invisible to
    # anyone reading the API docs, and the manifest gate above cannot see the omission
    # because it only compares symbols.
    listed = set(
        re.findall(r"^- :mod:`~anvilate\.analysis\.(\w+)`", analysis_pkg.__doc__ or "", re.M)
    )
    modules = set(_module_names())
    unlisted = sorted(modules - listed)
    stale = sorted(listed - modules)
    assert not unlisted, (
        "analysis modules with no ``- :mod:`` bullet in the anvilate.analysis package "
        f"docstring: {unlisted}"
    )
    assert not stale, (
        f"the anvilate.analysis package docstring lists modules that no longer exist: {stale}"
    )


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
    "bending",
    "block shear",
    "bolt shear",
    "bolt tension",
    "buckling",
    "combined tension+shear",
    "concrete bearing",
    "edge tear-out",
    "gross yielding",
    "net rupture",
    "interaction",
    "net tension",
    "pin bearing",
    "plate bearing",
    "plate bending",
    "joist shear",
    "shear rupture",
    "shear yielding",
    "weld shear",
}


def _structural_entries():
    """One scorecard entry per structural-pack check, from a screened assembly."""
    from anvilate.analysis import CrossSection
    from anvilate.packs.structural import (
        BasePlate,
        BeamColumnMember,
        BeamMember,
        BoltedConnection,
        ColumnMember,
        ConcreteBearing,
        GussetPlate,
        LiftingLug,
        LoadType,
        ShearPlate,
        Support,
        TensionMember,
        WeldedConnection,
        screen_base_plate,
        screen_beam_column,
        screen_beam_member,
        screen_bolted_connection,
        screen_column_member,
        screen_concrete_bearing,
        screen_gusset_plate,
        screen_lifting_lug,
        screen_shear_plate,
        screen_tension_member,
        screen_welded_connection,
    )
    from anvilate.units import Quantity

    section = CrossSection.rectangular(
        width=Quantity.parse("50 mm"), height=Quantity.parse("50 mm")
    )
    entries = []
    entries.extend(
        screen_beam_member(
            BeamMember(
                name="joist",
                section=CrossSection.rectangular(
                    width=Quantity.parse("100 mm"), height=Quantity.parse("150 mm")
                ),
                length=Quantity.parse("4 m"),
                support=Support.SIMPLY_SUPPORTED,
                load_type=LoadType.DISTRIBUTED,
                load=Quantity.parse("5 kN/m"),
                material="ASTM-A36",
            ),
            required_safety_factor=1.5,
        ).entries
    )
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
    entries.extend(
        screen_base_plate(
            BasePlate(
                name="bp",
                width=Quantity.parse("300 mm"),
                depth=Quantity.parse("300 mm"),
                axial_load=Quantity.parse("500 kN"),
                concrete_strength=Quantity.parse("25 MPa"),
                plate_thickness=Quantity.parse("25 mm"),
                cantilever=Quantity.parse("75 mm"),
                plate_material="ASTM-A36",
            ),
            required_safety_factor=1.5,
        ).entries
    )
    entries.extend(
        screen_gusset_plate(
            GussetPlate(
                name="gusset",
                net_shear_area=Quantity.parse("3000 mm^2"),
                net_tension_area=Quantity.parse("1200 mm^2"),
                load=Quantity.parse("400 kN"),
                material="ASTM-A36",
            ),
            required_safety_factor=2.0,
        ).entries
    )
    entries.extend(
        screen_shear_plate(
            ShearPlate(
                name="tab",
                gross_shear_area=Quantity.parse("2400 mm^2"),
                net_shear_area=Quantity.parse("1800 mm^2"),
                load=Quantity.parse("250 kN"),
                material="ASTM-A36",
            ),
            required_safety_factor=1.5,
        ).entries
    )
    entries.extend(
        screen_beam_column(
            BeamColumnMember(
                name="bc",
                section=section,
                length=Quantity.parse("3 m"),
                axial_load=Quantity.parse("300 kN"),
                moment=Quantity.parse("20 kN*m"),
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


def test_no_assertion_is_disarmed_by_the_approx_absolute_floor():
    # pytest.approx applies a DEFAULT abs=1e-12 alongside whatever rel= is written, and
    # takes whichever tolerance is looser. On a sub-nanoscale quantity that floor is
    # enormous relative to the value itself — for a 1.67e-27 kg proton mass it is 1e15
    # times the number — so the rel= is silently disarmed and the assertion degenerates
    # to "the answer is small". That is a silent green of exactly the kind this library
    # exists to refuse: a formula wrong by orders of magnitude still passes.
    #
    # Fix such a site by asserting in a scaled unit (pm, ps, pW, u) so the magnitude is
    # order-one, or by passing an explicit abs= sized to the value. Comparisons against
    # a literal zero are exempt: there the absolute floor is the whole point.
    offenders = []
    for path in sorted(_TESTS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != "approx" or not node.args:
                continue
            if any(keyword.arg == "abs" for keyword in node.keywords):
                continue
            try:
                expected = ast.literal_eval(node.args[0])
            except ValueError:
                continue
            if isinstance(expected, (int, float)) and 0 < abs(expected) < 1e-9:
                offenders.append(f"{path.name}:{node.lineno} approx({expected!r}) with no abs=")
    assert not offenders, (
        "these assertions are swamped by pytest.approx's default abs=1e-12, so their rel= "
        f"tolerance does nothing; assert in a scaled unit or pass an explicit abs=: {offenders}"
    )
