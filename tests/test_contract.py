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
    assert len(modules) > 200, f"the module sweep found only {len(modules)}"
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
    out.extend(_discipline_pack_derivations())
    return out


def _discipline_pack_derivations() -> list[tuple[str, object]]:
    """One screen from every other pack that writes a derivation.

    The render-truth gate is only as wide as what it renders, and the sample above reached
    the structural and industrial packs only — so the hydraulics, geotechnical, electrical,
    lighting, ventilation and noise formulas were rendered by nothing and checked by
    nothing. `test_every_pack_that_writes_a_derivation_is_in_the_render_truth_sample`
    holds this list against the packs that actually build one.
    """
    from anvilate.packs import (
        electrical,
        geotechnical,
        hydraulics,
        lighting,
        masonry,
        noise_exposure,
        ventilation,
    )
    from anvilate.units import Quantity

    def q(text: str) -> Quantity:
        return Quantity.parse(text)

    cards = [
        (
            "hydraulics pump",
            hydraulics.screen_pump_duty(
                hydraulics.PumpDuty(
                    flow_rate=q("0.05 m**3/s"),
                    total_head=q("20 m"),
                    fluid_density=q("1000 kg/m**3"),
                    efficiency=0.70,
                    motor_rating=q("18.5 kW"),
                    npsh_available=q("5.6 m"),
                    npsh_required=q("4 m"),
                )
            ),
        ),
        (
            "hydraulics pipe",
            hydraulics.screen_pipe_run(
                hydraulics.PipeRun(
                    flow_rate=q("0.05 m**3/s"),
                    diameter=q("0.15 m"),
                    length=q("100 m"),
                    roughness=q("0.045 mm"),
                    fitting_loss_coefficient=5.0,
                    kinematic_viscosity=q("1e-6 m**2/s"),
                    available_head=q("10 m"),
                )
            ),
        ),
        (
            "footing",
            geotechnical.screen_shallow_footing(
                geotechnical.ShallowFooting(
                    width=q("2 m"),
                    length=q("3 m"),
                    embedment_depth=q("1.2 m"),
                    applied_load=q("900 kN"),
                    cohesion=q("20 kPa"),
                    friction_angle=28.0,
                    unit_weight=q("18 kN/m**3"),
                )
            ),
        ),
        (
            "wall",
            geotechnical.screen_retaining_wall(
                geotechnical.RetainingWall(
                    retained_height=q("4 m"),
                    backfill_unit_weight=q("19 kN/m**3"),
                    backfill_friction_angle=32.0,
                    vertical_load=q("180 kN/m"),
                    load_arm=q("1.4 m"),
                    base_friction_coefficient=0.5,
                )
            ),
        ),
        # Both sides of the effective-stress floor: dry, and drowned so the clamp binds.
        (
            "slope dry",
            geotechnical.screen_infinite_slope(
                geotechnical.InfiniteSlope(
                    cohesion=q("20 kPa"),
                    friction_angle=30.0,
                    unit_weight=q("19 kN/m**3"),
                    depth=q("2.5 m"),
                    slope_angle=35.0,
                )
            ),
        ),
        (
            "slope drowned",
            geotechnical.screen_infinite_slope(
                geotechnical.InfiniteSlope(
                    cohesion=q("20 kPa"),
                    friction_angle=30.0,
                    unit_weight=q("19 kN/m**3"),
                    depth=q("2.5 m"),
                    slope_angle=35.0,
                    pore_pressure=q("500 kPa"),
                )
            ),
        ),
        (
            "pile",
            geotechnical.screen_driven_pile(
                geotechnical.DrivenPile(
                    diameter=q("450 mm"),
                    length=q("14 m"),
                    undrained_shear_strength=q("60 kPa"),
                    adhesion_factor=0.55,
                    applied_load=q("300 kN"),
                    factor_of_safety=2.5,
                )
            ),
        ),
        # Both sides of the reactance branch: the reactive term renders as zero without one.
        (
            "feeder resistive",
            electrical.screen_feeder(
                electrical.Feeder(
                    load_power=q("75 kW"),
                    power_factor=0.85,
                    line_voltage=q("400 V"),
                    resistivity=q("1.72e-8 ohm*m"),
                    one_way_length=q("80 m"),
                    conductor_area=q("70 mm**2"),
                    conductor_ampacity=q("180 A"),
                )
            ),
        ),
        (
            "feeder reactive",
            electrical.screen_feeder(
                electrical.Feeder(
                    load_power=q("75 kW"),
                    power_factor=0.85,
                    line_voltage=q("400 V"),
                    resistivity=q("1.72e-8 ohm*m"),
                    one_way_length=q("80 m"),
                    conductor_area=q("70 mm**2"),
                    conductor_ampacity=q("180 A"),
                    reactance=q("0.008 ohm"),
                )
            ),
        ),
        (
            "lighting",
            lighting.screen_lighting(
                lighting.LightingInstallation(
                    luminaire_count=24,
                    lumens_per_luminaire=q("4800 lumen"),
                    input_watts_per_luminaire=q("36 W"),
                    coefficient_of_utilization=0.62,
                    light_loss_factor=0.8,
                    floor_area=q("300 m**2"),
                    required_illuminance=q("300 lux"),
                    allowable_power_density=q("9 W/m**2"),
                )
            ),
        ),
        (
            "ventilation",
            ventilation.screen_ventilation(
                ventilation.VentilationZone(
                    people_outdoor_rate=q("2.5 L/s"),
                    occupancy=40,
                    area_outdoor_rate=q("0.3 L/s/m**2"),
                    floor_area=q("300 m**2"),
                    zone_air_distribution_effectiveness=0.8,
                    provided_outdoor_airflow=q("300 L/s"),
                    room_volume=q("900 m**3"),
                    required_air_changes=1.0,
                )
            ),
        ),
        # Both sides of the h/r = 99 crossover, where §8.2.4 changes formula.
        (
            "masonry slender",
            masonry.screen_masonry_wall(
                masonry.MasonryWall(
                    masonry_strength=q("13.8 MPa"),
                    slenderness_ratio=110.0,
                    axial_stress=q("1.2 MPa"),
                    flexural_stress=q("0.9 MPa"),
                )
            ),
        ),
        (
            "masonry stocky",
            masonry.screen_masonry_wall(
                masonry.MasonryWall(
                    masonry_strength=q("13.8 MPa"),
                    slenderness_ratio=84.0,
                    axial_stress=q("1.2 MPa"),
                    flexural_stress=q("0.9 MPa"),
                )
            ),
        ),
        (
            "noise",
            noise_exposure.screen_noise_exposure(
                noise_exposure.WorkerNoiseExposure(
                    machine_levels=(88.0, 84.0), exposure_duration=q("6 hour")
                )
            ),
        ),
        # Boundary cases, from a sweep of the new derivations across their extremes. Each
        # is a branch or a term that the ordinary case above leaves at a value where an
        # error would not show: a reactive term that is zero, an occupancy that is zero, a
        # single-source noise level that never enters the logarithmic sum, an efficiency
        # at the top of its range.
        (
            "feeder unity power factor",
            electrical.screen_feeder(
                electrical.Feeder(
                    load_power=q("75 kW"),
                    power_factor=1.0,
                    line_voltage=q("400 V"),
                    resistivity=q("1.72e-8 ohm*m"),
                    one_way_length=q("80 m"),
                    conductor_area=q("70 mm**2"),
                    conductor_ampacity=q("180 A"),
                    reactance=q("0.05 ohm"),
                )
            ),
        ),
        (
            "ventilation unoccupied",
            ventilation.screen_ventilation(
                ventilation.VentilationZone(
                    people_outdoor_rate=q("2.5 L/s"),
                    occupancy=0,
                    area_outdoor_rate=q("0.3 L/s/m**2"),
                    floor_area=q("300 m**2"),
                    zone_air_distribution_effectiveness=1.0,
                    provided_outdoor_airflow=q("300 L/s"),
                    room_volume=q("900 m**3"),
                    required_air_changes=1.0,
                )
            ),
        ),
        (
            "noise single source",
            noise_exposure.screen_noise_exposure(
                noise_exposure.WorkerNoiseExposure(
                    machine_levels=(85.0,), exposure_duration=q("8 hour")
                )
            ),
        ),
        (
            "pump near-ideal",
            hydraulics.screen_pump_duty(
                hydraulics.PumpDuty(
                    flow_rate=q("0.05 m**3/s"),
                    total_head=q("20 m"),
                    fluid_density=q("1000 kg/m**3"),
                    efficiency=0.99,
                    motor_rating=q("18.5 kW"),
                    npsh_available=q("4.4 m"),
                    npsh_required=q("4 m"),
                )
            ),
        ),
        # Both sides of the §8.2.4 crossover, one step apart, where the two curves meet.
        (
            "masonry at the crossover",
            masonry.screen_masonry_wall(
                masonry.MasonryWall(
                    masonry_strength=q("13.8 MPa"),
                    slenderness_ratio=98.999,
                    axial_stress=q("1.2 MPa"),
                    flexural_stress=q("0.9 MPa"),
                )
            ),
        ),
        (
            "masonry past the crossover",
            masonry.screen_masonry_wall(
                masonry.MasonryWall(
                    masonry_strength=q("13.8 MPa"),
                    slenderness_ratio=99.001,
                    axial_stress=q("1.2 MPa"),
                    flexural_stress=q("0.9 MPa"),
                )
            ),
        ),
    ]
    out = [
        (f"{label} {entry.name}", entry.derivation)
        for label, card in cards
        for entry in card.entries
        if entry.derivation is not None
    ]
    out.extend(_load_combination_derivations())
    out.extend(_pressure_vessel_derivations())
    out.extend(_spectrum_and_lifter_derivations())
    out.extend(_material_and_carbon_derivations())
    return out


