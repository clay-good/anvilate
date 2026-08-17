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
import types
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


def test_no_exported_symbol_shadows_its_own_module():
    # The package re-exports every module's symbols into one flat namespace, so a function
    # whose name equals a module stem rebinds the package attribute over the submodule:
    # ``import anvilate.analysis.radiation_pressure as m`` then binds the *function*, and
    # ``m.photon_momentum`` raises AttributeError. The manifest and __all__ gates above cannot
    # see this, because both sides of the comparison agree -- only the attribute type differs.
    modules = set(_module_names())
    shadowed = sorted(modules & set(analysis_pkg.__all__))
    assert not shadowed, (
        "exported symbols that collide with an analysis module name, making "
        f"``import anvilate.analysis.<name> as m`` return the function instead: {shadowed}"
    )
    # And prove the property directly rather than only by name comparison.
    for name in _module_names():
        attribute = getattr(analysis_pkg, name)
        assert isinstance(attribute, types.ModuleType), (
            f"anvilate.analysis.{name} resolves to {attribute!r}, not the submodule"
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


def _citation_authorities() -> list[str]:
    path = _REPO / "docs" / "api" / "citation-authorities.txt"
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _uncited_manifest() -> set[str]:
    path = _REPO / "docs" / "api" / "uncited-symbols.txt"
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _uncited_symbols() -> set[str]:
    """Public analysis symbols naming no source, in their own docstring or their module's."""
    import importlib
    import inspect

    authorities = _citation_authorities()

    def cited(text: str) -> bool:
        return any(token in text for token in authorities)

    missing: set[str] = set()
    for entry in _manifest_surface():
        module_name, _, symbol = entry.partition(".")
        try:
            module = importlib.import_module(f"anvilate.analysis.{module_name}")
            obj = getattr(module, symbol)
        except (ImportError, AttributeError):  # pragma: no cover - the surface gate catches this
            continue
        if not (cited(inspect.getdoc(obj) or "") or cited(inspect.getdoc(module) or "")):
            missing.add(entry)
    return missing


def test_every_new_public_check_names_its_source():
    """The citation gate, held as a ratchet: the debt can only go down.

    "Every check cites its clause" is the library's contract, and a little over a third
    of the public surface does not yet keep it. Backfilling all of it at once would mean
    attaching sources to formulas nobody re-read, which is worse than an honest gap. So
    the outstanding symbols are enumerated in ``docs/api/uncited-symbols.txt`` and this
    test holds the line in both directions: a NEW public symbol must name a source, and a
    listed symbol that has since been cited must be struck off. Neither the list nor the
    silence can drift.
    """
    uncited = _uncited_symbols()
    recorded = _uncited_manifest()

    newly_uncited = sorted(uncited - recorded)
    assert not newly_uncited, (
        "public analysis symbols that name no source and are not recorded as known debt.\n"
        "Name the source in the docstring (or the module's, if the whole module follows "
        "one text) using a token from docs/api/citation-authorities.txt — do NOT add the "
        "symbol to docs/api/uncited-symbols.txt:\n  " + "\n  ".join(newly_uncited)
    )

    now_cited = sorted(recorded - uncited)
    assert not now_cited, (
        "these symbols are recorded as uncited but now name a source. Strike them from "
        "docs/api/uncited-symbols.txt so the debt stays honest:\n  " + "\n  ".join(now_cited)
    )


def test_the_citation_gate_can_actually_detect_a_missing_source():
    """A gate nobody has watched fail is a gate nobody knows works."""
    authorities = _citation_authorities()

    def cited(text: str) -> bool:
        return any(token in text for token in authorities)

    assert cited("The AISC 360-22 §F2 flexural strength.")
    assert cited("Roark's Formulas for Stress and Strain, Table 8.1.")
    assert cited("The Terzaghi bearing capacity.")
    # A docstring that explains the physics beautifully and never says where it came
    # from is exactly what this gate is for.
    assert not cited(
        "The stress in a member, which is the load over the area — a relation so "
        "familiar that nobody writes down where it comes from."
    )
    assert not cited("")


_INVERSE_NAME = re.compile(
    r"(^)(required_|minimum_|min_|max_|size_)|_for_|_from_|_needed|_to_reach"
)


def _inverse_inventory() -> tuple[dict[str, str], set[str]]:
    """The recorded (inverse -> forward) pairs, and the symbols recorded as unpaired."""
    path = _REPO / "docs" / "api" / "design-inverses.txt"
    paired: dict[str, str] = {}
    unpaired: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " -> " in line:
            inverse, forward = line.split(" -> ", 1)
            paired[inverse.strip()] = forward.strip()
        else:
            unpaired.add(line)
    return paired, unpaired


def test_every_inverse_shaped_symbol_has_a_recorded_pairing_decision():
    """A design inverse must not ship without a decision about what it inverts.

    The contract is that an inverse lands its forward check at exactly the required
    margin — an overshoot is a silent cost, an undershoot a silent failure. The pairs are
    hand-verified because automatic pairing resolved only 14 of 156 candidates here, and
    a wrong pairing tested automatically would be worse than no test. So the inventory is
    a declaration, and this gate only insists that the declaration is complete: every
    inverse-shaped public symbol is either paired and round-tripped, or recorded as not
    yet paired.
    """
    paired, unpaired = _inverse_inventory()
    recorded = set(paired) | unpaired
    candidates = {
        entry for entry in _manifest_surface() if _INVERSE_NAME.search(entry.split(".", 1)[1])
    }

    unrecorded = sorted(candidates - recorded)
    assert not unrecorded, (
        "inverse-shaped public symbols with no entry in docs/api/design-inverses.txt. "
        "Add each one: '<inverse> -> <forward>' with a round-trip test in "
        "tests/test_design_inverses.py, or the bare name if it is a conversion rather "
        "than a design inverse:\n  " + "\n  ".join(unrecorded)
    )

    # The name pattern is a discovery heuristic, not the definition: a pair recorded
    # deliberately may not look inverse-shaped (asme_b313_pipe_wall_thickness is the
    # rating inverse of asme_b313_pipe_pressure and matches nothing). So staleness is
    # checked against the public surface, not against the heuristic.
    stale = sorted(recorded - _manifest_surface())
    assert not stale, (
        "docs/api/design-inverses.txt names symbols that are no longer on the public "
        "surface:\n  " + "\n  ".join(stale)
    )


def test_every_recorded_inverse_pairing_resolves_and_is_round_tripped():
    paired, _ = _inverse_inventory()
    surface = _manifest_surface()
    for inverse, forward in sorted(paired.items()):
        assert inverse in surface, f"{inverse} is paired but is not on the public surface"
        assert forward in surface, f"{inverse} is paired to {forward}, which is not public"

    # Every paired inverse must actually be exercised by the round-trip suite, or the
    # pairing is a claim nobody checks.
    round_trips = (_TESTS / "test_design_inverses.py").read_text(encoding="utf-8")
    untested = sorted(inverse for inverse in paired if inverse.split(".", 1)[1] not in round_trips)
    assert not untested, (
        "these inverses are recorded as paired but no round-trip test names them:\n  "
        + "\n  ".join(untested)
    )
