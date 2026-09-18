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

from pydantic import ConfigDict, Field, model_validator

from ._models import ItemCollection, Named, Provenance, StatableModel
from .spec import ValidationTier
from .units import UnitSystem

__all__ = [
    "Deprecation",
    "ModuleManifest",
    "ModuleRegistry",
    "MODULE_MANIFESTS",
    "manifest_for",
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
        summary=summary,
    )


#: One manifest per shipped pack. The screens are held against what each pack exports by the
#: gate in `tests/test_modules.py`, so this list cannot drift into describing a pack that has
#: moved on without it.
MODULE_MANIFESTS = ModuleRegistry(
    manifests=(
        _manifest(
            "electrical",
            screens=("screen_feeder",),
            standards=("NEC",),
            summary="branch and feeder circuits: conductor ampacity, voltage drop, breaker size",
        ),
        _manifest(
            "geotechnical",
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
            screens=(
                "screen_pipe_run",
                "screen_pump_duty",
            ),
            material_properties=("fluid density", "kinematic viscosity"),
            summary="pumped systems: shaft power against the motor, NPSH margin, pipe losses",
        ),
        _manifest(
            "industrial",
            screens=("screen_cover_plate",),
            standards=("AISC",),
            material_properties=("yield strength", "elastic modulus"),
            summary="walkable industrial covers: plate bending, deflection and slip",
        ),
        _manifest(
            "lighting",
            screens=("screen_lighting",),
            standards=("ASHRAE",),
            summary="interior lighting: illuminance from a layout against the task requirement",
        ),
        _manifest(
            "machinery",
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
            screens=("screen_masonry_wall",),
            standards=("TMS",),
            material_properties=("masonry compressive strength",),
            summary="masonry walls: axial and flexural capacity with slenderness",
        ),
        _manifest(
            "noise_exposure",
            screens=("screen_noise_exposure",),
            summary="occupational noise: daily dose against the exposure limit",
        ),
        _manifest(
            "structural",
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
            screens=("screen_ventilation",),
            standards=("ASHRAE",),
            summary="outdoor-air ventilation: the rate a space needs against the rate supplied",
        ),
    )
)


def manifest_for(module: str) -> ModuleManifest:
    """The manifest of the module with this id, refusing an id nothing ships."""
    for manifest in MODULE_MANIFESTS.manifests:
        if manifest.id == module:
            return manifest
    shipped = sorted(entry.id for entry in MODULE_MANIFESTS.manifests)
    raise ValueError(f"no discipline module '{module}'; this build ships {shipped}")