def _material_and_carbon_derivations() -> list[tuple[str, object]]:
    """The four NDS margins and an itemised embodied-carbon estimate.

    The bearing value is here for its symbol as much as its formula: NDS writes it F'_c⊥,
    and the perpendicular sign has to be a name character in both the substituter and the
    MathML grammar or the line substitutes correctly and then falls back to plain text.
    """
    from anvilate.analysis.nds_timber import (
        nds_bearing_scorecard,
        nds_bending_scorecard,
        nds_compression_scorecard,
        nds_shear_scorecard,
    )
    from anvilate.units import Quantity

    def q(text: str) -> Quantity:
        return Quantity.parse(text)

    entries = [
        (
            "nds bending",
            nds_bending_scorecard(
                "header bending", bending_stress=q("8 MPa"), adjusted_bending_value=q("12.4 MPa")
            ),
        ),
        (
            "nds shear",
            nds_shear_scorecard(
                "header shear", shear_stress=q("0.7 MPa"), adjusted_shear_value=q("1.2 MPa")
            ),
        ),
        (
            "nds bearing",
            nds_bearing_scorecard(
                "end bearing", bearing_stress=q("2 MPa"), adjusted_bearing_value=q("4 MPa")
            ),
        ),
        (
            "nds compression",
            nds_compression_scorecard(
                "post compression",
                compression_stress=q("5 MPa"),
                adjusted_compression_value=q("9.5 MPa"),
            ),
        ),
    ]
    from anvilate.analysis import (
        CarbonFactor,
        ModuleScope,
        carbon_contribution,
        embodied_carbon_estimate,
        embodied_carbon_scorecard,
    )

    # More than one contribution, because the sum is written out term by term and a
    # one-item estimate would render a "sum" with nothing to add.
    factors = {
        "steel, hot-rolled section": 1.55,
        "aluminium, extruded": 8.60,
        "polymer, injection moulded": 3.10,
    }
    contributions = [
        carbon_contribution(
            label=material.split(",")[0],
            mass=q(f"{10.0 * index} kg"),
            factor=CarbonFactor(
                material=material,
                value=value,
                scope=ModuleScope.A1_A3,
                source="generic federal dataset, cited by the engineer of record",
                band_low=0.75,
                band_high=1.50,
            ),
        )
        for index, (material, value) in enumerate(factors.items(), start=1)
    ]
    entries.append(
        (
            "embodied carbon",
            embodied_carbon_scorecard(
                "assembly",
                estimate=embodied_carbon_estimate(contributions),
                budget=q("500 kg"),
            ),
        )
    )
    return [(label, entry.derivation) for label, entry in entries if entry.derivation is not None]


def _spectrum_and_lifter_derivations() -> list[tuple[str, object]]:
    """The Miner sum and the two BTH-1 margins.

    The spectrum includes a block below the cutoff, whose endurance is infinite: its term
    is a finite count over `inf`, which is zero, and rendering it is how the report says
    "this block does no damage" rather than dropping a block from a sum it was part of.
    """
    from anvilate.analysis.fatigue import weld_fatigue_scorecard
    from anvilate.analysis.lifting_device import (
        DesignCategory,
        ServiceClass,
        bth1_fatigue_scorecard,
        bth1_member_scorecard,
    )
    from anvilate.units import Quantity

    def q(text: str) -> Quantity:
        return Quantity.parse(text)

    entries = [
        (
            "weld spectrum",
            weld_fatigue_scorecard(
                "weld fatigue",
                stress_ranges=[q("80 MPa"), q("45 MPa"), q("15 MPa")],
                applied_cycles=[2.0e5, 1.0e6, 5.0e6],
                detail_category=q("90 MPa"),
            ),
        ),
        (
            "bth1 member",
            bth1_member_scorecard(
                "lug net tension",
                stress=q("96 MPa"),
                allowable=q("124 MPa"),
                category=DesignCategory.B,
            ),
        ),
        (
            "bth1 fatigue",
            bth1_fatigue_scorecard(
                "lug fatigue",
                service_class=ServiceClass.CLASS_2,
                stress_range=q("48 MPa"),
                allowable_stress_range=q("69 MPa"),
            ),
        ),
    ]
    return [(label, entry.derivation) for label, entry in entries if entry.derivation is not None]


def _pressure_vessel_derivations() -> list[tuple[str, object]]:
    """The three pressure-equipment scorecards that render a formula.

    These live in `anvilate.analysis`, not in a pack, so the pack-coverage gate does not
    reach them — and a formula the render-truth gate never evaluates is a formula nothing
    checks, whichever package it lives in.
    """
    from anvilate.analysis import (
        AllowableStress,
        asme_b313_branch_reinforcement,
        asme_b313_branch_reinforcement_scorecard,
        asme_b313_pressure_scorecard,
        asme_ug37_nozzle_reinforcement,
        asme_ug37_reinforcement_scorecard,
    )
    from anvilate.units import Quantity

    def q(text: str) -> Quantity:
        return Quantity.parse(text)

    allowable = AllowableStress(
        value=q("138 MPa"), temperature=q("477.6 K"), material="A106-B", source="Table A-1"
    )
    entries = [
        (
            "b313 pressure",
            asme_b313_pressure_scorecard(
                "process line",
                design_pressure=q("5 MPa"),
                design_temperature=q("477.6 K"),
                outside_diameter=q("114.3 mm"),
                nominal_wall=q("6.02 mm"),
                allowable=allowable,
                corrosion_allowance=q("1.5 mm"),
            ),
        ),
        (
            "b313 branch",
            asme_b313_branch_reinforcement_scorecard(
                "branch opening",
                reinforcement=asme_b313_branch_reinforcement(
                    run_outside_diameter=q("406.40 mm"),
                    run_wall=q("4.18 mm"),
                    run_pressure_design_thickness=q("3.78 mm"),
                    branch_outside_diameter=q("26.7 mm"),
                    branch_wall=q("2.51 mm"),
                    branch_pressure_design_thickness=q("0.25 mm"),
                    mechanical_allowance=q("0 mm"),
                ),
            ),
        ),
        (
            "ug37 nozzle",
            asme_ug37_reinforcement_scorecard(
                "nozzle opening",
                reinforcement=asme_ug37_nozzle_reinforcement(
                    shell_thickness=q("12 mm"),
                    shell_required_thickness=q("8 mm"),
                    nozzle_outside_diameter=q("168.3 mm"),
                    nozzle_thickness=q("10.97 mm"),
                    nozzle_required_thickness=q("4 mm"),
                    corrosion_allowance=q("1.5 mm"),
                    weld_leg=q("8 mm"),
                ),
            ),
        ),
    ]
    return [(label, entry.derivation) for label, entry in entries if entry.derivation is not None]


def _load_combination_derivations() -> list[tuple[str, object]]:
    """One entry per ASCE 7 combination set, including the counteracting case.

    The combination derivation builds its symbolic line from the governing combination's
    own factors, so a template error would show up only on the combination that governs —
    which is why the uplift case is here beside the gravity one.
    """
    from anvilate.loads import (
        LoadNature,
        asce7_asd_basic,
        asce7_lrfd_basic,
        asce7_lrfd_seismic,
        combination_scorecard,
    )

    cases = (
        (
            "gravity",
            asce7_lrfd_basic(),
            {LoadNature.DEAD: 12.0, LoadNature.LIVE: 30.0, LoadNature.SNOW: 8.0},
            90.0,
            False,
        ),
        ("uplift", asce7_lrfd_basic(), {LoadNature.DEAD: 12.0, LoadNature.WIND: -40.0}, 30.0, True),
        ("asd", asce7_asd_basic(), {LoadNature.DEAD: 12.0, LoadNature.LIVE: 30.0}, 60.0, False),
        (
            "seismic",
            asce7_lrfd_seismic(s_ds=0.9),
            {LoadNature.DEAD: 12.0, LoadNature.LIVE: 30.0, LoadNature.SEISMIC: 25.0},
            90.0,
            False,
        ),
    )
    out: list[tuple[str, object]] = []
    for label, combinations, loads, capacity, minimize in cases:
        entry = combination_scorecard(
            label,
            combinations=combinations,
            loads=loads,
            capacity=capacity,
            required=1.0,
            minimize=minimize,
        )
        if entry.derivation is not None:
            out.append((f"combination {label}", entry.derivation))
    return out


def test_every_pack_that_writes_a_derivation_is_in_the_render_truth_sample():
    """A pack that builds a formula nothing renders is a formula nothing checks.

    The sample was hand-written, so a new pack's derivations joined the library without
    joining the gate that evaluates them. This reads the packages rather than a list of
    names: any pack module whose source constructs a `Derivation` has to turn up in the
    sample, and the sample has to be non-trivial for each.
    """
    import anvilate.packs as packs_pkg

    writing = {
        name
        for _, name, _ in pkgutil.iter_modules(packs_pkg.__path__)
        if not name.startswith("_")
        and "Derivation(" in (Path(packs_pkg.__path__[0]) / f"{name}.py").read_text("utf-8")
    }
    assert len(writing) >= 6, f"only {len(writing)} packs write a derivation; the pattern moved"

    sampled = {
        derivation.citation
        for _, derivation in _sample_derivations()
        if derivation.citation is not None
    }
    missing: list[str] = []
    for name in sorted(writing):
        module = importlib.import_module(f"anvilate.packs.{name}")
        cited = {
            value
            for attribute, value in vars(module).items()
            if attribute.endswith("_REFERENCE") and isinstance(value, str)
        }
        if cited and not (cited & sampled):
            missing.append(f"{name} (cites {sorted(cited)[0]!r} and renders in no sample)")
    assert not missing, (
        "these packs build derivations the render-truth gate never evaluates. Add a screen "
        "to _discipline_pack_derivations:\n  " + "\n  ".join(missing)
    )


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

    radical = "\u221a((250000 mm**2)/(40000 mm**2))"
    expanded = UREG.parse_expression(_expand_roots(radical))
    assert math.isclose(float(expanded), 2.5)

    # What pint does with the radical *itself* depends on the interpreter, and the claim
    # here is that neither answer can be trusted. On 3.11 it drops the character and returns
    # 6.25 — the ratio, unrooted, which is the silent wrong number this expansion exists to
    # prevent. On 3.12 the rewritten tokenizer hands the character to the unit lookup and it
    # raises. Asserting the 3.11 behaviour alone made this test a claim about CPython's
    # tokenizer, and it failed the first time the suite met 3.12.
    try:
        plain = float(UREG.parse_expression(radical))
    except Exception:  # noqa: BLE001 - any refusal is the acceptable outcome
        plain = None
    assert plain is None or math.isclose(plain, 6.25)
    assert plain != 2.5, "pint answered the radical correctly; the expansion is now dead code"


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

    Built here rather than read off the session collector, because a test cannot know how
    much of the suite has run before it. The RATCHET reads the collector (tests/conftest.py)
    and so sees the whole library; this deterministic set is what other tests compare
    against.
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


