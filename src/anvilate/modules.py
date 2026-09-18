"""What a discipline module declares about itself, so a tenth domain is a manifest.

Nine disciplines sit on a domain-neutral foundation — units, the Spec IR, the scorecard, the
citation doctrine, the evidence bundle — and adding a tenth used to mean editing the shared
pack specification. The blocker was spec shape, not capability: the contract never had to
answer what a module declares about itself, what it may depend on, which standards it is
written against, or what stops it shipping checks nothing exercises.

A :class:`ModuleManifest` is those answers as data: a stable id, its version, the unit
system its figures are written in, the standards bodies it cites, the material property
sets its screens need, the pipeline tiers it touches, the modules it depends on, and the
screens it exports. :data:`MODULE_MANIFESTS` carries one per
shipped pack.

**The manifest is held against the pack, not trusted.** `tests/test_modules.py` derives the
screens each pack actually exports and fails a manifest that names a different set, and refuses a
pack with no manifest or a manifest for no pack. A manifest that could drift from the module
it describes would be documentation with a type annotation on it.

The spec this implements also asks a module to reserve a *check-name namespace*. That field
is not here, because nothing in this library could hold a pack to it today: a check is named
after the element instance that produced it (``col_base plate bending``), not after the
module, so a declared namespace would be a string no gate could check. It arrives with the
naming change that makes it true, not before.

A deprecated module says so in its manifest, with the version it goes away in and what to use
instead, so a caller reading a scorecard from it is told at the source rather than by a
release note nobody reads.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import ConfigDict, Field, model_validator

from ._models import ItemCollection, Named, Provenance, StatableModel
from .spec import ValidationTier
from .units import UnitSystem

__all__ = [
    "Deprecation",
    "ModuleManifest",
    "ModuleRegistry",
    "MODULE_MANIFESTS",
    "LoadedModules",
    "manifest_for",
    "load_modules",
]


class Deprecation(StatableModel):
    """A module on its way out: when it goes, and what replaces it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    since: Named
    removed_in: Named
    use_instead: Provenance

    def __str__(self) -> str:
        return (
            f"deprecated since {self.since}, removed in {self.removed_in}; use {self.use_instead}"
        )


