"""Module manifests, held against the packs they describe rather than trusted."""

from __future__ import annotations

import importlib
import pkgutil

import pytest
from pydantic import ValidationError

from anvilate.modules import (
    MODULE_MANIFESTS,
    Deprecation,
    ModuleManifest,
    ModuleRegistry,
    manifest_for,
)
from anvilate.spec import ValidationTier
from anvilate.units import UnitSystem


def _shipped_packs() -> dict[str, tuple[str, ...]]:
    """Every pack module and the screens it exports, read off the package.

    Derived the way `element_registry` derives them, so a pack that ships a screen is a
    pack this census sees — a hand-written list here would go stale in the one direction
    the gate exists to catch.
    """
    import anvilate.packs as packs

    found = {}
    for info in pkgutil.iter_modules(packs.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"anvilate.packs.{info.name}")
        found[info.name] = tuple(
            sorted(name for name in getattr(module, "__all__", ()) if name.startswith("screen_"))
        )
    return found


def _manifest(**fields: object) -> ModuleManifest:
    declared: dict[str, object] = {
        "id": "example",
        "version": "1.0.0",
        "unit_default": UnitSystem.SI,
        "tiers": (ValidationTier.T1_ANALYTICAL,),
        "screens": ("screen_example",),
        "summary": "an example module, for the tests below",
    }
    declared.update(fields)
    return ModuleManifest(**declared)  # type: ignore[arg-type]


def test_every_shipped_pack_has_a_manifest_and_every_manifest_a_pack() -> None:
    packs = _shipped_packs()
    assert len(packs) >= 10, f"the census found only {len(packs)} packs"
    declared = {manifest.id for manifest in MODULE_MANIFESTS.manifests}
    missing = sorted(set(packs) - declared)
    assert not missing, (
        f"these packs ship screens and declare no manifest: {missing}. A module nobody "
        "declared is one a caller cannot version, cite or depend on."
    )
    invented = sorted(declared - set(packs))
    assert not invented, f"these manifests describe packs this build does not ship: {invented}"


def test_a_manifest_names_the_screens_its_pack_actually_exports() -> None:
    packs = _shipped_packs()
    drift = []
    for manifest in MODULE_MANIFESTS.manifests:
        actual = packs[manifest.id]
        if tuple(sorted(manifest.screens)) != actual:
            missing = sorted(set(actual) - set(manifest.screens))
            invented = sorted(set(manifest.screens) - set(actual))
            drift.append(f"{manifest.id}: undeclared {missing}, declared-but-absent {invented}")
    assert not drift, (
        "these manifests do not describe the pack they name — a screen a pack ships and its "
        f"manifest omits is one nothing can attribute: {drift}"
    )
    # The floor: the gate is reading real screens, not an empty set on both sides.
    assert sum(len(manifest.screens) for manifest in MODULE_MANIFESTS.manifests) >= 25


def test_every_manifest_says_what_the_module_is_for() -> None:
    for manifest in MODULE_MANIFESTS.manifests:
        assert len(manifest.summary.split()) >= 6, f"{manifest.id} summarises itself in a phrase"
        assert manifest.tiers, f"{manifest.id} touches no pipeline tier"


def test_a_standard_a_manifest_declares_is_one_the_library_knows() -> None:
    """A body nothing recognises cannot be resolved, cited or held to an edition."""
    from anvilate.standards.effectivity import STANDARDS_BODIES

    for manifest in MODULE_MANIFESTS.manifests:
        unknown = sorted(set(manifest.standards) - set(STANDARDS_BODIES))
        assert not unknown, f"{manifest.id} declares {unknown}, which no standards body matches"
    # And the declaration is not vacuous across the registry: most packs cite something.
    citing = [manifest for manifest in MODULE_MANIFESTS.manifests if manifest.standards]
    assert len(citing) >= 6, f"only {len(citing)} modules declare a standard; the field is idle"


def test_the_registry_refuses_two_modules_with_one_id() -> None:
    with pytest.raises(ValidationError, match="two modules claim the same id"):
        ModuleRegistry(manifests=(_manifest(), _manifest(summary="a second module of one name")))