def test_the_effectivity_ratchet_reads_the_whole_library():
    """The gate this replaced built its own reference set, and the set was too small.

    It reached the structural pack plus whatever the render-truth sample happened to
    include, so the debt read as six references while the library was building
    twenty-two — and every one of the sixteen it could not see was a real editionless
    citation. The ratchet now runs off the session collector in tests/conftest.py; what
    is held here is its rule, and the fact that the collector records what the packs
    attach. The two directions of the ratchet itself need the whole suite and are
    asserted there.
    """
    import conftest

    # Act first, then observe: how much of the suite has already run is not knowable, so
    # the probe supplies its own citations rather than assuming somebody else's.
    produced = _evidence_references()
    assert len(produced) >= 10
    observed = conftest._observed_citations()
    unseen = sorted(produced - observed)
    assert not unseen, (
        "these references were just produced by the packs and the collector did not "
        "record them:\n  " + "\n  ".join(unseen)
    )

    # The rule itself, on data rather than on the library: a body with an edition is not
    # debt, a body without one is, and a textbook is neither.
    probes = {
        "AISC 360-16 Ch. F": False,
        "ACI 318-19 §22.8.3": False,
        "EN 1993-1-9:2005 Table 8.1": False,
        "ASME BTH-1 §3-3": True,
        "NEC 310.16 — conductor ampacity": True,
        "BS 7910 / R6 Option 1 failure assessment diagram": True,
        "Roark's Formulas, Table 11.4": False,
        "Timoshenko plate theory": False,
    }
    assert conftest._editionless_citations(set(probes)) == {
        text for text, debt in probes.items() if debt
    }
    # And the manifest is the shape the ratchet reads: one clause per non-comment line.
    manifest = conftest._editionless_manifest()
    assert "NDS" in manifest and all(not text.startswith("#") for text in manifest)


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
    """A number that lives only in prose has no gate on it, and this one went stale every
    time the debt was paid down.

    ``docs/citations.md`` told a reader what fraction of the public analysis surface named
    no source. It was written at 23% and still read 23% after 89 symbols had been paid off,
    then failed for real on the next four batches. The debt is now zero, so the claim the
    page has to keep changed shape: it must say the surface is covered, and say it with the
    count the manifest actually holds. If a symbol is ever uncited again the percentage
    branch takes over, because a page that implies coverage the library does not have is
    the failure this guards either way.
    """
    uncited = len(_uncited_manifest())
    total = len(_manifest_surface())
    assert total > 1000, "the surface came back implausibly small, so the claim is vacuous"
    page = (_REPO / "docs" / "citations.md").read_text()

    if uncited == 0:
        assert f"{total:,} public analysis symbols now" in page, (
            "the debt is paid and docs/citations.md does not say so, or says it with a "
            f"different count than the {total:,} symbols the manifest holds"
        )
        assert "does not\n  yet name a source" not in page, (
            "docs/citations.md still describes an outstanding debt that is paid"
        )
        return

    actual = 100.0 * uncited / total
    published = re.search(r"About (\d+)% of the public analysis surface does not", page)
    assert published is not None, (
        f"{uncited} symbols name no source and docs/citations.md no longer states the "
        "debt as a percentage. Restore the sentence rather than letting the page imply "
        "coverage the library does not have"
    )
    claimed = float(published.group(1))
    assert abs(claimed - actual) < 1.0, (
        f"docs/citations.md says {claimed:.0f}% of the analysis surface is uncited; it is "
        f"{actual:.1f}% ({uncited} of {total}). Move the sentence when you move the debt"
    )


def test_the_contributing_pages_two_traps_are_arithmetic_it_can_check():
    """`docs/contributing-analysis.md` teaches two conversion traps and a survey number.

    The temperature one carries its own worked factor — a delta read through the absolute
    scale, cubed — and the raise-site survey is a count of the shipped tree that drifts
    every time a guard is added. Neither had a gate.
    """
    import ast
    import re

    page = " ".join(
        (Path(__file__).resolve().parent.parent / "docs" / "contributing-analysis.md")
        .read_text()
        .split()
    )

    trap = re.search(
        r"carries the ([\d.]+) offset into a delta\. In a cubic correlation that was a "
        r"factor of ([\d,]+)",
        page,
    )
    assert trap is not None, "the temperature trap on the contributing page has moved"
    offset = float(trap.group(1))
    claimed = float(trap.group(2).replace(",", ""))
    # The factor is exact for one delta, and the page's own arithmetic names which:
    # ((ΔT + offset)/ΔT)³ = claimed has a single positive root.
    delta = offset / (claimed ** (1.0 / 3.0) - 1.0)
    assert ((delta + offset) / delta) ** 3 == pytest.approx(claimed, rel=1e-4)
    assert delta == pytest.approx(10.0, abs=0.05), (
        "the page's factor no longer corresponds to a round temperature difference"
    )
    from anvilate.units import Quantity

    assert Quantity(magnitude=delta, unit="degC").to("K").magnitude == pytest.approx(
        delta + offset, abs=1e-9
    ), "the offset the page names is not the one the registry applies"

    survey = re.search(r"around (\d+)% of the roughly ([\d,]+) `raise` sites", page)
    assert survey is not None, "the raise-site survey on the contributing page has moved"
    sites = 0
    for module in (Path(__file__).resolve().parent.parent / "src" / "anvilate").rglob("*.py"):
        sites += sum(
            isinstance(node, ast.Raise) for node in ast.walk(ast.parse(module.read_text()))
        )
    stated = float(survey.group(2).replace(",", ""))
    assert sites == pytest.approx(stated, rel=0.05), (
        f"the page says roughly {stated:.0f} raise sites and the tree has {sites}"
    )


def test_no_shipped_module_carries_an_invalid_escape_sequence():
    """A docstring with `\\*` in it is a non-raw string Python is deprecating.

    Found by a page gate that walks the tree with `ast.parse`: `nds_timber` wrote F_b\\*
    in a plain docstring, which is a `SyntaxWarning` today and a `SyntaxError` later. The
    fix is one `r` prefix, and this is the check that says when another appears.
    """
    import ast
    import warnings

    offenders: list[str] = []
    parsed = 0
    for module in (Path(__file__).resolve().parent.parent / "src" / "anvilate").rglob("*.py"):
        parsed += 1
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ast.parse(module.read_text())
        offenders += [f"{module.name}: {w.message}" for w in caught]
    assert parsed > 200, f"the sweep parsed only {parsed} modules; the root has moved"
    assert not offenders, f"modules parse with warnings: {offenders}"


# The pages whose distinctive numbers are facts about the world rather than about this
# library: published package versions verified against PyPI on a stated date, a paper's
# reported results, and dated research write-ups quoting other people's published figures.
# Nothing here can recompute any of them, and a gate that pretended to would be checking
# that a literal equals itself.
#
# Paths are relative to `docs/`, because the sweep below is **recursive**. It was not, and
# `docs/research/` — two write-ups denser in numbers than most of the library's own pages —
# was invisible to it: not gated, not excused, just below the level the glob looked at.
_PAGES_WHOSE_NUMBERS_ARE_EXTERNAL = frozenset(
    {
        "export-targets.md",  # dependency versions, re-verified against PyPI by hand
        "valid-is-not-correct.md",  # an arXiv identifier and that paper's own figures
        "research/2026-07-27-capability-research.md",  # other projects' published figures
        "research/2026-07-27-capability-research-wave-2.md",  # likewise
    }
)


def test_every_docs_page_that_argues_from_a_number_is_opened_by_a_test():
    """The ratchet under this session's sweep: a page's numbers need a test that reads it.

    A number quoted only in prose has no gate on it, and the sweep that found nineteen
    such pages is worth keeping rather than repeating. "Distinctive" is a decimal with two
    or more fraction digits or a comma-grouped integer — enough to be a claim and not a
    section number — and a page counts as opened when some test names its filename.
    """
    import ast
    import re

    root = Path(__file__).resolve().parent.parent
    # A page counts as opened only when a test names it in a *string literal*. The first
    # version of this gate searched the raw source, and `timber-screening.md` — the page
    # carrying more numbers than any other — passed it on a mention inside a comment.
    # A gate satisfiable by a comment is the substring-gate failure one level up.
    suite = "\n".join(
        literal.value
        for module in (root / "tests").glob("*.py")
        for literal in ast.walk(ast.parse(module.read_text()))
        if isinstance(literal, ast.Constant) and isinstance(literal.value, str)
    )
    distinctive = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+\.\d{2,})(?![\w])")

    for name in _PAGES_WHOSE_NUMBERS_ARE_EXTERNAL:
        assert (root / "docs" / name).exists(), f"the allow-list names {name}, which is gone"

    ungated = sorted(
        str(page.relative_to(root / "docs"))
        for page in (root / "docs").rglob("*.md")
        if page.name not in suite
        and distinctive.search(page.read_text())
        and str(page.relative_to(root / "docs")) not in _PAGES_WHOSE_NUMBERS_ARE_EXTERNAL
    )
    assert not ungated, (
        f"these pages argue from numbers no test reads: {ungated}. Open the page in a test "
        "and hold its figures against what the library computes, or add it to "
        "_PAGES_WHOSE_NUMBERS_ARE_EXTERNAL with the reason."
    )

    # The allow-list earns its place: both pages really do carry such numbers, so an entry
    # cannot sit there excusing a page that has nothing to excuse.
    for name in _PAGES_WHOSE_NUMBERS_ARE_EXTERNAL:
        assert distinctive.search((root / "docs" / name).read_text()), (
            f"{name} is excused from the sweep and carries no number to excuse"
        )


