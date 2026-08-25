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
import inspect
import math
import pkgutil
import re
import types
from pathlib import Path

import pytest

import anvilate as anvilate_pkg
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


# --- The same contract, for the cross-cutting layers ----------------------------------
#
# Every gate above scopes to ``anvilate.analysis``. That was right when the analysis
# library was the whole shipped surface, and it stopped being right as the cross-cutting
# layers grew: fifteen top-level modules now export 134 public symbols under no contract at
# all. The practice had held anyway — all ten already declared ``__all__`` and documented
# every callable — but nothing was enforcing it, and an unenforced convention is one
# careless commit from being a former convention.

_CORE_MANIFEST = _REPO / "docs" / "api" / "core-public-surface.txt"


def _core_module_names() -> list[str]:
    """The top-level, non-package modules of ``anvilate`` — the cross-cutting layers."""
    return sorted(m.name for m in pkgutil.iter_modules(anvilate_pkg.__path__) if not m.ispkg)


def _core_live_surface() -> set[str]:
    surface = set()
    for name in _core_module_names():
        module = importlib.import_module(f"anvilate.{name}")
        for symbol in module.__all__:
            surface.add(f"{name}.{symbol}")
    return surface


def test_every_core_module_declares_its_public_surface():
    for name in _core_module_names():
        module = importlib.import_module(f"anvilate.{name}")
        assert hasattr(module, "__all__"), (
            f"anvilate.{name} has no __all__; every shipped module must declare its "
            "public surface explicitly, not leave it to whatever happens to be importable"
        )


