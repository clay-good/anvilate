"""Limit states by identity: which check evaluates what, and one implementation of each.

A discipline module composes the screens that already exist rather than shipping a second
implementation of a limit state. Checking that needs an identity a gate can read, and a
check's name is not one: it is written after the element instance that produced it (``col_base
plate bending``), two implementations of one limit state routinely carry different names, and
one name routinely covers two limit states. The base plate's ``concrete bearing`` is AISC
§J8's unconfined 0.85·f′c; the pedestal's ``concrete bearing`` is ACI 318 §22.8.3 with the
√(A₂/A₁) confinement bonus. Same words, two limit states, and a detector keyed on the words
would have called them one.

A :class:`LimitState` is the identity: an id from this shared registry, what the limit state
is, and every (screen, check) that evaluates it. Where more than one screen evaluates it, the
record also names the **one implementation** they all compose, and a gate reads each screen's
own calls to hold them to it — a module that re-derives a registered limit state inline, under
any name, fails naming the symbol it should have called.

:meth:`LimitStateRegistry.identify` answers, for one check a screen emitted, which limit state
it is. The suite resolves every check a module screen emits through it, so a module that adds
a limit state adds its registry entry in the same change or CI names the check that has none.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field, model_validator

from ._models import ItemCollection, Named, Provenance, StatableModel

__all__ = [
    "ScreenCheck",
    "LimitState",
    "LimitStateRegistry",
    "DEFAULT_LIMIT_STATES",
]


class ScreenCheck(StatableModel):
    """One check a module screen emits: the screen, and the check kind its entry names.

    ``screen`` is ``module.screen_name``. ``check`` is the part of the entry name after the
    element instance's own name — ``net tension`` for ``pad_eye net tension`` — or the whole
    name for a screen whose entries carry no instance prefix.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    screen: Named
    check: Named

    def names(self, entry_name: str) -> bool:
        """Whether an entry this screen emitted under ``entry_name`` is this check."""
        return entry_name == self.check or entry_name.endswith(f" {self.check}")

    def __str__(self) -> str:
        return f"{self.screen}: {self.check}"


class LimitState(StatableModel):
    """One limit state, the checks that evaluate it, and what implements it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    description: Provenance
    evaluated_by: tuple[ScreenCheck, ...] = Field(min_length=1)
    #: The one symbol every evaluating screen composes, as ``module.symbol`` under
    #: ``anvilate``. Required once two screens evaluate the limit state: without it, two
    #: screens computing one thing are two implementations of it by construction. ``None``
    #: means the single evaluating screen is itself the implementation.
    implementation: Named | None = None

    @model_validator(mode="after")
    def _one_implementation(self) -> LimitState:
        screens = sorted({binding.screen for binding in self.evaluated_by})
        if len(screens) > 1 and self.implementation is None:
            raise ValueError(
                f"limit state '{self.id}' is evaluated by {screens} and names no implementation; "
                "name the one symbol they all call in `implementation`, or they are two "
                "implementations of one limit state"
            )
        listed = [str(binding) for binding in self.evaluated_by]
        if len(set(listed)) != len(listed):
            raise ValueError(f"limit state '{self.id}' lists one check twice: {sorted(listed)}")
        return self

    def implemented_by(self) -> str:
        """The symbol that computes this limit state: the named one, or the only screen."""
        return self.implementation or self.evaluated_by[0].screen

    def __str__(self) -> str:
        checks = "; ".join(str(binding) for binding in self.evaluated_by)
        return f"{self.id}: {self.description} (implemented by {self.implemented_by()}; {checks})"


class LimitStateRegistry(ItemCollection, StatableModel):
    """Every registered limit state, with no id registered twice and no check claimed twice."""

    model_config = ConfigDict(frozen=True)

    limit_states: tuple[LimitState, ...] = ()

    @model_validator(mode="after")
    def _distinct(self) -> LimitStateRegistry:
        by_id: dict[str, LimitState] = {}
        for state in self.limit_states:
            if state.id in by_id:
                raise ValueError(
                    f"limit state '{state.id}' is registered twice, implemented by "
                    f"{by_id[state.id].implemented_by()} and by {state.implemented_by()}; "
                    f"a second implementation composes {by_id[state.id].implemented_by()} "
                    "and adds its check to the existing entry instead"
                )
            by_id[state.id] = state
        claimed: dict[str, str] = {}
        for state in self.limit_states:
            for binding in state.evaluated_by:
                key = str(binding)
                if key in claimed:
                    raise ValueError(
                        f"check '{key}' is bound to both '{claimed[key]}' and '{state.id}'; "
                        "one check evaluates one limit state"
                    )
                claimed[key] = state.id
        return self

    def identify(self, screen: str, entry_name: str) -> LimitState | None:
        """The limit state an entry ``screen`` emitted as ``entry_name`` evaluates.

        The longest matching check wins, so ``post buckling (AISC E3 elastic)`` is the
        §E3 check and not merely a ``buckling`` one. ``None`` is an unregistered check,
        which the suite refuses.
        """
        match = self._match(screen, entry_name)
        return None if match is None else match[0]

    def _match(self, screen: str, entry_name: str) -> tuple[LimitState, ScreenCheck] | None:
        best: tuple[LimitState, ScreenCheck] | None = None
        for state in self.limit_states:
            for binding in state.evaluated_by:
                if binding.screen == screen and binding.names(entry_name):
                    if best is None or len(binding.check) > len(best[1].check):
                        best = (state, binding)
        return best

    def extended(self, *limit_states: LimitState) -> LimitStateRegistry:
        """This registry with more limit states — a module's own — refusing any clash."""
        return LimitStateRegistry(limit_states=(*self.limit_states, *limit_states))

    def __str__(self) -> str:
        checks = sum(len(state.evaluated_by) for state in self.limit_states)
        return f"{len(self.limit_states)} limit states, evaluated by {checks} module checks"