def test_the_package_docstrings_quoted_constants_are_the_functions_own():
    """`anvilate.analysis`'s docstring writes four coefficients out in full.

    They belong to functions in other modules, so nothing tied the summary to the code:
    the same lens as the docs and example sweeps, one level in. Each is recovered from
    the function that applies it rather than compared against a literal.
    """
    import math
    import re

    from anvilate import analysis
    from anvilate.units import Quantity

    prose = " ".join((analysis.__doc__ or "").split())

    def _quoted(pattern: str) -> float:
        match = re.search(pattern, prose)
        assert match is not None, f"the analysis docstring no longer states {pattern}"
        return float(match.group(1))

    # The two 1/7-power-law plate coefficients: C = value·Re^-0.2, so the coefficient is
    # the returned number times Re^0.2.
    flow = {
        "freestream_velocity": Quantity.parse("10 m/s"),
        "kinematic_viscosity": Quantity.parse("1.5e-5 m**2/s"),
    }
    reynolds = 10.0 * 2.0 / 1.5e-5
    local = analysis.turbulent_skin_friction_coefficient(distance=Quantity.parse("2 m"), **flow)
    average = analysis.turbulent_plate_drag_coefficient(plate_length=Quantity.parse("2 m"), **flow)
    assert local * reynolds**0.2 == pytest.approx(
        _quoted(r"C_f = ([\d.]+)/Re_x\^\(1/5\)"), rel=1e-9
    )
    assert average * reynolds**0.2 == pytest.approx(
        _quoted(r"C_D = ([\d.]+)/Re_L\^\(1/5\)"), rel=1e-9
    )

    # The moist-air humidity coefficient: v grows linearly in W, so two humidity ratios
    # give the slope, and the coefficient is the slope over the dry-air intercept.
    air = {"temperature": Quantity.parse("293.15 K"), "pressure": Quantity.parse("101325 Pa")}
    dry = analysis.moist_air_specific_volume(humidity_ratio=0.0, **air).to("m**3/kg").magnitude
    humid = analysis.moist_air_specific_volume(humidity_ratio=0.01, **air).to("m**3/kg").magnitude
    # The docstring rounds the molar-mass ratio to three places; the module carries it
    # in full, so the check is to the digits the summary prints.
    assert (humid - dry) / (0.01 * dry) == pytest.approx(_quoted(r"\(1 \+ ([\d.]+)·W\)"), abs=5e-4)

    # The coaxial constant: Z_0·√ε_r/ln(b/a) is it, by construction of the formula.
    impedance = (
        analysis.coaxial_characteristic_impedance(
            inner_radius=Quantity.parse("1 mm"),
            outer_radius=Quantity.parse("3 mm"),
            relative_permittivity=2.25,
        )
        .to("ohm")
        .magnitude
    )
    assert impedance * math.sqrt(2.25) / math.log(3.0) == pytest.approx(
        _quoted(r"Z_0 = \(([\d.]+)/√ε_r\)"), abs=5e-3
    )


def test_the_ci_skip_gate_allows_exactly_what_the_scheduled_jobs_install():
    """`tests/conftest.py` fails a CI run that skips a gate for a missing package.

    Its allow-list is the packages only the scheduled jobs install, and an entry no job
    backs would excuse a skip forever. So the list is held against the workflow: every
    allowed import is installed by a scheduled job, and every package those jobs install
    is allowed. `lxml.etree` is the import name beside the distribution's own.
    """
    import re

    root = Path(__file__).resolve().parent.parent
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text()
    conftest = (root / "tests" / "conftest.py").read_text()

    allowed = set(
        re.findall(
            r'"([\w.]+)"',
            re.search(r"_SCHEDULED_ONLY_IMPORTS = frozenset\(\{([^}]*)\}", conftest).group(1),
        )
    )
    assert allowed, "the conftest gate no longer declares an allow-list"

    # Every extra package a scheduled job installs, from its own install step.
    scheduled = set()
    for job in re.split(r"\n  (?=\w[\w-]*:)", workflow)[1:]:
        if "github.event_name == 'schedule'" not in job:
            continue
        for install in re.findall(r'pip install -e "\.\[dev\]"([^\n]*)', job):
            for token in install.split():
                requirement = token.strip('"')
                # A version pin ("numpy<2") constrains a package something else already
                # pulls in; it adds no import a test could skip on.
                if not any(char in requirement for char in "<>=!~"):
                    scheduled.add(requirement)
    assert scheduled, "no scheduled job installs an extra package any more"

    aliases = {"lxml": {"lxml", "lxml.etree"}}
    expected = {name for package in scheduled for name in aliases.get(package, {package})}
    assert allowed == expected, (
        f"the conftest allow-list is {sorted(allowed)} and the scheduled jobs install "
        f"{sorted(scheduled)}; an allowed import no job installs excuses a skip forever"
    )


# --- The refusal a bare number gets ----------------------------------------------------
#
# The library's whole premise is that it takes dimensioned quantities, so the single most
# likely way to call it wrong is to pass a number. Measured on 2026-08-29, 1,524 of about
# 1,740 public analysis functions answered that with
# `AttributeError: 'float' object has no attribute 'has_dimension'` — the guard calling a
# method on the thing it was checking. That names no parameter, no expected dimension, and
# no library; it reads as an internal slip, which is exactly what it was.


def _probe_kwargs(signature):
    """Every required parameter bound to a bare ``1.0``, or ``None`` if there are none."""
    kwargs = {}
    for parameter in signature.parameters.values():
        if parameter.default is not inspect.Parameter.empty:
            continue
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        kwargs[parameter.name] = 1.0
    return kwargs or None


def test_every_public_analysis_function_refuses_a_bare_number_by_name():
    """A refusal that names nothing is the failure this gate exists to catch.

    Every required parameter is bound to ``1.0`` and the call made. Returning is allowed —
    a dimensionless correlation legitimately takes plain floats. Raising is allowed. What
    is not allowed is raising something that names neither the parameter nor what was
    wanted: an `AttributeError` off a guard, a `KeyError` off a table lookup, a `TypeError`
    off `len()` or an unpack.

    Two halves, because either alone is satisfiable by accident. The class must be
    `ValueError` — the class every other refusal in the package uses, and the one a caller
    is told to catch — **and** the message must name one of the parameters, so that a bare
    `raise ValueError("bad input")` does not pass. The floor on the number probed is here
    for the third way a gate like this goes quiet: covering nothing and saying so in green.
    """
    probed, failures = [], []
    for name in sorted(analysis_pkg.__all__):
        function = getattr(analysis_pkg, name, None)
        if not inspect.isfunction(function):
            continue
        try:
            signature = inspect.signature(function)
        except (TypeError, ValueError):  # pragma: no cover - every signature resolves today
            continue
        kwargs = _probe_kwargs(signature)
        if kwargs is None:
            continue
        probed.append(name)
        try:
            function(**kwargs)
        except ValueError as refusal:
            if not any(parameter in str(refusal) for parameter in kwargs):
                failures.append(f"{name}: refusal names no parameter: {refusal}")
        except Exception as slip:  # noqa: BLE001 - the class is the thing under test
            failures.append(f"{name}: {type(slip).__name__}: {slip}")

    assert len(probed) > 1500, (
        f"only {len(probed)} public analysis functions were probed; this gate covers the "
        "surface or it covers nothing"
    )
    assert not failures, (
        f"{len(failures)} public function(s) answer a bare number with something other "
        "than a ValueError naming the parameter:\n  " + "\n  ".join(sorted(failures)[:25])
    )


def test_every_public_analysis_function_refuses_a_wrapped_number_by_naming_the_mistake():
    """The mirror of the sweep above, and in this library the likelier mistake of the two.

    A caller told that everything here is a `Quantity` wraps the parameters that are *not*
    quantities — a ratio, a count, an angle in degrees. Every required parameter is bound to
    a quantity with an absurd dimension and the call made; 213 functions answered with the
    interpreter's own sentence, `'<' not supported between instances of 'Quantity' and
    'int'`, which names neither the parameter nor the mistake.

    They were not 213 separate defects. `Quantity` defined no ordering, no arithmetic and no
    numeric conversions at all, so the interpreter was answering for it in every one of
    them; defining those operators to refuse fixed all 213 in one file and could regress
    nothing, because each of them raised before.

    The assertion here is weaker than the bare-number gate's on purpose, and the reason is
    worth stating: an operator does not know the parameter it was reached through, so it
    cannot name one. It names the mistake and the number to pass instead. Requiring a
    parameter name here would be requiring the 170 call sites the one-file fix replaced.
    """
    from anvilate.units import Quantity

    absurd = Quantity(magnitude=1.0, unit="candela")
    probed, failures = [], []
    for name in sorted(analysis_pkg.__all__):
        function = getattr(analysis_pkg, name, None)
        if not inspect.isfunction(function):
            continue
        try:
            signature = inspect.signature(function)
        except (TypeError, ValueError):  # pragma: no cover - every signature resolves today
            continue
        parameters = [
            p.name
            for p in signature.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        ]
        if not parameters:
            continue
        probed.append(name)
        try:
            function(**dict.fromkeys(parameters, absurd))
        except ValueError:
            continue
        except Exception as slip:  # noqa: BLE001 - the class is the thing under test
            failures.append(f"{name}: {type(slip).__name__}: {slip}")

    assert len(probed) > 1500, (
        f"only {len(probed)} public analysis functions were probed; this gate covers the "
        "surface or it covers nothing"
    )
    assert not failures, (
        f"{len(failures)} public function(s) answer a quantity where a plain number belongs "
        "with something other than a ValueError:\n  " + "\n  ".join(sorted(failures)[:25])
    )


# --- The installed metadata is a snapshot, and the BOM is derived from it ---------------


def _requirements_by_extra(requirements):
    """``{extra or None: {requirement without its marker}}``, normalised for comparison."""
    grouped: dict[str | None, set[str]] = {}
    for requirement in requirements:
        head, _, marker = requirement.partition(";")
        extra = re.search(r"""extra\s*==\s*['"]([^'"]+)['"]""", marker)
        grouped.setdefault(extra.group(1) if extra else None, set()).add(head.strip())
    return grouped