def test_the_core_public_surface_matches_its_manifest():
    """Growing the top-level public surface is a deliberate act with a diff."""
    live = _core_live_surface()
    recorded = {
        line.strip()
        for line in _CORE_MANIFEST.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    added = sorted(live - recorded)
    removed = sorted(recorded - live)
    assert not added, (
        "public symbols in a top-level module's __all__ with no line in "
        f"docs/api/core-public-surface.txt: {added}"
    )
    assert not removed, (
        f"docs/api/core-public-surface.txt names symbols that no longer exist: {removed}"
    )


def test_every_core_module_is_listed_in_the_package_docstring():
    """The package docstring is the library's table of contents, and it was half a list.

    Four modules shipped in one session without a bullet between them. The manifest gate
    cannot see that omission — it compares symbols, and a module absent from the docstring
    still exports its symbols correctly. This is the gate that sees it.
    """
    listed = set(re.findall(r"^- :mod:`anvilate\.(\w+)`", anvilate_pkg.__doc__ or "", re.M))
    modules = set(_core_module_names())
    unlisted = sorted(modules - listed)
    assert not unlisted, (
        "top-level modules with no ``- :mod:`` bullet in the anvilate package docstring: "
        f"{unlisted}"
    )


def test_every_public_core_callable_has_a_docstring():
    undocumented = []
    for name in _core_module_names():
        module = importlib.import_module(f"anvilate.{name}")
        for symbol in module.__all__:
            obj = getattr(module, symbol)
            if not (inspect.isfunction(obj) or inspect.isclass(obj)):
                continue
            if not (obj.__doc__ or "").strip():
                undocumented.append(f"{name}.{symbol}")
    assert not undocumented, (
        f"public callables in the cross-cutting layers with no docstring: {undocumented}"
    )


def test_the_core_surface_gates_can_actually_detect_what_they_claim_to():
    """Prove the gates fail on a violation, rather than trusting that they would.

    A manifest gate that compares two sets built from the same source passes forever.
    These build the live side from the imported modules and the recorded side from the
    file on disk, so the comparison is real — and this asserts that by perturbing each
    side in turn.
    """
    live = _core_live_surface()
    assert live, "the live core surface came back empty, so every comparison is vacuous"
    recorded = {
        line.strip()
        for line in _CORE_MANIFEST.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    # An added symbol and a removed one are each visible from exactly one side.
    assert sorted((live | {"explore.brand_new_symbol"}) - recorded) == ["explore.brand_new_symbol"]
    assert sorted((recorded | {"explore.deleted_symbol"}) - live) == ["explore.deleted_symbol"]
    # And the docstring gate reads a real table of contents, not an empty string.
    listed = set(re.findall(r"^- :mod:`anvilate\.(\w+)`", anvilate_pkg.__doc__ or "", re.M))
    assert "explore" in listed and "verification" in listed
    assert "not_a_module" not in listed


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


def _fold(node: ast.AST, constants: dict[str, object]) -> object | None:
    """The numeric value of an expected-value expression, or None if it is not one.

    ``ast.literal_eval`` raises on anything that is not a bare literal, and the gate used
    to swallow that and move on — so every expression-valued expectation was invisible.
    This folds the arithmetic a test actually writes (a product, a power, a negation) and
    resolves module-level constants defined in the same file.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, (int, float)) else None
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _fold(node.operand, constants)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        left, right = _fold(node.left, constants), _fold(node.right, constants)
        if left is None or right is None:
            return None
        try:
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
        except (ArithmeticError, TypeError, ValueError):  # pragma: no cover - not an expectation
            return None
    return None


def _disarmed_approx_sites(root: Path | None = None) -> list[str]:
    """Every pytest.approx call whose rel= is swamped by the default abs=1e-12 floor."""
    offenders: list[str] = []
    base = _TESTS if root is None else root
    for path in sorted(base.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    value = _fold(node.value, {})
                    if value is not None:
                        constants[target.id] = value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != "approx":
                continue
            if any(keyword.arg == "abs" for keyword in node.keywords):
                continue
            # The keyword form has no positional args at all, so requiring one skipped it.
            expected_node = (
                node.args[0]
                if node.args
                else next((kw.value for kw in node.keywords if kw.arg == "expected"), None)
            )
            if expected_node is None:
                continue
            expected = _fold(expected_node, constants)
            if isinstance(expected, (int, float)) and 0 < abs(expected) < 1e-9:
                offenders.append(f"{path.name}:{node.lineno} approx({expected!r}) with no abs=")
    return offenders


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
    offenders = sorted(_disarmed_approx_sites())
    assert not offenders, (
        "these assertions are swamped by pytest.approx's default abs=1e-12, so their rel= "
        f"tolerance does nothing; assert in a scaled unit or pass an explicit abs=: {offenders}"
    )


def test_the_approx_gate_sees_the_forms_it_used_to_walk_past(tmp_path):
    """The reader has to read what is written, not only what is spelled as a bare literal.

    The gate resolved its expected value with ``ast.literal_eval`` and skipped anything
    that raised — which is *every* expression. ``approx(1.67 * 1e-27)``, ``approx(10**-27)``
    and ``approx(PROTON_MASS)`` all slipped through, as did the ``approx(expected=...)``
    keyword form (no positional args at all) and every file in a ``tests/`` subdirectory.
    An audit instrumented pytest.approx over the whole suite and found 38 live disarmed
    sites, none of them visible to this gate, because each was written as an expression.

    So the gate now folds constant arithmetic, resolves module-level constants in the same
    file, and reads the keyword form. This test is the proof: each form below must be
    caught, and the order-one control must not be.
    """
    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "PROTON_MASS = 1.6726e-27\n"
        "def test_a():\n"
        "    assert x == pytest.approx(1.67e-27)\n"  # bare literal, caught before
        "    assert x == pytest.approx(1.67 * 1e-27)\n"  # folded product
        "    assert x == pytest.approx(10**-27)\n"  # folded power
        "    assert x == pytest.approx(-1.67e-27)\n"  # folded unary minus
        "    assert x == pytest.approx(PROTON_MASS)\n"  # module-level constant
        "    assert x == pytest.approx(expected=1.67e-27)\n"  # keyword form
        "    assert x == pytest.approx(1.67e-27, abs=1e-30)\n"  # armed: not an offender
        "    assert x == pytest.approx(9.81)\n"  # order-one: not an offender
        "    assert x == pytest.approx(0.0)\n"  # zero is exempt by design
    )
    caught = sorted(_disarmed_approx_sites(root=tmp_path))
    assert len(caught) == 6, caught
    for line in (3, 4, 5, 6, 7, 8):
        assert any(f":{line} " in site for site in caught), (line, caught)
    for line in (9, 10, 11):
        assert not any(f":{line} " in site for site in caught), (line, caught)

    # And a subdirectory is not a hiding place.
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "test_deep.py").write_text("def test_b():\n    assert x == pytest.approx(1.67e-27)\n")
    assert any("test_deep.py" in site for site in _disarmed_approx_sites(root=tmp_path))


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
        own = inspect.getdoc(obj) or ""
        if cited(own):
            continue
        # A module-level `Sources:` line covers the symbols that were in the module when
        # it was written, and those are enumerated. It must NOT silently cover a symbol
        # added later — otherwise a new check ships uncited into any backfilled module,
        # which is the opposite of what this gate is for.
        if cited(inspect.getdoc(module) or "") and entry in _module_cited_manifest():
            continue
        missing.add(entry)
    return missing


def _module_cited_manifest() -> set[str]:
    """Symbols whose only citation is their module's docstring — the recorded baseline."""
    path = _REPO / "docs" / "api" / "module-cited-symbols.txt"
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


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

    # The pattern itself has to keep working. Narrowing it — dropping `required_`, say —
    # shrinks the candidate set to a subset of what is already recorded, so
    # `candidates - recorded` stays empty and the gate goes green while silently ceasing
    # to notice every future `required_*` inverse. A mutation pass walked straight
    # through that, so each alternative is asserted to still match something recorded.
    for fragment, example in (
        ("required_", "section.required_section_modulus"),
        ("_for_", "torsion.shaft_diameter_for_torque"),
        ("_from_", "dynamics.natural_frequency_from_deflection"),
        ("minimum_", "wire_rope.minimum_sheave_diameter_for_bending_stress"),
    ):
        assert example in recorded, f"the inventory lost its {fragment!r} exemplar"
        assert _INVERSE_NAME.search(example.split(".", 1)[1]), (
            f"_INVERSE_NAME no longer matches {example!r}, so the gate has stopped "
            f"discovering {fragment!r} inverses entirely"
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
    # pairing is a claim nobody checks. This reads that suite's own DECLARATION rather
    # than grepping its text: the text search was satisfied by a comment, and an audit
    # slipped a nonsense pairing past it with a single "# TODO: round-trip ... someday".
    import test_design_inverses

    untested = sorted(set(paired) - test_design_inverses.ROUND_TRIPPED)
    assert not untested, (
        "these inverses are recorded as paired but no round-trip test names them:\n  "
        + "\n  ".join(untested)
    )

    # ...and the DECLARATION itself has to correspond to tests that exist and exercise
    # the recorded PAIR. Two holes were walked through before this existed: a brand-new
    # public inverse with no round-trip test at all passed every gate on one line in
    # design-inverses.txt plus one string in ROUND_TRIPPED; and rewriting a pairing to an
    # unrelated forward (`required_section_modulus -> fin_array_count_for_resistance`)
    # stayed green, because the round-trip tests hardcode their own pairs and never read
    # the file the gate is checking. So this reads the suite's actual test bodies and
    # requires some single test to name BOTH halves of each recorded pair.
    import ast

    tree = ast.parse((_REPO / "tests" / "test_design_inverses.py").read_text(encoding="utf-8"))
    per_test: list[set[str]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            names = {
                child.id if isinstance(child, ast.Name) else child.attr
                for child in ast.walk(node)
                if isinstance(child, (ast.Name, ast.Attribute))
            }
            per_test.append(names)

    unexercised: list[str] = []
    for inverse, forward in sorted(paired.items()):
        if inverse not in test_design_inverses.ROUND_TRIPPED:
            continue
        inverse_symbol = inverse.split(".", 1)[1]
        forward_symbol = forward.split(".", 1)[1]
        if not any(inverse_symbol in names and forward_symbol in names for names in per_test):
            unexercised.append(f"{inverse} -> {forward}")
    assert not unexercised, (
        "these pairings are declared in ROUND_TRIPPED but no single test in "
        "tests/test_design_inverses.py calls both halves, so the pairing recorded in "
        "docs/api/design-inverses.txt is a claim nobody checks:\n  " + "\n  ".join(unexercised)
    )
    # And the reader itself has to keep reading: if the AST walk stopped finding tests,
    # every pairing above would pass vacuously.
    assert len(per_test) >= 12, (
        f"only {len(per_test)} round-trip tests were discovered — the reader has stopped "
        f"reading, and the pairing check above is passing on an empty set"
    )


_UNIT_TOKEN = r"[A-Za-z\u00b5\u03a9%][A-Za-z0-9_]*(?:\*\*\d+)?"
# A compound unit is one token, not the first of several: "20.83 kN*m" and "5.2 kg/m**3"
# have to be captured whole, or the tail migrates out of the parentheses and lands in
# whatever operator follows.
_VALUE_UNIT = re.compile(
    r"(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+(" + _UNIT_TOKEN + r"(?:\s*[*/]\s*" + _UNIT_TOKEN + r")*)"
)


def _sample_derivations() -> list[tuple[str, object]]:
    """Derivations built by the packs, harvested from a representative set of screens."""
    from anvilate.analysis import CrossSection
    from anvilate.packs import industrial, structural
    from anvilate.units import Quantity

    def q(text: str) -> Quantity:
        return Quantity.parse(text)

    out: list[tuple[str, object]] = []
    section = CrossSection.rectangular(width=q("50 mm"), height=q("100 mm"))
    for support in structural.Support:
        for load_type in (structural.LoadType.POINT, structural.LoadType.DISTRIBUTED):
            kwargs = {}
            if support is structural.Support.OVERHANG:
                kwargs["overhang_length"] = q("0.5 m")
            member = structural.BeamMember(
                name="b",
                section=section,
                length=q("3 m"),
                support=support,
                load=q("6 kN") if load_type is structural.LoadType.POINT else q("2 N/mm"),
                load_type=load_type,
                material="ASTM-A36",
                **kwargs,
            )
            for entry in structural.screen_beam_member(member, required_safety_factor=1.5).entries:
                if entry.derivation is not None:
                    out.append(
                        (f"{support.value}/{load_type.value} {entry.name}", entry.derivation)
                    )
    lug = structural.LiftingLug(
        name="lug",
        width=q("80 mm"),
        hole_diameter=q("25 mm"),
        thickness=q("12 mm"),
        load=q("50 kN"),
        material="ASTM-A36",
    )
    for entry in structural.screen_lifting_lug(lug, required_safety_factor=2.0).entries:
        if entry.derivation is not None:
            out.append((f"lug {entry.name}", entry.derivation))
    cover = industrial.CoverPlate(
        name="c",
        pressure=q("400 kPa"),
        thickness=q("12 mm"),
        material="ASTM-A36",
        diameter=q("500 mm"),
    )
    for entry in industrial.screen_cover_plate(cover, required_safety_factor=1.5).entries:
        if entry.derivation is not None:
            out.append((f"cover {entry.name}", entry.derivation))
    # Every structural screen, not a hand-picked few. The sample used to be three
    # screens, and the one defect this gate has ever missed — a substituted line 25%
    # high whenever the ACI §22.8.3 confinement cap bound — was in a screen the sample
    # did not reach. A render-truth gate is only as wide as what it renders.
    for entry in _structural_entries():
        if entry.derivation is not None:
            out.append((f"structural {entry.name}", entry.derivation))
    # Both sides of every branch that changes the formula. A capped confinement factor
    # evaluates a DIFFERENT expression from an uncapped one, so rendering only the
    # uncapped case leaves the capped one unwatched. The same goes for the two AISC E3
    # branches, whose formulas share no term at all.
    for label, length in (("slender", "3 m"), ("stocky", "500 mm")):
        column = structural.ColumnMember(
            name="post",
            section=section,
            length=q(length),
            axial_load=q("40 kN"),
            material="ASTM-A36",
        )
        for entry in structural.screen_column_member(column, required_safety_factor=2.0).entries:
            if entry.derivation is not None:
                out.append((f"column {label} {entry.name}", entry.derivation))
    for label, support_area in (("capped", "250000 mm**2"), ("uncapped", "90000 mm**2")):
        bearing = structural.ConcreteBearing(
            name="pedestal",
            bearing_area=q("40000 mm**2"),
            support_area=q(support_area),
            concrete_strength=q("28 MPa"),
            load=q("500 kN"),
        )
        for entry in structural.screen_concrete_bearing(
            bearing, required_safety_factor=1.5
        ).entries:
            if entry.derivation is not None:
                out.append((f"bearing {label} {entry.name}", entry.derivation))
    return out


def _expand_roots(expression: str) -> str:
    """Rewrite every \u221a(...) in a substituted line as (...)**0.5, matching parentheses.

    Without this, pint parses "\u221a(A\u2082/A\u2081)" by quietly discarding the radical and using
    the ratio itself — so a line with a square root in it evaluated to the wrong number
    and the gate compared that wrong number against the printed result. It happened to
    agree often enough to look fine, which is the worst way for a checker to be broken.
    """
    while (start := expression.find("\u221a(")) != -1:
        depth = 0
        for i in range(start + 1, len(expression)):
            if expression[i] == "(":
                depth += 1
            elif expression[i] == ")":
                depth -= 1
                if depth == 0:
                    inner = expression[start + 2 : i]
                    expression = f"{expression[:start]}(({inner})**0.5){expression[i + 1 :]}"
                    break
        else:  # pragma: no cover - an unbalanced radical is not a derivation we build
            return expression.replace("\u221a", "", 1)
    return expression


def test_the_render_truth_gate_can_actually_see_a_square_root():
    """The checker has to evaluate what the line says, radicals included.

    This is the gate-mechanism half of the render-truth check, and it is here because
    the mechanism was broken: pint dropped the radical, so \u221a(4) evaluated as 4. Any
    formula with a square root in it was being compared against a number the line does
    not say, and the ACI confined-bearing derivation hid a 25% mismatch behind it.
    """
    assert _expand_roots("0.85 * (28 MPa) * \u221a((250000 mm**2)/(40000 mm**2))") == (
        "0.85 * (28 MPa) * (((250000 mm**2)/(40000 mm**2))**0.5)"
    )
    assert _expand_roots("a * b") == "a * b"

    from anvilate.units.registry import UREG

    plain = UREG.parse_expression("\u221a((250000 mm**2)/(40000 mm**2))")
    expanded = UREG.parse_expression(_expand_roots("\u221a((250000 mm**2)/(40000 mm**2))"))
    # 6.25 before, 2.5 after: the radical was being thrown away.
    assert math.isclose(float(plain), 6.25)
    assert math.isclose(float(expanded), 2.5)


def test_every_derivation_the_library_builds_evaluates_to_its_own_result():
    """A substituted line must multiply out to the result printed under it.

    The calculation report tells a reviewer to check the arithmetic by hand, and
    docs/citations.md tells them a mismatch is a bug worth reporting. Until this test
    existed the only assertion of that property was a hardcoded literal for one SI
    fixture, so the claim was a claim. This walks every derivation the packs actually
    build, in BOTH unit systems, and evaluates the substituted line with pint.

    It was written because an audit found eighteen live mismatches, up to 13% off:
    `decimals_for` fixed the printed precision per dimension rather than per value, so a
    working stress of 0.087 ksi printed as "0.1 ksi" and the error landed in the very
    line a reviewer is told to check.
    """
    from anvilate.units import UnitSystem
    from anvilate.units.registry import UREG

    derivations = _sample_derivations()
    assert len(derivations) >= 10, "the sample got too small to be meaningful"

    number = re.compile(r"(-?\d+\.?\d*(?:[eE][-+]?\d+)?)")
    checked = 0
    mismatches: list[str] = []
    unparsed: list[str] = []
    for label, derivation in derivations:
        if derivation.unresolved_symbols():
            continue
        for system in (UnitSystem.SI, UnitSystem.US):
            substituted = derivation.substituted(system=system)
            _, _, rhs = substituted.partition(" = ")
            expression = rhs.replace("\u00b7", "*").replace("\u2212", "-")
            expression = expression.replace("\u00b2", "**2").replace("\u00b3", "**3")
            expression = expression.replace("\u2074", "**4")
            expression = _expand_roots(expression)
            # Pint binds a bare "/ 4166666.67 mm**4" as a division by the NUMBER times
            # the unit, so each value-unit pair has to be parenthesised before parsing.
            expression = _VALUE_UNIT.sub(r"(\1 \2)", expression)
            try:
                value = UREG.parse_expression(expression)
            except Exception as exc:
                unparsed.append(f"{label} [{system.value}]: {substituted} ({exc})")
                continue
            printed = derivation.result.rendered(system=system)
            match = number.match(printed)
            if match is None:
                continue
            expected = float(match.group(1))
            unit = printed[match.end() :].strip().replace("\u00b7", "*")
            try:
                actual = value.to(UREG.Unit(unit)).magnitude
            except Exception:  # pragma: no cover - dimensionally odd lines are skipped
                continue
            checked += 1
            # The printed result carries its own precision, so the tolerance is a little
            # over its last place plus slack for the inputs' own rounding.
            if abs(actual - expected) > max(abs(expected) * 0.01, 5e-4):
                mismatches.append(
                    f"{label} [{system.value}]: {substituted} -> printed {printed}, "
                    f"line evaluates to {actual:.6g}"
                )

    assert not unparsed, (
        "substituted lines the checker could not evaluate. A render-truth gate that "
        "skips what it cannot read reports coverage it does not have — this is how both "
        "§H1.1 derivations went unchecked in both unit systems while the gate still "
        "cleared its floor:\n  " + "\n  ".join(unparsed)
    )
    assert checked >= 20, f"only {checked} substituted lines were checkable"
    assert not mismatches, (
        "substituted lines that do not evaluate to the result printed under them:\n  "
        + "\n  ".join(mismatches)
    )


def test_every_pack_input_model_inherits_the_magnitude_guard():
    """A pack model that validates dimensions and not magnitudes is a silent green waiting.

    ``TensionMember`` bounded ``net_area`` against ``gross_area`` by their ordering and
    never against zero. A net area of −500 mm² — what you get by deducting one bolt hole
    too many — satisfies that ordering trivially and screened to a **passing** scorecard
    on both AISC §D2 limit states. Twenty of the twenty-three pack input models had the
    same shape: dimension checked, magnitude not.

    So the guard lives in one place and this asserts nobody skipped it. A model that
    genuinely needs a signed field declares it in ``signed_fields``, which is a
    declaration a reader can see rather than an omission they cannot.
    """
    import importlib
    import inspect
    import pkgutil

    from pydantic import BaseModel

    import anvilate.packs as packs
    from anvilate.packs._guarded import GuardedInputs
    from anvilate.units import Quantity

    unguarded: list[str] = []
    guarded = 0
    for module_info in pkgutil.iter_modules(packs.__path__):
        module = importlib.import_module(f"anvilate.packs.{module_info.name}")
        for name, obj in vars(module).items():
            if not (inspect.isclass(obj) and issubclass(obj, BaseModel)):
                continue
            if obj.__module__ != module.__name__ or obj is GuardedInputs:
                continue
            carries_quantity = any(
                info.annotation is Quantity or "Quantity" in str(info.annotation)
                for field, info in obj.model_fields.items()
                if field != "signed_fields"
            )
            if not carries_quantity:
                continue
            if issubclass(obj, GuardedInputs):
                guarded += 1
            else:
                unguarded.append(f"{module_info.name}.{name}")

    assert not unguarded, (
        "pack input models carrying Quantity fields that do not inherit "
        "anvilate.packs._guarded.GuardedInputs, so a negative or non-finite magnitude "
        "reaches the screen unchecked:\n  " + "\n  ".join(sorted(unguarded))
    )
    assert guarded >= 20, (
        f"only {guarded} guarded models found — the discoverer stopped discovering"
    )


def test_the_pack_magnitude_guard_actually_rejects_what_it_claims_to():
    """A guard nobody has watched fail is a guard nobody knows works.

    Including the two live defects that motivated it: the negative net area that screened
    to a pass, and the negative bearing area that reached √(A₂/A₁) and came back complex.
    """
    from pydantic import ValidationError

    from anvilate.packs.structural import ConcreteBearing, TensionMember
    from anvilate.units import Quantity

    def q(text: str) -> Quantity:
        return Quantity.parse(text)

    with pytest.raises(ValidationError, match="must not be negative"):
        TensionMember(
            name="t",
            gross_area=q("2000 mm**2"),
            net_area=q("-500 mm**2"),
            load=q("50 kN"),
            material="ASTM-A36",
        )
    with pytest.raises(ValidationError, match="must not be negative"):
        ConcreteBearing(
            name="p",
            bearing_area=q("-250000 mm**2"),
            support_area=q("250000 mm**2"),
            concrete_strength=q("28 MPa"),
            load=q("500 kN"),
        )
    with pytest.raises(ValidationError, match="must be a finite quantity"):
        TensionMember(
            name="t",
            gross_area=q("2000 mm**2"),
            net_area=Quantity(magnitude=float("nan"), unit="mm**2"),
            load=q("50 kN"),
            material="ASTM-A36",
        )
    # A declared signed field is exempt, and stays exempt: the library's contract is that
    # a non-positive DEMAND screens to NOT_EVALUATED rather than raising at construction.
    # Turning that into an exception would be the guard/scorecard pairing bug again.
    member = TensionMember(
        name="t",
        gross_area=q("2000 mm**2"),
        net_area=q("1500 mm**2"),
        load=q("-50 kN"),
        material="ASTM-A36",
    )
    assert member.load.magnitude == -50.0


def _evidence_references() -> set[str]:
    """Every reference string the packs put into a scorecard entry or a derivation.

    These are the citations the evidence bundle actually carries — the ones a reviewer
    reads — rather than the prose in a docstring. Effectivity is about what the bundle
    claims, so this is the surface that has to carry an edition.
    """
    refs: set[str] = set()
    for entry in _structural_entries():
        if entry.reference:
            refs.add(entry.reference)
        if entry.derivation is not None and entry.derivation.citation:
            refs.add(entry.derivation.citation)
    for _, derivation in _sample_derivations():
        if derivation.citation:
            refs.add(derivation.citation)
    return refs


def _editionless_manifest() -> set[str]:
    path = _REPO / "docs" / "api" / "editionless-citations.txt"
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def test_every_cited_standard_names_its_edition():
    """The effectivity gate, held as a ratchet: the debt can only go down.

    A clause without an edition identifies a paragraph in a book nobody named, and the
    evidence bundle's entire claim rests on those clauses. Most of the pack references
    already carry one; the outstanding few are enumerated, and this holds the line in
    both directions so neither the list nor the silence can drift.
    """
    from anvilate.standards.effectivity import names_a_standard, parse_citation

    references = _evidence_references()
    editionless = {
        ref
        for ref in references
        if names_a_standard(ref) is not None and parse_citation(ref) is None
    }
    recorded = _editionless_manifest()

    new = sorted(editionless - recorded)
    assert not new, (
        "these references name a normative standard and not its edition. Add the edition "
        "exactly as the standard spells it (AISC 360-16, ACI 318-19, EN 1993-1-9:2005) — "
        "do NOT add the reference to docs/api/editionless-citations.txt:\n  " + "\n  ".join(new)
    )

    versioned = sorted(recorded - editionless)
    assert not versioned, (
        "these references are recorded as editionless but now name an edition. Strike "
        "them from docs/api/editionless-citations.txt so the debt stays honest:\n  "
        + "\n  ".join(versioned)
    )

    # The discoverer has to keep discovering. A parser that stopped parsing would make
    # `editionless` the whole reference set (caught above), but one that stopped
    # RECOGNISING standards would make it empty and the gate would go green for ever.
    assert sum(1 for r in references if names_a_standard(r) is not None) >= 10, (
        "names_a_standard has stopped recognising the references this suite builds, so "
        "the effectivity gate is passing on an empty set"
    )


def test_the_effectivity_parser_knows_a_eurocode_number_from_a_year():
    """The one place a year-shaped token is not an edition.

    Eurocodes are EN 1990 through EN 1999 — document numbers that read exactly like
    years. Reading "EN 1993-1-9" as the 1993 edition of something called EN would record
    a wrong edition for every Eurocode citation in the library, silently and plausibly.
    Their real edition is the colon suffix, ``EN 1993-1-9:2005``.
    """
    from anvilate.standards.effectivity import names_a_standard, parse_citation

    assert parse_citation("EN 1993-1-9 Table 8.1") is None
    versioned = parse_citation("EN 1993-1-9:2005 Table 8.1")
    assert versioned is not None
    assert versioned.standard == "EN 1993-1-9"
    assert versioned.edition == "2005"
    assert parse_citation("EN 1990:2002") == parse_citation("EN 1990:2002")

    # The ordinary forms still work, and a part number is not an edition.
    for text, standard, edition in (
        ("AISC 360-16 Ch. E", "AISC 360", "16"),
        ("ACI 318-19 §22.8.3", "ACI 318", "19"),
        ("ASCE 7-22 §2.3.6", "ASCE 7", "22"),
        ("Aluminum Design Manual 2020 Part I §B.4", "Aluminum Design Manual", "2020"),
    ):
        parsed = parse_citation(text)
        assert parsed is not None and (parsed.standard, parsed.edition) == (standard, edition)
    assert parse_citation("ISO 286-2") is None  # a part, not an edition
    assert parse_citation("ASME B31.3") is None

    # A textbook is a complete citation and is not effectivity debt.
    assert names_a_standard("Timoshenko plate theory") is None
    assert names_a_standard("Roark's Formulas for Stress and Strain, Table 8.1") is None
    assert names_a_standard("ASME BTH-1 §3-3") == "ASME"


def test_no_pack_ever_says_certified_about_a_user_s_design():
    """A screening tool must not use the vocabulary of certification about its output.

    This is the library-wide half of the check in tests/test_review.py, and it is here
    rather than there because the risk is not confined to the review module: every
    scorecard detail and every reference string is a statement about the user's design,
    and any one of them can be pasted into an email and read as assurance.

    Docstrings are out of scope for the same reason as in the review suite — prose about
    the policy has to be able to name the thing it prohibits.
    """
    from anvilate.review import PROHIBITED_ASSURANCE_LANGUAGE

    renderings: list[tuple[str, str]] = []
    for entry in _structural_entries():
        renderings.append((entry.name, entry.detail))
        if entry.reference:
            renderings.append((entry.name, entry.reference))
    for label, derivation in _sample_derivations():
        if derivation.citation:
            renderings.append((label, derivation.citation))
        renderings.append((label, derivation.result.description))

    offenders = [
        f"{where}: {phrase!r} in {text!r}"
        for where, text in renderings
        for phrase in PROHIBITED_ASSURANCE_LANGUAGE
        if phrase in text.lower()
    ]
    assert not offenders, (
        "these renderings use the language of certification about a user's design:\n  "
        + "\n  ".join(offenders)
    )
    assert len(renderings) >= 30, (
        f"only {len(renderings)} renderings were swept — the discoverer has stopped "
        f"discovering and this gate is passing on an empty set"
    )


def test_every_declared_derivation_typesets():
    """The MathML renderer, held against the corpus rather than against examples.

    A formula the renderer declines falls back to plain text — honest, but it is a
    submittal document losing its stacked fractions, so the library's own derivations are
    required to typeset. A new one written outside the grammar fails here, where the author
    can widen the grammar or reword the formula, rather than silently rendering as a line
    of text in somebody's report.
    """
    from xml.etree import ElementTree as ET

    from anvilate.report.mathml import formula_to_mathml

    corpus = _sample_derivations()
    assert len(corpus) >= 20, f"the derivation corpus came back with {len(corpus)}; too few"
    declined = []
    for label, derivation in corpus:
        for line in derivation.lines():
            math = formula_to_mathml(line)
            if math is None:
                declined.append(f"{label}: {line}")
            else:
                # Valid XML, or the report is not a document a browser can open.
                ET.fromstring(math)
    assert not declined, "derivations the MathML renderer declined:\n" + "\n".join(declined)


def test_the_published_citation_debt_percentage_is_the_real_one():
    """A number that lives only in prose has no gate on it, and this one goes stale every
    time the debt is paid down.

    ``docs/citations.md`` tells a reader what fraction of the public analysis surface names
    no source. It was written at 23% and read 23% after 89 symbols had been paid off. The
    figure is now derived from the two manifests the gate above already holds, so paying
    the debt down without moving the sentence fails here.
    """
    uncited = len(_uncited_manifest())
    total = len(_manifest_surface())
    assert total > 1000, "the surface came back implausibly small, so the ratio is vacuous"
    actual = 100.0 * uncited / total
    published = re.search(
        r"About (\d+)% of the public analysis surface does not",
        (_REPO / "docs" / "citations.md").read_text(),
    )
    assert published is not None, (
        "docs/citations.md no longer states the citation debt as a percentage; either "
        "restore the sentence or delete this test with it"
    )
    claimed = float(published.group(1))
    assert abs(claimed - actual) < 1.0, (
        f"docs/citations.md says {claimed:.0f}% of the analysis surface is uncited; it is "
        f"{actual:.1f}% ({uncited} of {total}). Move the sentence when you move the debt"
    )