def _state(
    identifier: str,
    description: str,
    *checks: tuple[str, str],
    implementation: str | None = None,
) -> LimitState:
    return LimitState(
        id=identifier,
        description=description,
        evaluated_by=tuple(ScreenCheck(screen=screen, check=check) for screen, check in checks),
        implementation=implementation,
    )


_FEEDER = "electrical.screen_feeder"
_COVER = "industrial.screen_cover_plate"
_SPRING = "machinery.screen_compression_spring"
_GEAR = "machinery.screen_gear_mesh"
_BEARING = "machinery.screen_rolling_bearing"
_SHAFT = "machinery.screen_shaft"
_KEY = "machinery.screen_shaft_key"
_BEAM = "structural.screen_beam_member"
_BOLTS = "structural.screen_bolted_connection"
_COLUMN = "structural.screen_column_member"

#: The limit states the shipped modules evaluate. A module that adds a check adds it here.
DEFAULT_LIMIT_STATES = LimitStateRegistry(
    limit_states=(
        _state(
            "electrical.conductor_ampacity",
            "a conductor carrying more current than its insulation's temperature rating allows",
            (_FEEDER, "conductor ampacity"),
        ),
        _state(
            "electrical.voltage_drop",
            "supply voltage lost along a feeder beyond what the load tolerates",
            (_FEEDER, "voltage drop"),
        ),
        _state(
            "geotechnical.pile_axial_capacity",
            "a driven pile's shaft friction and end bearing falling short of its load",
            ("geotechnical.screen_driven_pile", "pile capacity"),
        ),
        _state(
            "geotechnical.infinite_slope",
            "an infinite slope sliding on a plane parallel to its surface",
            ("geotechnical.screen_infinite_slope", "slope stability"),
        ),
        _state(
            "geotechnical.wall_overturning",
            "a retaining wall rotating about its toe",
            ("geotechnical.screen_retaining_wall", "overturning"),
        ),
        _state(
            "geotechnical.wall_sliding",
            "a retaining wall sliding along its base",
            ("geotechnical.screen_retaining_wall", "sliding"),
        ),
        _state(
            "geotechnical.footing_bearing_capacity",
            "the soil under a shallow footing failing in general shear",
            ("geotechnical.screen_shallow_footing", "bearing capacity"),
        ),
        _state(
            "hydraulics.pipe_head_loss",
            "a pipe run losing more head than its supply provides",
            ("hydraulics.screen_pipe_run", "head budget"),
        ),
        _state(
            "hydraulics.pump_cavitation",
            "a pump cavitating because the NPSH available falls short of the NPSH required",
            ("hydraulics.screen_pump_duty", "NPSH margin"),
        ),
        _state(
            "hydraulics.pump_motor_overload",
            "a pump drawing more shaft power than its motor is rated for",
            ("hydraulics.screen_pump_duty", "motor rating"),
        ),
        _state(
            "plate.flat_plate_bending",
            "a flat cover plate yielding in bending under its pressure",
            (_COVER, "plate bending"),
        ),
        _state(
            "plate.flat_plate_deflection",
            "a flat cover plate deflecting past its flatness allowance",
            (_COVER, "flatness"),
        ),
        _state(
            "plate.flat_plate_resonance",
            "a flat plate's fundamental frequency falling near an excitation",
            (_COVER, "resonance"),
        ),
        _state(
            "lighting.power_density",
            "installed lighting power exceeding the allowance for the space",
            ("lighting.screen_lighting", "lighting power density"),
        ),
        _state(
            "lighting.task_illuminance",
            "a task surface lit below the level the task needs",
            ("lighting.screen_lighting", "task illuminance"),
        ),
        _state(
            "machinery.spring_coil_shear",
            "a helical spring's coil overstressed in torsional shear",
            (_SPRING, "coil shear stress"),
        ),
        _state(
            "machinery.spring_buckling",
            "a compression spring buckling sideways under its deflection",
            (_SPRING, "lateral buckling"),
        ),
        _state(
            "machinery.spring_solid_height",
            "a compression spring driven to solid before its working deflection",
            (_SPRING, "solid-height clearance"),
        ),
        _state(
            "machinery.gear_contact_ratio",
            "a gear mesh with too little tooth overlap to transmit smoothly",
            (_GEAR, "contact ratio"),
        ),
        _state(
            "machinery.gear_pitting",
            "gear tooth flanks pitting under Hertzian contact stress",
            (_GEAR, "surface pitting"),
        ),
        _state(
            "machinery.gear_root_bending",
            "a gear tooth breaking at its root in bending",
            (_GEAR, "tooth-root bending"),
        ),
        _state(
            "machinery.gear_undercut",
            "a pinion cut with too few teeth, so the generating tool undercuts the flank",
            (_GEAR, "undercut"),
        ),
        _state(
            "machinery.bearing_rating_life",
            "a rolling bearing reaching its rated fatigue life before the required service",
            (_BEARING, "bearing rating life"),
        ),
        _state(
            "machinery.bearing_static_capacity",
            "a rolling bearing's raceways permanently indented by a static load",
            (_BEARING, "bearing static capacity"),
        ),
        _state(
            "machinery.shaft_static_strength",
            "a shaft yielding under combined bending and torsion",
            (_SHAFT, "combined bending and torsion"),
        ),
        _state(
            "machinery.shaft_fatigue",
            "a rotating shaft failing in fatigue at a stress raiser",
            (_SHAFT, "rotating-shaft fatigue"),
        ),
        _state(
            "machinery.shaft_torsional_stiffness",
            "a shaft twisting more than its drive tolerates",
            (_SHAFT, "torsional twist"),
        ),
        _state(
            "machinery.key_shear",
            "a shaft key shearing across its width",
            (_KEY, "key shear"),
        ),
        _state(
            "machinery.key_bearing",
            "a shaft key crushing against the side of its keyway",
            (_KEY, "key side bearing"),
        ),
        _state(
            "masonry.wall_axial",
            "a masonry wall overstressed in axial compression",
            ("masonry.screen_masonry_wall", "axial stress"),
        ),
        _state(
            "masonry.wall_combined",
            "a masonry wall overstressed by axial load and flexure together",
            ("masonry.screen_masonry_wall", "combined axial + flexure"),
        ),
        _state(
            "noise_exposure.daily_dose",
            "a worker's daily noise dose exceeding the permissible exposure",
            ("noise_exposure.screen_noise_exposure", "noise dose"),
        ),
        _state(
            "steel.base_plate_bearing",
            "concrete under a column base plate crushing, at AISC §J8's unconfined 0.85·f′c",
            ("structural.screen_base_plate", "concrete bearing"),
        ),
        _state(
            "steel.base_plate_bending",
            "a column base plate yielding in cantilever bending beyond the column",
            ("structural.screen_base_plate", "plate bending"),
        ),
        _state(
            "steel.column_flexural_buckling",
            "a compression member buckling in flexure on the AISC §E3 column curve",
            (_COLUMN, "buckling"),
            (_COLUMN, "buckling (AISC E3 elastic)"),
            (_COLUMN, "buckling (AISC E3 inelastic)"),
            ("structural.screen_beam_column", "axial capacity"),
            implementation="analysis.aisc_flexural_buckling_stress",
        ),
        _state(
            "steel.beam_column_interaction",
            "a member failing under axial load and bending together (AISC §H1.1)",
            ("structural.screen_beam_column", "interaction"),
        ),
        _state(
            "steel.beam_column_tension_interaction",
            "a member failing under net tension and bending together (AISC §H1.2)",
            ("structural.screen_beam_column", "tension interaction"),
        ),
        _state(
            "timber.beam_bending",
            "a sawn-lumber beam exceeding its NDS adjusted bending design value",
            ("timber.screen_timber_beam", "bending"),
        ),
        _state(
            "timber.beam_shear",
            "a sawn-lumber beam exceeding its NDS adjusted shear design value parallel to grain",
            ("timber.screen_timber_beam", "shear"),
        ),
        _state(
            "timber.beam_deflection",
            "a sawn-lumber beam sagging past its limit, with creep on its sustained load",
            ("timber.screen_timber_beam", "deflection"),
        ),
        _state(
            "steel.beam_bending",
            "a beam yielding in bending",
            (_BEAM, "bending"),
        ),
        _state(
            "steel.beam_shear",
            "a beam web yielding in shear",
            (_BEAM, "shear"),
        ),
        _state(
            "steel.beam_deflection",
            "a beam deflecting past its serviceability limit",
            (_BEAM, "deflection"),
        ),
        _state(
            "steel.beam_resonance",
            "a beam's fundamental frequency falling near an excitation",
            (_BEAM, "resonance"),
        ),
        _state(
            "steel.bolt_shear",
            "a bolt shearing across its shank",
            (_BOLTS, "bolt shear"),
        ),
        _state(
            "steel.bolt_tension",
            "a bolt failing in tension",
            (_BOLTS, "bolt tension"),
        ),
        _state(
            "steel.bolt_combined",
            "a bolt failing under tension and shear together",
            (_BOLTS, "combined tension+shear"),
        ),
        _state(
            "steel.bolt_hole_bearing",
            "a connected plate deforming in bearing at its bolt holes",
            (_BOLTS, "plate bearing"),
        ),
        _state(
            "steel.bolt_tear_out",
            "a bolt tearing out through the plate edge beyond its hole",
            (_BOLTS, "edge tear-out"),
        ),
        _state(
            "concrete.confined_bearing",
            "concrete crushing under a bearing plate, with ACI 318 §22.8.3's confinement bonus",
            ("structural.screen_concrete_bearing", "concrete bearing"),
        ),
        _state(
            "steel.block_shear",
            "a connection tearing out along a combined shear and tension path",
            ("structural.screen_gusset_plate", "block shear"),
        ),
        _state(
            "steel.lug_net_tension",
            "a lifting lug yielding in tension across the net section beside its pin hole",
            ("structural.screen_lifting_lug", "net tension"),
        ),
        _state(
            "steel.lug_pin_bearing",
            "a lifting lug yielding in bearing against its pin",
            ("structural.screen_lifting_lug", "pin bearing"),
        ),
        _state(
            "steel.connection_shear_yielding",
            "a connection element yielding in shear on its gross section",
            ("structural.screen_shear_plate", "shear yielding"),
        ),
        _state(
            "steel.connection_shear_rupture",
            "a connection element rupturing in shear on its net section",
            ("structural.screen_shear_plate", "shear rupture"),
        ),
        _state(
            "steel.tension_gross_yielding",
            "a tension member yielding along its gross section",
            ("structural.screen_tension_member", "gross yielding"),
            ("structural.screen_beam_column", "tensile yielding"),
            implementation="analysis.axial_stress",
        ),
        _state(
            "steel.tension_net_rupture",
            "a tension member rupturing across its net section",
            ("structural.screen_tension_member", "net rupture"),
        ),
        _state(
            "steel.fillet_weld_shear",
            "a fillet weld rupturing in shear through its throat",
            ("structural.screen_welded_connection", "weld shear"),
        ),
        _state(
            "ventilation.air_changes",
            "a space ventilated at fewer air changes per hour than it needs",
            ("ventilation.screen_ventilation", "air changes per hour"),
        ),
        _state(
            "ventilation.outdoor_air",
            "a space supplied with less outdoor air than its occupancy needs",
            ("ventilation.screen_ventilation", "outdoor air"),
        ),
    )
)