class ModuleManifest(StatableModel):
    """What one discipline module declares about itself."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    version: Named
    unit_default: UnitSystem
    standards: tuple[Named, ...] = ()
    material_properties: tuple[Named, ...] = ()
    tiers: tuple[ValidationTier, ...] = Field(min_length=1)
    depends_on: tuple[Named, ...] = ()
    screens: tuple[Named, ...] = Field(min_length=1)
    # What a document may declare and have this module screen: the `element_type` tags its
    # screens are selected by. A document naming a tag no enabled module covers is told so,
    # naming the modules — which is what makes a missing module a reported gap rather than
    # a screen that quietly did not run.
    covers: tuple[Named, ...] = Field(min_length=1)
    summary: Provenance
    deprecated: Deprecation | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> ModuleManifest:
        for field, values in (
            ("standards", self.standards),
            ("material_properties", self.material_properties),
            ("tiers", self.tiers),
            ("depends_on", self.depends_on),
            ("screens", self.screens),
            ("covers", self.covers),
        ):
            listed = [str(value) for value in values]
            if len(set(listed)) != len(listed):
                raise ValueError(f"module '{self.id}' names one {field} twice: {sorted(listed)}")
        if self.id in self.depends_on:
            raise ValueError(f"module '{self.id}' depends on itself")
        if not all(screen.startswith("screen_") for screen in self.screens):
            raise ValueError(
                f"module '{self.id}' names screens {sorted(self.screens)}; a pack's screens are "
                "the `screen_*` functions the element registry selects, and a name outside that "
                "shape is one no document can reach"
            )
        return self

    def __str__(self) -> str:
        state = f" [{self.deprecated}]" if self.deprecated is not None else ""
        standards = ", ".join(self.standards) if self.standards else "no cited standards"
        return f"{self.id} {self.version}: {len(self.screens)} screens, {standards}{state}"


class ModuleRegistry(ItemCollection, StatableModel):
    """Every module manifest this build ships, with no two claiming one id or namespace."""

    model_config = ConfigDict(frozen=True)

    manifests: tuple[ModuleManifest, ...] = ()

    @model_validator(mode="after")
    def _distinct(self) -> ModuleRegistry:
        for field in ("id",):
            claimed = [getattr(manifest, field) for manifest in self.manifests]
            if len(set(claimed)) != len(claimed):
                doubled = sorted({name for name in claimed if claimed.count(name) > 1})
                raise ValueError(
                    f"two modules claim the same {field}: {doubled}; a check name that two "
                    "modules could own is one no reader can attribute"
                )
        known = {manifest.id for manifest in self.manifests}
        for manifest in self.manifests:
            missing = sorted(set(manifest.depends_on) - known)
            if missing:
                raise ValueError(
                    f"module '{manifest.id}' depends on {missing}, which this build does not "
                    "carry; a dependency nobody loads is a screen that cannot run"
                )
        return self

    def __str__(self) -> str:
        if not self.manifests:
            return "no discipline modules"
        lines = [f"{len(self.manifests)} discipline modules"]
        lines += [f"  {manifest}" for manifest in sorted(self.manifests, key=lambda m: m.id)]
        return "\n".join(lines)


def _manifest(
    identifier: str,
    *,
    screens: tuple[str, ...],
    covers: tuple[str, ...],
    summary: str,
    standards: tuple[str, ...] = (),
    material_properties: tuple[str, ...] = (),
    tiers: tuple[ValidationTier, ...] = (ValidationTier.T1_ANALYTICAL,),
    unit_default: UnitSystem = UnitSystem.SI,
) -> ModuleManifest:
    return ModuleManifest(
        id=identifier,
        version="1.0.0",
        unit_default=unit_default,
        standards=standards,
        material_properties=material_properties,
        tiers=tiers,
        screens=screens,
        covers=covers,
        summary=summary,
    )


#: One manifest per shipped pack. The screens are held against what each pack exports by the
#: gate in `tests/test_modules.py`, so this list cannot drift into describing a pack that has
#: moved on without it.
MODULE_MANIFESTS = ModuleRegistry(
    manifests=(
        _manifest(
            "electrical",
            covers=("feeder",),
            screens=("screen_feeder",),
            standards=("NEC",),
            summary="branch and feeder circuits: conductor ampacity, voltage drop, breaker size",
        ),
        _manifest(
            "geotechnical",
            covers=(
                "driven_pile",
                "infinite_slope",
                "retaining_wall",
                "shallow_footing",
            ),
            screens=(
                "screen_driven_pile",
                "screen_infinite_slope",
                "screen_retaining_wall",
                "screen_shallow_footing",
            ),
            material_properties=("soil unit weight", "friction angle", "cohesion"),
            summary="soil-bearing elements: shallow footings, driven piles, walls and slopes",
        ),
        _manifest(
            "hydraulics",
            covers=(
                "pipe_run",
                "pump_duty",
            ),
            screens=(
                "screen_pipe_run",
                "screen_pump_duty",
            ),
            material_properties=("fluid density", "kinematic viscosity"),
            summary="pumped systems: shaft power against the motor, NPSH margin, pipe losses",
        ),
        _manifest(
            "industrial",
            covers=("cover_plate",),
            screens=("screen_cover_plate",),
            # No standards. The pack's own docstring calls its members "AISC-flavored", and
            # a phrase in prose is not a citation: the both-directions gate measured what
            # its entries actually cite — nothing — and this declaration was the drift.
            material_properties=("yield strength", "elastic modulus"),
            summary="walkable industrial covers: plate bending, deflection and slip",
        ),
        _manifest(
            "lighting",
            covers=("lighting_installation",),
            screens=("screen_lighting",),
            standards=("ASHRAE",),
            summary="interior lighting: illuminance from a layout against the task requirement",
        ),
        _manifest(
            "machinery",
            covers=(
                "helical_compression_spring",
                "rolling_bearing",
                "shaft_key",
                "spur_gear_mesh",
                "transmission_shaft",
            ),
            screens=(
                "screen_compression_spring",
                "screen_gear_mesh",
                "screen_rolling_bearing",
                "screen_shaft",
                "screen_shaft_key",
            ),
            standards=("AGMA",),
            material_properties=("yield strength", "ultimate strength", "endurance limit"),
            summary="drive trains: shafts, gear meshes, keys, bearings and springs",
        ),
        _manifest(
            "masonry",
            covers=("masonry_wall",),
            screens=("screen_masonry_wall",),
            standards=("TMS",),
            material_properties=("masonry compressive strength",),
            summary="masonry walls: axial and flexural capacity with slenderness",
        ),
        _manifest(
            "noise_exposure",
            covers=("worker_noise_exposure",),
            screens=("screen_noise_exposure",),
            summary="occupational noise: daily dose against the exposure limit",
        ),
        _manifest(
            "structural",
            covers=(
                "base_plate",
                "beam_column_member",
                "beam_member",
                "bolted_connection",
                "column_member",
                "concrete_bearing",
                "gusset_plate",
                "lifting_lug",
                "shear_plate",
                "tension_member",
                "welded_connection",
            ),
            screens=(
                "screen_base_plate",
                "screen_beam_column",
                "screen_beam_member",
                "screen_bolted_connection",
                "screen_column_member",
                "screen_concrete_bearing",
                "screen_gusset_plate",
                "screen_lifting_lug",
                "screen_shear_plate",
                "screen_structure",
                "screen_tension_member",
                "screen_welded_connection",
            ),
            standards=("AISC", "ACI", "ASME"),
            material_properties=("yield strength", "ultimate strength", "elastic modulus"),
            tiers=(ValidationTier.T1_ANALYTICAL, ValidationTier.T2_DFM),
            summary="steel, concrete and pressure members, and the connections between them",
        ),
        _manifest(
            "ventilation",
            covers=("ventilation_zone",),
            screens=("screen_ventilation",),
            standards=("ASHRAE",),
            summary="outdoor-air ventilation: the rate a space needs against the rate supplied",
        ),
    )
)


class LoadedModules(StatableModel):
    """The modules a run has enabled, and the screens they make reachable.

    The enabled set is part of what a run is: two builds of one document that enabled
    different modules screened different things, and a bundle that recorded only the
    verdict could not say so. It is carried here as data rather than left in a caller's
    head, and :meth:`screens` is what a document can actually reach.
    """

    model_config = ConfigDict(frozen=True)

    enabled: tuple[Named, ...]
    disabled: tuple[Named, ...] = ()

    def screens(self) -> tuple[str, ...]:
        """Every screen the enabled modules export, in module then declaration order."""
        return tuple(
            screen for identifier in self.enabled for screen in manifest_for(identifier).screens
        )

    def load(self, module: str):
        """Import an enabled module and hand it back, refusing one that is not enabled.

        The import happens here rather than at declaration: a manifest is data about a
        module, and reading the registry must not drag every discipline's dependencies into
        a process that wanted one of them.
        """
        import importlib

        if module not in self.enabled:
            raise ValueError(
                f"module '{module}' is not enabled in this run; enabled are "
                f"{sorted(self.enabled)}. A screen from a module nobody enabled would be a "
                "verdict the run cannot account for"
            )
        return importlib.import_module(f"anvilate.packs.{module}")

    def __str__(self) -> str:
        if not self.disabled:
            return f"{len(self.enabled)} modules enabled, none disabled"
        return (
            f"{len(self.enabled)} modules enabled, {len(self.disabled)} disabled: "
            f"{', '.join(sorted(self.disabled))}"
        )


def load_modules(
    enabled: Iterable[str] | None = None, *, registry: ModuleRegistry | None = None
) -> LoadedModules:
    """The modules to run with: every shipped one by default, or the named subset.

    Nothing is imported here. The manifests already say what each module is, and a caller
    that enables one discipline should not pay for the other nine — :meth:`LoadedModules.load`
    imports a module when something actually reaches for it.

    Two refusals, both about a set that would screen less than it looks like it does:

    - a name no manifest carries, because a typo that silently enabled nothing would screen
      a document against a subset nobody chose;
    - a module whose dependency is not in the set, named with what it needs, because a
      module composing with another and running without it is the same gap one layer down.
    """
    catalogue = registry if registry is not None else MODULE_MANIFESTS
    shipped = {manifest.id: manifest for manifest in catalogue.manifests}
    chosen = list(shipped) if enabled is None else list(dict.fromkeys(enabled))
    unknown = sorted(set(chosen) - set(shipped))
    if unknown:
        raise ValueError(f"no discipline module {unknown}; this build ships {sorted(shipped)}")
    missing = {
        identifier: sorted(set(shipped[identifier].depends_on) - set(chosen))
        for identifier in chosen
        if set(shipped[identifier].depends_on) - set(chosen)
    }
    if missing:
        named = "; ".join(f"'{module}' needs {needs}" for module, needs in sorted(missing.items()))
        raise ValueError(
            f"these enabled modules depend on modules this run disabled: {named}. A module "
            "composing with another and running without it screens less than it says it does"
        )
    return LoadedModules(enabled=tuple(chosen), disabled=tuple(sorted(set(shipped) - set(chosen))))


def manifest_for(module: str) -> ModuleManifest:
    """The manifest of the module with this id, refusing an id nothing ships."""
    for manifest in MODULE_MANIFESTS.manifests:
        if manifest.id == module:
            return manifest
    shipped = sorted(entry.id for entry in MODULE_MANIFESTS.manifests)
    raise ValueError(f"no discipline module '{module}'; this build ships {shipped}")