def test_a_dependency_on_a_module_this_build_does_not_carry_is_refused() -> None:
    with pytest.raises(ValidationError, match=r"depends on \['nowhere'\]"):
        ModuleRegistry(manifests=(_manifest(depends_on=("nowhere",)),))
    # A dependency that resolves is accepted, and a self-dependency never is.
    pair = ModuleRegistry(
        manifests=(_manifest(id="base"), _manifest(id="upper", depends_on=("base",)))
    )
    assert len(pair) == 2
    with pytest.raises(ValidationError, match="depends on itself"):
        _manifest(id="base", depends_on=("base",))


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"screens": ()}, "at least 1 item"),
        ({"tiers": ()}, "at least 1 item"),
        ({"screens": ("compute_thing",)}, "names screens"),
        ({"standards": ("AISC", "AISC")}, "names one standards twice"),
        ({"screens": ("screen_a", "screen_a")}, "names one screens twice"),
        ({"summary": "   "}, "must state"),
        ({"id": ""}, "must state"),
    ],
)
def test_a_malformed_manifest_is_refused(fields: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _manifest(**fields)


def test_manifest_for_names_what_this_build_ships_when_asked_for_something_else() -> None:
    assert manifest_for("structural").id == "structural"
    with pytest.raises(ValueError, match="no discipline module 'optomechanical'"):
        manifest_for("optomechanical")


def test_a_deprecated_module_renders_its_replacement_wherever_it_appears() -> None:
    going = _manifest(
        deprecated=Deprecation(
            since="1.4.0", removed_in="2.0.0", use_instead="anvilate.packs.structural"
        )
    )
    rendered = str(going)
    assert "deprecated since 1.4.0, removed in 2.0.0" in rendered
    assert "use anvilate.packs.structural" in rendered
    # And a live module says nothing about deprecation at all.
    assert "deprecated" not in str(_manifest())


def test_the_registry_renders_every_module_it_carries() -> None:
    lines = str(MODULE_MANIFESTS).splitlines()
    assert lines[0] == f"{len(MODULE_MANIFESTS.manifests)} discipline modules"
    assert len(lines) == 1 + len(MODULE_MANIFESTS.manifests)
    assert any("structural 1.0.0: 12 screens, AISC, ACI, ASME" in line for line in lines)
    assert str(ModuleRegistry()) == "no discipline modules"


def test_a_registry_round_trips_through_its_own_serialization() -> None:
    assert ModuleRegistry.model_validate_json(MODULE_MANIFESTS.model_dump_json()) == (
        MODULE_MANIFESTS
    )


def test_the_exercise_gate_reads_what_the_suite_actually_ran() -> None:
    """The collector behind the MODULE EXERCISE gate, exercised in both directions.

    The gate itself only fires at the end of a clean full run — it reads an absence — so
    its helper is tested here, where a wrong answer in either direction is visible.
    """
    import conftest

    saved = set(conftest._screens_run)
    try:
        conftest._screens_run.clear()
        every = conftest._unexercised_screens()
        assert len(every) == conftest._declared_screen_count() >= 25
        assert "structural.screen_lifting_lug" in every
        conftest._screens_run.update(every)
        assert conftest._unexercised_screens() == []
    finally:
        conftest._screens_run.clear()
        conftest._screens_run.update(saved)


def test_a_screen_that_composes_others_is_recorded_as_run() -> None:
    """`screen_structure` builds no entry of its own — it dispatches to member screens.

    The collector records every screen frame on the stack rather than the nearest one, so
    the one screen that composes the others is not reported as the one nobody runs. With a
    nearest-frame detector it was exactly that: the single unexercised screen of the 29.
    """
    import sys

    import conftest

    sys.path.insert(0, str(conftest.Path(__file__).parent))
    from anvilate.packs.structural import LoadType, Support, screen_structure
    from test_structural import _column, _member  # the suite's own members

    saved = set(conftest._screens_run)
    try:
        conftest._screens_run.clear()
        screen_structure(
            [_member(Support.SIMPLY_SUPPORTED, LoadType.POINT, "100 N"), _column("500 mm")],
            required_safety_factor=2.0,
        )
        assert "structural.screen_structure" in conftest._screens_run
        assert "structural.screen_beam_member" in conftest._screens_run
    finally:
        conftest._screens_run.clear()
        conftest._screens_run.update(saved)