def test_the_installed_metadata_still_says_what_pyproject_declares():
    """`EnvironmentBOM.of_this_environment()` reads the *installed* dependency list.

    `importlib.metadata.requires` does not read `pyproject.toml`. It reads the snapshot
    written into `.dist-info/METADATA` at install time, and an editable install — the shape
    every contributor here works in — does not rewrite that snapshot when the project's
    dependencies change. So a dependency added to `pyproject.toml` is invisible to the BOM
    until somebody reinstalls, and nothing says so.

    That is not hypothetical. This checkout sat with `export = ["ezdxf>=1.1"]` declared,
    ezdxf 1.4.4 installed and importable, `anvilate.export.dxf` able to write a DXF — and
    the attestation for that bundle naming only pint, pydantic and pyyaml. The provenance
    record was missing the library that wrote the artifact. The only thing that noticed was
    `test_dev_tooling_is_not_reported_as_having_produced_the_bundle`, which reads as an
    accusation against the BOM code and sends you into `attestation.py` rather than to
    `pip install`.

    Names *and* specifiers are compared, per extra, because setuptools copies each
    requirement through verbatim and only appends the marker. What this does **not** hold
    is the environment itself: a declared dependency can still be absent or at a version
    outside its own bound, and the BOM leaves an uninstalled one out by design.
    """
    import tomllib
    from importlib.metadata import PackageNotFoundError, requires

    with (_REPO / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    declared = {None: {r.strip() for r in project["dependencies"]}}
    for extra, entries in (project.get("optional-dependencies") or {}).items():
        declared[extra] = {r.strip() for r in entries}

    try:
        installed = _requirements_by_extra(requires("anvilate") or ())
    except PackageNotFoundError:  # pragma: no cover - anvilate is installed in every dev env
        pytest.fail("anvilate is not installed, so nothing can read a BOM off this environment")

    drift = []
    for extra in sorted(set(declared) | set(installed), key=lambda e: (e is not None, e or "")):
        where = "dependencies" if extra is None else f"optional-dependencies.{extra}"
        missing = sorted(declared.get(extra, set()) - installed.get(extra, set()))
        invented = sorted(installed.get(extra, set()) - declared.get(extra, set()))
        if missing:
            drift.append(f"{where}: declared but not in the installed metadata: {missing}")
        if invented:
            drift.append(f"{where}: in the installed metadata but no longer declared: {invented}")

    assert not drift, (
        "the installed distribution metadata has drifted from pyproject.toml, so every "
        "bill of materials this environment attests is derived from a stale dependency "
        "list:\n  " + "\n  ".join(drift) + "\n\nReinstall to refresh the snapshot:\n"
        "  pip install -e . --no-deps"
    )


def test_every_pytest_step_in_ci_counts_the_tests_it_actually_names():
    """`grep -qE "^N passed"` is what stops a scheduled job going green on a skip.

    It is also a hand-typed number sitting beside a hand-typed list of node ids, and the two
    drift in the direction that matters: add a test to the list, leave the count alone, and
    the step still passes while proving one fewer thing than it says. The scheduled job
    would catch it — a week later, in a run nobody is watching. This catches it here.

    The number is what pytest *collects*, which is not the length of the list: one of the
    node ids the fetch step names is parametrized and counts twice. So the ids are handed to
    a real collection rather than counted, which also settles whether each one still exists —
    pytest errors on a node id it cannot find, and a renamed test is the quieter half of
    this. Only steps that name their tests exactly are held; a `-k` step has no list.
    """
    import subprocess
    import sys

    workflow = (_REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    steps = re.findall(
        r"(?s)\n      - name: ([^\n]+)\n(.*?)(?=\n      - name: |\n\n  |\Z)", workflow
    )
    checked = []
    for name, body in steps:
        expected = re.search(r'grep -qE "\^(\d+) passed"', body)
        if expected is None:
            continue
        named = re.findall(r'"(tests/[\w/]+\.py::\w+)"', body)
        assert named, f"the {name!r} step counts passes but names no test to run"
        checked.append(name)
        collected = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header", *named],
            cwd=_REPO,
            capture_output=True,
            text=True,
        )
        assert collected.returncode == 0, (
            f"the {name!r} step names a test pytest cannot collect:\n{collected.stdout[-2000:]}"
        )
        counted = re.search(r"(\d+) tests? collected", collected.stdout)
        assert counted is not None, collected.stdout[-2000:]
        assert int(counted.group(1)) == int(expected.group(1)), (
            f"the {name!r} step collects {counted.group(1)} test(s) and requires "
            f"'{expected.group(1)} passed'; the difference is the number of checks it "
            "reports as run without running them"
        )

    assert len(checked) >= 2, (
        f"only {len(checked)} CI step(s) count their passes; this gate covers the steps "
        "that prove a scheduled job did not skip, and there are more than one"
    )


# --- the code a reader copies off a page ---------------------------------------------------
#
# 72 fenced Python blocks across `docs/`, and one of them did not parse. Most are excerpts
# that deliberately omit their imports, so executing them is not the bar; what is checkable
# without running anything is that they parse, that every anvilate symbol they import exists,
# and that every call they make is one the real signature accepts.

_PYTHON_FENCE = re.compile(r"```python\n(.*?)```", re.S)


def _documented_blocks():
    """Every fenced Python block in the repository's Markdown, as ``(label, source)``."""
    pages = [_REPO / "README.md", *sorted((_REPO / "docs").rglob("*.md"))]
    blocks = []
    for page in pages:
        if not page.exists():  # pragma: no cover - README and docs/ both ship
            continue
        text = page.read_text(encoding="utf-8")
        for index, block in enumerate(_PYTHON_FENCE.findall(text)):
            blocks.append((f"{page.relative_to(_REPO)}#{index}", block))
    assert len(blocks) > 50, f"only {len(blocks)} documented Python blocks were found"
    return blocks


def test_every_documented_python_block_parses():
    """`docs/reinforced-concrete.md` shipped a block a reader could not run at all.

    Its last line elided the arguments as `f(required_moment=..., ...)` — prose punctuation
    inside a call, and a positional argument after a keyword one, which is a `SyntaxError`.
    The figure it claimed was right and gated elsewhere; the code around it was not code.
    """
    broken = []
    for label, block in _documented_blocks():
        try:
            ast.parse(block)
        except SyntaxError as slip:
            broken.append(f"{label}: line {slip.lineno}: {slip.msg}")
    assert not broken, "documented Python that does not parse:\n  " + "\n  ".join(broken)


def _imported_anvilate_names(tree):
    """``{local name: object}`` for every anvilate symbol a block imports."""
    bound = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("anvilate"):
            module = importlib.import_module(node.module)
            for alias in node.names:
                bound[alias.asname or alias.name] = getattr(module, alias.name, None)
    return bound


def test_every_symbol_a_documented_block_imports_exists():
    """A rename leaves the page importing a name nothing answers to, and the page is where
    a reader starts. Held for the import itself, which is the line they copy first."""
    missing = []
    for label, block in _documented_blocks():
        try:
            tree = ast.parse(block)
        except SyntaxError:  # reported by the gate above
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not (node.module or "").startswith(
                "anvilate"
            ):
                continue
            try:
                module = importlib.import_module(node.module)
            except Exception as slip:  # noqa: BLE001 - the failure is the finding
                missing.append(f"{label}: import {node.module} -> {type(slip).__name__}")
                continue
            for alias in node.names:
                if not hasattr(module, alias.name):
                    missing.append(f"{label}: {node.module} has no {alias.name!r}")
    assert not missing, "documented imports that no longer resolve:\n  " + "\n  ".join(missing)


def test_every_documented_call_is_one_the_signature_accepts():
    """`docs/cold-formed-steel.md` told a reader to write `aisi_effective_width(...)`.

    It parses — `...` is a legal expression — and it raises `TypeError: takes 0 positional
    arguments but 1 was given`, because every analysis function here is keyword-only. Two
    pages carried that elision and a third carried the version that does not even parse.

    Only what a block *states* is checked, with `bind_partial`: an omitted required argument
    is how an excerpt is written, but a keyword the function does not take, or a positional
    where none is accepted, is a call that cannot work. Calls that splat (`*args`,
    `**kwargs`) are skipped — there is nothing to bind.
    """
    probed, wrong = 0, []
    for label, block in _documented_blocks():
        try:
            tree = ast.parse(block)
        except SyntaxError:  # reported by the gate above
            continue
        bound = _imported_anvilate_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            target = bound.get(node.func.id)
            if target is None or not callable(target):
                continue
            if any(isinstance(argument, ast.Starred) for argument in node.args):
                continue
            if any(keyword.arg is None for keyword in node.keywords):
                continue
            try:
                signature = inspect.signature(target)
            except (TypeError, ValueError):  # pragma: no cover - every target resolves today
                continue
            probed += 1
            marker = object()
            try:
                signature.bind_partial(
                    *[marker] * len(node.args),
                    **{keyword.arg: marker for keyword in node.keywords},
                )
            except TypeError as slip:
                wrong.append(f"{label}: {node.func.id}(...) at line {node.lineno}: {slip}")

    assert probed > 40, (
        f"only {probed} documented calls were checked against a signature; this gate covers "
        "the pages or it covers nothing"
    )
    assert not wrong, "documented calls the function would refuse:\n  " + "\n  ".join(wrong)


# --- the cross-references the library makes about itself ------------------------------------

_REST_REFERENCE = re.compile(r":(?:func|meth|class|mod|attr|data|exc):`~?(anvilate[\w.]*)`")


def _resolve_dotted(target: str):
    """``target`` as an object, or a string saying which step of it does not exist."""
    parts = target.split(".")
    module, rest = None, []
    for cut in range(len(parts), 0, -1):
        try:
            module = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            continue
        rest = parts[cut:]
        break
    if module is None:
        return f"no module in {target!r} imports"
    current = module
    for step in rest:
        # A pydantic field is not an attribute of its class — v2 strips them off — so a
        # reference to one has to be resolved through `model_fields` or every model
        # attribute in the package reads as missing. The first version of this walk said
        # `CrossSection.shear_form_factor` was gone; it is a field, and it is there.
        fields = getattr(current, "model_fields", None)
        if isinstance(fields, dict) and step in fields:
            current = fields[step]
            continue
        current = getattr(current, step, None)
        if current is None:
            return f"{target!r}: {step!r} does not exist"
    return None


def test_every_cross_reference_the_docstrings_make_resolves():
    """A `:func:` pointing at a symbol that moved is rot no manifest gate can see.

    `analysis/lifting_device.py` pointed at `anvilate.packs.screen_lifting_lug` from the
    paragraph explaining the one thing a generic lug check gets wrong — the sentence most
    worth following — and `screen_lifting_lug` lives in `anvilate.packs.structural`, which
    `anvilate.packs` does not re-export.

    Only the 799 module-qualified references are resolvable; the 1,424 bare ones
    (`` :func:`some_name` ``) name no module and Sphinx resolves them by context, so they
    are outside what this can hold.
    """
    broken, checked = [], 0
    for path in sorted((_REPO / "src" / "anvilate").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            docstring = ast.get_docstring(node)
            if not docstring:
                continue
            for target in _REST_REFERENCE.findall(docstring):
                checked += 1
                problem = _resolve_dotted(target)
                if problem is not None:
                    broken.append(f"{path.relative_to(_REPO)}: {problem}")

    assert checked > 700, (
        f"only {checked} qualified cross-references were resolved; this gate covers the "
        "docstrings or it covers nothing"
    )
    assert not broken, "docstring cross-references that no longer resolve:\n  " + "\n  ".join(
        broken
    )


def test_the_cross_reference_gate_sees_a_field_as_well_as_an_attribute():
    """The gate's own blind spot, closed and kept closed.

    `model_fields` is the only way to reach a pydantic field from its class, and a walk that
    used `getattr` alone reported every documented model attribute as missing — a false
    positive that would have been "fixed" by deleting a correct reference.
    """
    assert _resolve_dotted("anvilate.analysis.CrossSection.shear_form_factor") is None
    assert getattr(analysis_pkg.CrossSection, "shear_form_factor", None) is None, (
        "pydantic now exposes fields as class attributes; the model_fields branch above is "
        "no longer the only thing holding this and should say so"
    )
    assert _resolve_dotted("anvilate.analysis.CrossSection.no_such_field") is not None
    assert _resolve_dotted("anvilate.packs.screen_lifting_lug") is not None
    assert _resolve_dotted("anvilate.packs.structural.screen_lifting_lug") is None


def test_a_warning_is_an_error_and_nothing_is_excused_from_that():
    """A warning printed by a test run is a check nobody reads.

    Pydantic and pint both announce a removal one minor version before they make it, and a
    suite that prints those and goes green finds out on the upgrade. `filterwarnings =
    ["error"]` turns each into a failure — the whole suite passed under it once a single
    leaked socket in `test_air_gapped.py` was closed, so it costs nothing today.

    What this holds is the *absence of ignores*. An `ignore::DeprecationWarning` added to
    quiet one noisy dependency silences every other library's notice with it, which is the
    state this started from, reached by a shorter route.
    """
    import tomllib

    with (_REPO / "pyproject.toml").open("rb") as handle:
        configured = tomllib.load(handle)["tool"]["pytest"]["ini_options"].get("filterwarnings")
    assert configured, "pytest no longer turns warnings into errors"
    assert configured[0] == "error", f"the first filter is {configured[0]!r}, not 'error'"
    excused = [rule for rule in configured[1:] if rule.split(":", 1)[0] in {"ignore", "default"}]
    assert not excused, (
        f"warnings excused from the error filter: {excused}. An exemption belongs beside the "
        "reason it exists and the version that will remove it, not in a standing list"
    )


def test_every_rolled_up_verdict_survives_serialisation():
    """A `status` returning a `CheckStatus` is a verdict, and a verdict has to serialise.

    A plain `@property` is invisible to `model_dump`, and the dump is the document: the
    attested `scorecard.json`, the `scorecard` and `verification` blocks inside a signed
    predicate, `anvilate check --format json`, a rendered report's JSON. Every one of those
    went out as the checks with no verdict on them, leaving the reader to rebuild a roll-up
    that is **not** a maximum — an empty scorecard is NOT_EVALUATED, and the obvious
    reimplementation reports a pass over no checks.

    Keyed on the annotation, not on the name. `ExportAuthorization.status` is also a
    property called `status`, and it is a label -- `"VALIDATED"` off a boolean already in the
    document -- so a rule that swept it in on its name would be asking for a field nobody
    needs. It returns `str`, and that is what keeps it out.
    """
    import pkgutil

    from pydantic import BaseModel

    from anvilate.scorecard import CheckStatus

    plain, checked = [], 0
    seen: set[type] = set()
    for info in pkgutil.walk_packages(anvilate_pkg.__path__, "anvilate."):
        try:
            module = importlib.import_module(info.name)
        except Exception:  # pragma: no cover - an optional dependency is absent
            continue
        for value in vars(module).values():
            if not (isinstance(value, type) and issubclass(value, BaseModel)):
                continue
            if not value.__module__.startswith("anvilate") or value in seen:
                continue
            seen.add(value)
            prop = vars(value).get("status")
            if not isinstance(prop, property):
                continue
            if inspect.signature(prop.fget).return_annotation != CheckStatus.__name__:
                continue
            checked += 1
            if "status" not in (value.model_computed_fields or {}):
                plain.append(f"{value.__module__}.{value.__name__}")

    assert checked >= 8, (
        f"only {checked} rolled-up verdicts were found; this gate covers them or it covers nothing"
    )
    assert not plain, (
        "these roll up a verdict with a plain property, so every document they are dumped "
        "into carries the checks and not the conclusion:\n  " + "\n  ".join(sorted(plain))
    )


def test_a_serialised_verdict_cannot_be_asserted_into_a_document():
    """The other direction, and the reason `computed_field` is the right tool rather than a
    stored field. A document claiming a verdict its own checks contradict must lose."""
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    card = Scorecard(entries=(ScorecardEntry.from_safety_factor("b", computed=1.0, required=2.0),))
    dumped = card.model_dump(mode="json")
    assert dumped["status"] == "fail"
    assert Scorecard.model_validate({**dumped, "status": "pass"}).status is CheckStatus.FAIL


def test_the_repository_root_holds_only_files_that_belong_there():
    """The root is where regenerable output lands, because an example writes to its own
    working directory and a reader runs it from the checkout.

    Three artifacts had been committed that way. `position_callout.dxf` was rewritten by
    every run of the suite — its diff is a timestamp and two GUIDs — so it attached itself
    to whatever commit came next, in this repository's history four times running. Two more,
    `bundle.txt` and `docranges.json`, were a CLI redirect and an audit scratch file that
    nothing read.

    An allowlist rather than a pattern, because the failure is not "a DXF at the root": the
    two scratch files were a `.txt` and a `.json`, extensions no gate can ban. What the root
    of a repository holds is a short, deliberate list, and adding to it should be a diff.
    """
    import subprocess

    allowed = {
        ".gitignore",
        "AGENTS.md",
        "CLAUDE.md",
        "LICENSE",
        "README.md",
        "package-lock.json",
        "package.json",
        "pyproject.toml",
    }
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", ":(top)*"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    root_files = {name for name in tracked if name and "/" not in name}
    assert root_files, "git ls-files listed nothing; the gate is looking at an empty set"
    assert "pyproject.toml" in root_files, "the gate is not looking at this repository"
    assert root_files <= allowed, (
        "these are tracked at the repository root and are not on the list of files that "
        f"belong there: {sorted(root_files - allowed)}. If one is example output, add it to "
        ".gitignore and `git rm --cached` it; if it belongs, add it to the list above"
    )


# Field names that carry provenance: a citation, the source a number was read from, the
# licence it ships under, the identifier a record is looked up by. Two of them are exempt,
# and both default to `""` because for those a blank *is* the modelled absence.
_PROVENANCE_FIELDS = frozenset(
    {
        "citation",
        "source",
        "reference",
        "ref",
        "attribution",
        "license",
        "provenance",
        "standard",
        "edition",
        "identifier",
        "clause",
        "origin_detail",
        "spdx",
    }
)
_BLANK_MEANS_ABSENT = {
    ("Citation", "clause"): "a standard cited without a clause; the renderer drops it",
    ("ReviewItem", "origin_detail"): "no detail recorded about where the decision came from",
}


def _provenance_fields():
    """Every provenance-named string field on a model in the package, with its guard."""
    import importlib
    import inspect
    import pkgutil
    import types
    import typing

    from pydantic import BaseModel

    import anvilate

    def is_string(annotation) -> bool:
        if annotation is str:
            return True
        if typing.get_origin(annotation) in (types.UnionType, typing.Union):
            return set(typing.get_args(annotation)) == {str, type(None)}
        return False

    found, seen = [], set()
    for info in pkgutil.walk_packages(anvilate.__path__, "anvilate."):
        try:
            module = importlib.import_module(info.name)
        except Exception:  # pragma: no cover - an optional dependency, not a model
            continue
        for _, model in inspect.getmembers(module, inspect.isclass):
            if not issubclass(model, BaseModel) or model is BaseModel or model in seen:
                continue
            seen.add(model)
            for name, field in model.model_fields.items():
                if name not in _PROVENANCE_FIELDS or not is_string(field.annotation):
                    continue
                guarded = any(
                    getattr(getattr(meta, "func", None), "__anvilate_provenance__", False)
                    for meta in field.metadata
                )
                found.append((model, name, field, guarded))
    return found


def test_every_provenance_field_refuses_to_be_present_and_blank():
    """A citation that is the empty string is worse than a missing one.

    It reads as filled in every rendering and serialises as a citation nobody can follow:
    `Citation(standard="", edition="", clause="")` rendered as `"-"`, and a
    `LoadCombination(name="", factors={}, citation="")` printed as `": "`.

    Seven models already refused it — each with its own after-validator and its own sentence
    worth keeping — and thirty-two comparable fields had nothing at all, which is what a rule
    implemented seven times looks like from the outside. It is one rule now
    (`anvilate._models.cited`), the sentence stays per field, and this is the census that
    keeps a thirty-third from landing unguarded.

    A field whose absence is meaningful states that in its type — `cited(...) | None` — or
    is exempt below with the reason a blank is its own answer.
    """
    fields = _provenance_fields()
    # Thirty-eight today. The floor is here so a broken census reports "nothing to
    # check" as a failure rather than as a pass.
    assert len(fields) >= 35, f"the census found only {len(fields)} provenance fields"

    unguarded = sorted(
        f"{model.__module__}.{model.__name__}.{name}"
        for model, name, _field, guarded in fields
        if not guarded and (model.__name__, name) not in _BLANK_MEANS_ABSENT
    )
    assert not unguarded, (
        "these carry provenance and accept a blank string:\n  "
        + "\n  ".join(unguarded)
        + "\nDeclare them with anvilate._models.cited(...), or add them to "
        "_BLANK_MEANS_ABSENT with the reason a blank is their answer."
    )

    for model, name, field, guarded in fields:
        if (model.__name__, name) not in _BLANK_MEANS_ABSENT:
            continue
        assert not guarded, f"{model.__name__}.{name} is guarded; drop its exemption"
        assert field.default == "", (
            f"{model.__name__}.{name} is exempt as 'blank means absent' and does not "
            f"default to blank; it defaults to {field.default!r}"
        )
    stale = sorted(
        f"{cls}.{name}"
        for cls, name in _BLANK_MEANS_ABSENT
        if not any(model.__name__ == cls and field == name for model, field, _f, _g in fields)
    )
    assert not stale, f"exempted fields that no longer exist: {stale}"


@pytest.mark.parametrize(
    ("factory", "blank"),
    [(lambda: __import__("anvilate.loads", fromlist=["x"]).LoadCombination, "  ")],
)
def test_the_provenance_guard_actually_refuses(factory, blank):
    """The census above checks a marker; this checks that the marker means something.

    A gate that asserts an annotation and never constructs anything is satisfied by a
    decoration that does nothing.
    """
    import pydantic

    model = factory()
    with pytest.raises(pydantic.ValidationError, match="must state"):
        model(name="LRFD 1", factors={"D": 1.4}, citation=blank)
    assert model(name="LRFD 1", factors={"D": 1.4}, citation="ASCE 7-22 §2.3.1").citation


def test_every_change_delta_names_a_requirement_the_archive_can_merge():
    """A change that cannot be archived is a change that fails when the work is done.

    `openspec validate --strict` passes a delta whose `## MODIFIED Requirements` names a
    requirement the capability has never had; the mismatch surfaces only at `openspec
    archive`, which refuses with "not found" and changes nothing. That is exactly what
    happened to `declare-the-spec-element-type`: its element requirement was written as
    MODIFIED, `spec-ir` had never carried one, and the refusal came months later when
    somebody tried to file the finished work.

    So the check is the archive's own rule, run early: a MODIFIED, REMOVED or RENAMED header
    must name a requirement the capability has, and an ADDED one must not.
    """
    import re

    problems = []
    for delta in sorted((_REPO / "openspec" / "changes").glob("*/specs/*/spec.md")):
        if "archive" in delta.parts:
            continue
        capability = delta.parent.name
        target = _REPO / "openspec" / "specs" / capability / "spec.md"
        existing = (
            set(re.findall(r"^### Requirement: (.+)$", target.read_text(), re.M))
            if target.exists()
            else set()
        )
        change = delta.parent.parent.parent.name
        section = None
        for line in delta.read_text().splitlines():
            header = re.match(r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements", line)
            if header:
                section = header.group(1)
                continue
            named = re.match(r"^### Requirement: (.+)$", line)
            if not named or section is None:
                continue
            requirement = named.group(1).strip()
            if section != "ADDED" and requirement not in existing:
                problems.append(
                    f"{change}: {section} '{requirement}' is not in specs/{capability}; "
                    "the archive would refuse it"
                )
            if section == "ADDED" and requirement in existing:
                problems.append(
                    f"{change}: ADDED '{requirement}' already exists in specs/{capability}"
                )
    assert not problems, "change deltas the archive would refuse:\n  " + "\n  ".join(problems)


def test_the_delta_gate_is_looking_at_real_deltas():
    """The gate above passes trivially if it finds no deltas — which is how a path typo in a
    glob reads from the outside."""
    deltas = [
        path
        for path in (_REPO / "openspec" / "changes").glob("*/specs/*/spec.md")
        if "archive" not in path.parts
    ]
    assert len(deltas) >= 5, f"only {len(deltas)} change deltas found; the glob has moved"


def test_every_name_field_refuses_a_blank():
    """A blank name is a blank citation seen from the other side.

    The field reads as filled and every rendering downstream prints an entry, a record or a
    check with nothing where its name goes: `[FAIL]    : safety factor 0.8` is a scorecard
    line a reader cannot act on, and `governing()` names it as the check to look at. Four
    models refused it and thirty-nine did not, which is the same split the provenance census
    found one field-name over.

    Held by the marker `anvilate._models.cited` attaches, so a model that writes its own
    validator instead is listed as an exemption with the reason rather than silently passing.
    """
    import importlib
    import inspect
    import pkgutil

    from pydantic import BaseModel

    import anvilate

    own_validator = {
        "Component": "a BOM component names its own rule about the subject line",
        "Subject": "an attestation subject names its own rule about the subject line",
        "Parameter": "an explore parameter says what a blank sweep axis would mean",
        "FatigueRecord": "a fatigue record refuses several blanks in one message",
    }
    unguarded, seen = [], set()
    for info in pkgutil.walk_packages(anvilate.__path__, "anvilate."):
        try:
            module = importlib.import_module(info.name)
        except Exception:  # pragma: no cover - an optional dependency, not a model
            continue
        for _, model in inspect.getmembers(module, inspect.isclass):
            if not issubclass(model, BaseModel) or model is BaseModel or model in seen:
                continue
            seen.add(model)
            field = model.model_fields.get("name")
            if field is None or field.annotation is not str:
                continue
            guarded = any(
                getattr(getattr(meta, "func", None), "__anvilate_provenance__", False)
                for meta in field.metadata
            )
            if not guarded and model.__name__ not in own_validator:
                unguarded.append(f"{model.__module__}.{model.__name__}")
    assert len(seen) > 100, f"the census walked only {len(seen)} models"
    assert not unguarded, (
        "these accept a blank name, which renders as an unnamed one:\n  "
        + "\n  ".join(sorted(unguarded))
        + "\nDeclare it as anvilate._models.Named, or add the model to the exemptions above "
        "with the reason its own validator is better."
    )


def test_every_capability_spec_is_one_openspec_would_accept():
    """`openspec validate --specs --strict` is not in CI, and CI is where a broken spec would
    be caught.

    The tool needs node; this needs nothing, and it holds the rule whose breakage is
    realistic: a requirement added with no scenario. That is what an archive merge carries
    into the spec when a change delta is written in a hurry, and it is exactly what strict
    mode refuses — confirmed by making the edit against a copy of this tree and watching the
    tool fail on it.
    """
    import re

    specs = sorted((_REPO / "openspec" / "specs").glob("*/spec.md"))
    assert len(specs) >= 25, f"only {len(specs)} capability specs found; the glob has moved"

    problems = []
    for spec in specs:
        capability = spec.parent.name
        text = spec.read_text()
        blocks = re.split(r"^### Requirement: ", text, flags=re.MULTILINE)[1:]
        if not blocks:
            problems.append(f"{capability}: no requirements")
            continue
        names = [block.splitlines()[0].strip() for block in blocks]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            problems.append(f"{capability}: two requirements share a name: {duplicates}")
        for name, block in zip(names, blocks, strict=True):
            scenarios = re.split(r"^#### Scenario: ", block, flags=re.MULTILINE)[1:]
            if not scenarios:
                problems.append(f"{capability}: requirement {name!r} demonstrates nothing")
                continue
            for scenario in scenarios:
                title = scenario.splitlines()[0].strip()
                body = scenario[: scenario.find("\n###")] if "\n###" in scenario else scenario
                if "**WHEN**" not in body or "**THEN**" not in body:
                    problems.append(
                        f"{capability}: scenario {title!r} under {name!r} has no WHEN/THEN"
                    )
    assert not problems, "capability specs openspec would refuse:\n  " + "\n  ".join(problems)


def test_every_relative_link_in_the_docs_resolves():
    """A 404 is the way a reader meets a file that moved.

    The docs index has a gate holding its entries against the pages that ship, and every
    other link in the tree — a page pointing at an example, a module, an openspec change,
    another page — had none. There are hundreds of them and they are exactly the kind of
    thing a rename breaks silently.
    """
    import re

    pages = [
        *sorted((_REPO / "docs").rglob("*.md")),
        _REPO / "README.md",
        _REPO / "AGENTS.md",
        _REPO / "examples" / "README.md",
    ]
    checked, broken = 0, []
    for page in pages:
        if not page.exists():  # pragma: no cover - all three ship
            continue
        for target in re.findall(r"\]\(([^)#]+?)(?:#[^)]*)?\)", page.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            checked += 1
            if not (page.parent / target).resolve().exists():
                broken.append(f"{page.relative_to(_REPO)} -> {target}")
    assert checked >= 100, f"only {checked} relative links found; the pattern has moved"
    assert not broken, "links to files that do not exist:\n  " + "\n  ".join(broken)


def test_every_repository_path_the_source_names_exists():
    """A refusal that points a reader at a file is only useful while the file is there.

    Archiving a completed change moves it under `openspec/changes/archive/<date>-<name>/`,
    which broke two comments the same afternoon the change landed — one of them in the module
    docstring of a module written that hour. The docs have a link gate; the source, whose
    messages a *user* reads out of a refused MCP call, had none.
    """
    import re

    pattern = re.compile(
        r"(openspec/(?:specs|changes)/[a-z0-9/-]+(?:\.md)?|src/anvilate/[a-z_/]+\.py"
        r"|docs/[a-z0-9-]+\.md|examples/[a-z0-9_]+\.py|tests/[a-z0-9_]+\.py)"
    )
    named, missing = 0, []
    for path in sorted((_REPO / "src" / "anvilate").rglob("*.py")):
        for target in sorted(set(pattern.findall(path.read_text(encoding="utf-8")))):
            named += 1
            if not (_REPO / target).exists():
                missing.append(f"{path.relative_to(_REPO)} names {target}")
    assert named >= 10, f"only {named} repository paths found in src/; the pattern has moved"
    assert not missing, "the source names paths that do not exist:\n  " + "\n  ".join(missing)


def test_every_repository_path_the_specs_name_exists():
    """The same rule for `openspec/`, where ninety-odd paths name modules, tests and examples.

    A proposal that argues from `src/anvilate/screening.py` and a spec whose scenario names an
    example are both claims about this tree, and a rename leaves them reading as right as
    ever. The archive is included on purpose: a completed change is the record of why the code
    looks like this, and a record pointing at files that moved is worth less than one that
    does not.
    """
    import re

    pattern = re.compile(
        r"(src/anvilate/[a-z_/]+\.py|tests/[a-z0-9_]+\.py|examples/[a-z0-9_]+\.py"
        r"|docs/[a-z0-9-]+\.md)"
    )
    named, missing = 0, []
    for path in sorted((_REPO / "openspec").rglob("*.md")):
        for target in sorted(set(pattern.findall(path.read_text(encoding="utf-8")))):
            named += 1
            if not (_REPO / target).exists():
                missing.append(f"{path.relative_to(_REPO)} names {target}")
    assert named >= 50, f"only {named} repository paths found in openspec/; the pattern moved"
    assert not missing, "the specs name paths that do not exist:\n  " + "\n  ".join(missing)


# --- the derivation-coverage ratchet ---------------------------------------------------
#
# The gate itself lives in tests/conftest.py, because only a running suite can see which
# checks build a derivation. These hold the gate: that the registry is well formed, that
# each of the four rules fires on the case it exists for, and that the collector is
# actually collecting — a ratchet whose collector silently stopped would report perfect
# agreement with a registry it never looked at.


def _registry():
    import conftest

    return conftest._read_registry()


def test_the_underived_registry_is_well_formed():
    """Both sections populated, every line reasoned, no clause filed twice.

    A clause on both lists would be read as whichever the parser saw last, which is the
    collapse of the two categories that the requirement forbids — arrived at by accident
    rather than by decision.
    """
    import conftest

    text = conftest._REGISTRY.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    sections = [line for line in lines if line.startswith("[")]
    assert sections == ["[lookup]", "[debt]"], sections

    seen: dict[str, str] = {}
    duplicates: list[str] = []
    section = ""
    for line in lines:
        if line.startswith("["):
            section = line[1:-1]
            continue
        clause, separator, reason = line.partition(" :: ")
        assert separator and reason.strip(), f"no stated reason: {line}"
        if clause in seen:
            duplicates.append(f"{clause} (in {seen[clause]} and {section})")
        seen[clause] = section
    assert not duplicates, "clauses filed twice:\n  " + "\n  ".join(duplicates)

    registry = _registry()
    assert sum(1 for s, _ in registry.values() if s == "lookup") >= 1
    assert sum(1 for s, _ in registry.values() if s == "debt") >= 10, (
        "the debt list has emptied out; either the derivations were written or the "
        "collector stopped seeing the checks that need them"
    )


def test_each_coverage_rule_fires_on_the_case_it_exists_for():
    """The probe table. Every rule is exercised against the shape it is meant to catch,
    and against the neighbouring shape it must not.

    Written as data rather than as a list of clause names, because a gate that is a set of
    names is satisfied by adding a name.
    """
    import conftest

    registry = {
        "Cited Std §1": ("debt", "the formula is unwritten"),
        "Cited Std §2": ("lookup", "a table, no formula"),
    }
    # (coverage, how many failures, a fragment of the message)
    probes = [
        # derived, evaluated, safety-factor-carrying
        ({"Cited Std §1": (0, 4, 4)}, 0, ""),  # debt, still owed: quiet
        ({"Cited Std §1": (3, 4, 4)}, 0, ""),  # debt, part paid: still quiet
        ({"Cited Std §1": (4, 4, 4)}, 0, ""),  # paid off — but that reads an absence
        ({"Cited Std §2": (0, 4, 0)}, 0, ""),  # a lookup as declared: quiet
        ({"Cited Std §2": (1, 4, 0)}, 1, "formula to render after all"),
        ({"Cited Std §2": (0, 4, 2)}, 1, "quotient is a formula"),
        ({"Unlisted §9": (0, 3, 3)}, 1, "on neither list"),
        ({"Unlisted §9": (3, 3, 3)}, 0, ""),  # fully derived: never needs a line
    ]
    for coverage, expected, fragment in probes:
        failures = conftest._coverage_failures(coverage, registry)
        assert len(failures) == expected, f"{coverage} gave {failures}"
        if fragment:
            assert fragment in failures[0], failures[0]

    # The two rules that read an ABSENCE are held apart, because only a full run may act
    # on them: on a filtered run "no underived entry left" and "that test did not run"
    # look exactly alike.
    assert conftest._paid_off_debts({"Cited Std §1": (4, 4, 4)}, registry) == ["Cited Std §1"]
    assert conftest._paid_off_debts({"Cited Std §1": (3, 4, 4)}, registry) == []
    assert conftest._paid_off_debts({"Cited Std §2": (0, 4, 0)}, registry) == []
    assert conftest._stale_registry_lines({"Cited Std §1": (0, 1, 1)}, registry) == ["Cited Std §2"]
    assert conftest._derivation_coverage_ratio(
        {"a": (2, 2, 0), "b": (1, 2, 0), "c": (0, 2, 0)}
    ) == (1, 3)


def test_the_coverage_collector_is_collecting():
    """A live probe: run a real screen, and look for its clause in the census.

    The failure this exists to catch is the quiet one — the collector uninstalled, or the
    library building entries by a route it does not watch — which leaves the registry
    agreeing perfectly with an empty observation.
    """
    import conftest

    entries = _structural_entries()
    assert entries, "the structural pack produced no entries to observe"

    coverage = conftest._observed_coverage()
    cited = {entry.reference for entry in entries if entry.reference}
    # Self-calibrating rather than a threshold: what the pack just cited is what the
    # collector has to have. The count below only keeps the probe itself from going
    # vacuous if the pack stops citing anything.
    assert len(cited) >= 5, f"the structural pack cited only {len(cited)} clauses"
    unseen = sorted(cited - set(coverage))
    assert not unseen, (
        "these clauses were just produced by the structural pack and the collector did "
        "not record them:\n  " + "\n  ".join(unseen)
    )

    # And it is recording the derivation, not just the citation: the structural pack
    # writes worked calculations, so some clause it just cited has to come back covered.
    # (How many clauses are *un*covered depends on which tests ran, so it is not asserted
    # here — the probe table above is what holds the uncovered rules.)
    assert any(coverage[clause][0] == coverage[clause][1] for clause in cited)


def test_the_calculation_report_page_counts_the_registry_it_describes():
    """The three numbers docs/calculation-reports.md quotes, held against the file.

    A count in prose expires silently: the page said which packs declared derivations and
    which did not, and nothing checked it. These are tied to the registry instead — the
    section sizes directly, and the ratio through the identity that every cited clause is
    either fully worked or has a line.
    """
    registry = _registry()
    page = (_REPO / "docs" / "calculation-reports.md").read_text(encoding="utf-8")

    worked, cited = (int(n) for n in re.search(r"\*\*(\d+) of (\d+) cited clauses", page).groups())
    assert cited - worked == len(registry), (
        f"the page claims {worked} of {cited} clauses worked, which leaves "
        f"{cited - worked} needing a line; the registry has {len(registry)}"
    )

    for section, claimed in re.findall(r"\| `\[(\w+)\]` \|[^|]+\| (\d+) \|", page):
        actual = sum(1 for listed, _ in registry.values() if listed == section)
        assert actual == int(claimed), (
            f"the page says [{section}] has {claimed} lines; it has {actual}"
        )
    assert len(re.findall(r"\| `\[(\w+)\]` \|", page)) == 2, "the section table moved"


def test_the_coverage_gate_counts_what_the_report_would_render():
    """A derivation the document refuses to show as worked is not coverage.

    `Derivation.unresolved_symbols` exists because a formula naming a symbol it never
    declares renders with a bare symbol where a number belongs; `ReportSection.is_worked`
    is where the report acts on it and falls back to the inputs table. The coverage gate
    counted the derivation's *presence*, so such a check would have been reported as
    covered while every rendering of it showed a table — the hidden gap, arrived at from
    the other side.
    """
    import conftest
    from anvilate.derivation import Derivation, SymbolValue
    from anvilate.report import ReportSection
    from anvilate.scorecard import CheckStatus, ScorecardEntry
    from anvilate.units import Quantity

    def entry_with(symbolic: str) -> ScorecardEntry:
        return ScorecardEntry(
            name="probe",
            status=CheckStatus.PASS,
            detail="",
            reference="Probe Std §1",
            derivation=Derivation(
                symbolic=symbolic,
                inputs=(
                    SymbolValue(symbol="P", description="declared", value=Quantity.parse("1 kN")),
                ),
                result=SymbolValue(symbol="σ", description="out", value=Quantity.parse("1 MPa")),
                citation="Probe Std §1",
            ),
        )

    complete = entry_with("σ = P")
    incomplete = entry_with("σ = P / A")  # A is never declared

    assert conftest._counts_as_worked(complete)
    assert not conftest._counts_as_worked(incomplete)
    # No derivation at all is the third case, and it is not worked either.
    assert not conftest._counts_as_worked(
        ScorecardEntry(name="probe", status=CheckStatus.PASS, detail="")
    )

    # And the condition is the report's own, not a second opinion about it.
    for entry in (complete, incomplete):
        assert conftest._counts_as_worked(entry) is ReportSection(entry=entry).is_worked
