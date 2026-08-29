"""ASME BTH-1 below-the-hook lifting devices: the design factor, and what sets it.

Every custom lifter — a spreader beam, a lifting beam, a plate-clamp frame — needs
BTH-1-compliant design under OSHA and ASME B30.20, and the practice is almost entirely
spreadsheet-bound. The arithmetic is not the hard part. The hard part is that BTH-1's
allowable stresses are not fixed numbers: they are the material's yield divided by a
*design factor* the designer selects, and selecting it is a judgement about the service
the lifter will see.

There are two, and the gap between them is 50%:

* **Design Category A**, N_d = 2.00 — the loads are predictable, the conditions
  controlled, the environment defined, and the device's use is closely supervised.
* **Design Category B**, N_d = 3.00 — anything less. Unpredictable loads, uncontrolled
  or severe conditions, a device that leaves the bay it was designed for.

Those are the yielding and buckling factors. Fracture and connection design take
1.20·N_d, which BTH-1 tabulates as 2.40 and 3.60 — so the net-section rupture allowable
here carries an extra 1.20 that the yield-governed allowables do not.

A lifter that screens comfortably as Category A can fail outright as Category B on the
same steel and the same load, and nothing in the geometry says which one applies. That is
the decision this module makes explicit and typed, rather than leaving it as a bare
``required_safety_factor`` a caller passes in and a reviewer cannot trace.

Service Class does the same job for fatigue. It is set by the number of load cycles the
device will see over its life, and Class 0 is the only one that carries no fatigue
obligation at all. A lifter declared Class 1 or above without cycle data has not been
screened for fatigue, and this module says so rather than passing it.

Sources: ASME BTH-1 (Design of Below-the-Hook Lifting Devices) §3-1.3 for the design
categories, §3-1.4 for the service classes, and §3-2/§3-3 for the allowable stresses.
Yield and ultimate strengths follow the user-supplied allowables doctrine.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity

__all__ = [
    "DesignCategory",
    "ServiceClass",
    "BTH1Allowables",
    "service_class_for_cycles",
    "bth1_allowable_stresses",
    "bth1_member_scorecard",
    "bth1_fatigue_scorecard",
    "BTH1LimitState",
    "LifterMemberStress",
    "LifterPinPlate",
    "LifterDevice",
    "bth1_allowable_for",
    "bth1_pin_plate_scorecard",
    "screen_lifter_device",
]

_CLAUSE_CATEGORY = "ASME BTH-1 §3-1.3 (Design Category)"
_CLAUSE_SERVICE = "ASME BTH-1 §3-1.4 (Service Class)"
_CLAUSE_ALLOWABLES = "ASME BTH-1 §3-2/§3-3 (allowable stresses)"

# BTH-1 §3-2: the coefficients on S_y/N_d and S_u/N_d that define each allowable.
_SHEAR_COEFFICIENT = 0.60  # F_v = 0.60·S_y/N_d
_BEARING_COEFFICIENT = 1.25  # F_p = 1.25·S_y/N_d, a pin in a hole with clearance
# BTH-1 does not use ONE design factor per category: the yielding and buckling limit
# states take N_d (2.00 / 3.00), and fracture and connection design take 1.20·N_d, which
# the standard tabulates directly as 2.40 and 3.60. So the net-section (rupture) allowable
# carries this extra 1.20 and the yield-governed ones do not — and the ratio between them
# is a property of the Code, not of the material.
_RUPTURE_DIVISOR = 1.20  # F_t,net = S_u/(1.20·N_d); 1.20·N_d is BTH-1's 2.40 / 3.60


class DesignCategory(StrEnum):
    """ASME BTH-1 §3-1.3: which design factor the lifter is designed to.

    :attr:`A` is for a device whose loads are predictable, whose conditions and
    environment are defined and controlled, and whose use is closely supervised.
    :attr:`B` is for everything else — and "everything else" includes the ordinary case
    of a lifter that leaves the bay it was designed for.

    The choice is a 50% change in every allowable stress, and it is not recoverable from
    the geometry. Making it a typed input rather than a bare safety factor is the point:
    a reviewer can see which category a margin was computed under.
    """

    A = "A"
    B = "B"

    @property
    def design_factor(self) -> float:
        """N_d — 2.00 for Category A, 3.00 for Category B."""
        return 2.00 if self is DesignCategory.A else 3.00


class ServiceClass(StrEnum):
    """ASME BTH-1 §3-1.4: the load-cycle band that sets the fatigue obligation.

    Class 0 is the only class with no fatigue analysis requirement. Every class above it
    carries one, and a device declared Class 1 or higher without cycle data has not been
    fatigue-screened — which is a different thing from having passed.
    """

    CLASS_0 = "0"
    CLASS_1 = "1"
    CLASS_2 = "2"
    CLASS_3 = "3"
    CLASS_4 = "4"

    @property
    def cycle_range(self) -> tuple[int, int | None]:
        """The (lower, upper) load-cycle bounds; ``None`` upper means unbounded."""
        return {
            ServiceClass.CLASS_0: (0, 20_000),
            ServiceClass.CLASS_1: (20_001, 100_000),
            ServiceClass.CLASS_2: (100_001, 500_000),
            ServiceClass.CLASS_3: (500_001, 2_000_000),
            ServiceClass.CLASS_4: (2_000_001, None),
        }[self]

    @property
    def fatigue_required(self) -> bool:
        """True for every class but 0 — BTH-1 exempts only the lowest band."""
        return self is not ServiceClass.CLASS_0


def service_class_for_cycles(load_cycles: int) -> ServiceClass:
    """The ASME BTH-1 §3-1.4 Service Class for a design life of ``load_cycles``.

    The bands are 0–20,000 (Class 0), 20,001–100,000 (1), 100,001–500,000 (2),
    500,001–2,000,000 (3), and above that Class 4. Note the boundaries are *inclusive
    upper* — a device at exactly 20,000 cycles is Class 0 and carries no fatigue
    obligation, and one at 20,001 is Class 1 and does. A design life estimated as "about
    twenty thousand" sits exactly on the only boundary in this table that changes whether
    a whole analysis is required, so it is worth being deliberate about which side of it
    the estimate falls.
    """
    if load_cycles < 0:
        raise ValueError(f"load_cycles must be non-negative; got {load_cycles}")
    for service in ServiceClass:
        low, high = service.cycle_range
        if load_cycles >= low and (high is None or load_cycles <= high):
            return service
    raise AssertionError("the service class bands cover every non-negative cycle count")


class BTH1Allowables(BaseModel):
    """The ASME BTH-1 allowable stresses for one material at one design category.

    Every one of them is a strength over the same design factor N_d, so they all scale
    together: moving from Category A to B multiplies each by 2/3, exactly.

    ``tension_gross`` F_t = S_y/N_d on the gross section, ``tension_net`` F_t =
    S_u/(1.20·N_d) on the net section, ``shear`` F_v = 0.60·S_y/N_d, ``bending`` F_b =
    S_y/N_d for a compact, laterally braced member, and ``pin_bearing`` F_p =
    1.25·S_y/N_d for a pin in a hole with clearance.
    """

    model_config = ConfigDict(frozen=True)

    category: DesignCategory
    design_factor: float
    tension_gross: Quantity
    tension_net: Quantity
    shear: Quantity
    bending: Quantity
    pin_bearing: Quantity

    def __str__(self) -> str:
        return (
            f"BTH-1 Category {self.category.value} (N_d = {self.design_factor:.2f}): "
            f"F_t {self.tension_gross}, F_v {self.shear}, F_p {self.pin_bearing}"
        )


def bth1_allowable_stresses(
    *,
    yield_strength: Quantity,
    ultimate_strength: Quantity,
    category: DesignCategory,
) -> BTH1Allowables:
    """The ASME BTH-1 §3-2/§3-3 allowable stresses for a material at a design category.

    F_t = S_y/N_d on the gross section and S_u/(1.20·N_d) on the net; F_v = 0.60·S_y/N_d;
    F_b = S_y/N_d for a compact, laterally braced member; F_p = 1.25·S_y/N_d for a pin in
    a hole with clearance. N_d is 2.00 for Category A and 3.00 for Category B.

    Two limits worth knowing before leaning on the bending value. F_b = S_y/N_d assumes
    the member is **compact and laterally braced** — a non-compact section or an unbraced
    compression flange takes BTH-1's reduced forms, which are not computed here, and
    using this value for one would be unconservative. And F_p is the clearance-fit pin
    value; a pin in sliding contact under load takes a much lower allowable, because it
    is a wear limit rather than a strength one.

    ``yield_strength`` S_y and ``ultimate_strength`` S_u are the caller's, read from the
    material certificate or specification. Returns a :class:`BTH1Allowables`.
    """
    for value, name in (
        (yield_strength, "yield_strength"),
        (ultimate_strength, "ultimate_strength"),
    ):
        if not isinstance(value, Quantity):
            raise ValueError(f"{name} must be a [pressure] quantity; got {value!r}")
        if not value.has_dimension("[pressure]"):
            raise ValueError(f"{name} must be a [pressure] quantity; got {value}")
        if value.magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    sy = yield_strength.to("MPa").magnitude
    su = ultimate_strength.to("MPa").magnitude
    if su < sy:
        raise ValueError(
            f"ultimate_strength ({ultimate_strength}) is below yield_strength "
            f"({yield_strength}); check they are not swapped"
        )
    nd = category.design_factor
    return BTH1Allowables(
        category=category,
        design_factor=nd,
        tension_gross=Quantity(magnitude=sy / nd, unit="MPa"),
        tension_net=Quantity(magnitude=su / (_RUPTURE_DIVISOR * nd), unit="MPa"),
        shear=Quantity(magnitude=_SHEAR_COEFFICIENT * sy / nd, unit="MPa"),
        bending=Quantity(magnitude=sy / nd, unit="MPa"),
        pin_bearing=Quantity(magnitude=_BEARING_COEFFICIENT * sy / nd, unit="MPa"),
    )


def bth1_member_scorecard(
    name: str,
    *,
    stress: Quantity,
    allowable: Quantity,
    category: DesignCategory,
) -> ScorecardEntry:
    """Screen a stress against an ASME BTH-1 allowable → a :class:`ScorecardEntry`.

    The safety factor is the allowable over the applied ``stress``, judged against 1.0 —
    **not** against a caller-supplied margin. BTH-1's design factor is already inside the
    allowable, and requiring a further margin on top of it would double-count: a lifter
    at exactly its BTH-1 allowable already carries N_d against yield.

    The detail names the category and its design factor, because the same geometry at the
    same load gives a margin 50% apart between the two, and a number without its category
    cannot be checked.
    """
    for value, label in ((stress, "stress"), (allowable, "allowable")):
        if not isinstance(value, Quantity):
            raise ValueError(f"{label} must be a [pressure] quantity; got {value!r}")
        if not value.has_dimension("[pressure]"):
            raise ValueError(f"{label} must be a [pressure] quantity; got {value}")
    applied = abs(stress.to("MPa").magnitude)
    limit = allowable.to("MPa").magnitude
    if limit <= 0:
        raise ValueError(f"allowable must be positive; got {allowable}")
    # Zero applied stress is a check with nothing to evaluate, not one that passed.
    computed = None if applied == 0 else limit / applied
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=1.0)
    detail = (
        f"{applied:.4g} MPa against a Category {category.value} allowable of "
        f"{limit:.4g} MPa (N_d = {category.design_factor:.2f}, already inside the "
        f"allowable)"
    )
    return entry.model_copy(update={"detail": detail, "reference": _CLAUSE_ALLOWABLES})


def bth1_fatigue_scorecard(
    name: str,
    *,
    service_class: ServiceClass,
    stress_range: Quantity | None = None,
    allowable_stress_range: Quantity | None = None,
) -> ScorecardEntry:
    """Screen a lifter's ASME BTH-1 fatigue obligation for its Service Class.

    Class 0 carries no BTH-1 fatigue analysis requirement, and this reports that as a
    PASS naming the exemption — a device below 20,000 cycles genuinely does not need one.

    Every class above 0 does. When ``stress_range`` and ``allowable_stress_range`` are
    both supplied the check runs; when either is missing the entry is ``NOT_EVALUATED``
    naming what is absent. It is never a pass: a Class 3 lifter with no fatigue data has
    not been screened, and reporting that as adequate would put the exemption Class 0
    earns onto a device that has not earned it.

    ``allowable_stress_range`` is the detail category's allowable at the class's cycle
    count — from :mod:`~anvilate.analysis.fatigue` or the applicable detail table — and
    is the caller's, like every other allowable here.
    """
    if not isinstance(service_class, ServiceClass):
        raise ValueError(f"service_class must be a ServiceClass; got {service_class!r}")
    if not service_class.fatigue_required:
        low, high = service_class.cycle_range
        return ScorecardEntry(
            name=name,
            status=CheckStatus.PASS,
            detail=(
                f"Service Class 0 ({low}–{high} load cycles) carries no BTH-1 fatigue "
                f"analysis requirement — the exemption, not a computed margin"
            ),
            reference=_CLAUSE_SERVICE,
        )
    low, high = service_class.cycle_range
    band = f"{low}–{high}" if high is not None else f"over {low - 1}"
    if stress_range is None or allowable_stress_range is None:
        missing = "stress range" if stress_range is None else "allowable stress range"
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — Service Class {service_class.value} ({band} load "
                f"cycles) requires a fatigue analysis and no {missing} was supplied. "
                f"Only Class 0 is exempt."
            ),
            reference=_CLAUSE_SERVICE,
        )
    for value, label in (
        (stress_range, "stress_range"),
        (allowable_stress_range, "allowable_stress_range"),
    ):
        if not isinstance(value, Quantity):
            raise ValueError(f"{label} must be a [pressure] quantity; got {value!r}")
        if not value.has_dimension("[pressure]"):
            raise ValueError(f"{label} must be a [pressure] quantity; got {value}")
    applied = abs(stress_range.to("MPa").magnitude)
    limit = allowable_stress_range.to("MPa").magnitude
    if limit <= 0:
        raise ValueError(f"allowable_stress_range must be positive; got {allowable_stress_range}")
    computed = None if applied == 0 else limit / applied
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=1.0)
    detail = (
        f"Service Class {service_class.value} ({band} load cycles): a stress range of "
        f"{applied:.4g} MPa against an allowable {limit:.4g} MPa"
    )
    return entry.model_copy(update={"detail": detail, "reference": _CLAUSE_SERVICE})


class BTH1LimitState(StrEnum):
    """Which ASME BTH-1 allowable a member stress is judged against.

    Naming the limit state rather than passing an allowable directly is the point: the
    five allowables differ by a factor of more than two, they are *not* interchangeable,
    and picking the wrong one is a silent error. A shear stress checked against the
    tension allowable passes at 1.67x the margin it has earned.
    """

    TENSION_GROSS = "tension_gross"
    TENSION_NET = "tension_net"
    SHEAR = "shear"
    BENDING = "bending"
    PIN_BEARING = "pin_bearing"


class LifterMemberStress(BaseModel):
    """One computed stress in a lifter member, tagged with the limit state it belongs to.

    Screened against the ASME BTH-1 §3-2/§3-3 allowable its limit state names.

    ``stress`` is whatever the geometry produced — from the beam, column or
    combined-stress functions elsewhere in the library, or from the caller's own
    analysis. ``limit_state`` decides which BTH-1 allowable screens it, so the design
    factor reaches the check through the standard's own routing rather than through a
    number the caller chose.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    stress: Quantity
    limit_state: BTH1LimitState


class LifterPinPlate(BaseModel):
    """A pin-connected plate in a lifter — a lug, a pad eye, a bail — and its load.

    Screened against the ASME BTH-1 §3-2.1 net-section and §3-3.3 bearing allowables.

    ``width`` W is the plate width across the hole, ``hole_diameter`` d the pin hole,
    ``thickness`` t the plate, and ``load`` P the force through the pin. The hole must
    fit inside the width, which is the one geometric transposition that would otherwise
    produce a negative net section and a nonsense stress.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    width: Quantity
    hole_diameter: Quantity
    thickness: Quantity
    load: Quantity


class LifterDevice(BaseModel):
    """A below-the-hook lifting device: what it is rated for, and what it is designed to.

    ``rated_load`` is the load the device will be *marked* with, and ``self_weight`` is
    the device's own weight. Both are required, and ``self_weight`` deliberately has no
    default: ASME BTH-1 §3-1.2 has the design consider the device's own weight alongside the
    rated load, and a spreader beam heavy enough to need a crane to fit is heavy enough
    to matter at its own upper attachment. Defaulting it to zero would let the most
    common omission in lifter design pass without anyone stating it. A designer who has
    genuinely established it as negligible passes zero on purpose, and that shows in the
    scorecard.

    ``design_load`` is their sum — the load at the **upper attachment**, where the crane
    hook carries the device as well as the lift. Members and attachments *below* the
    load path carry the rated load alone; the self weight does not reach them, so do not
    apply this to a lower lug.

    ``category`` and ``service_class`` are the two typed judgements that set every
    allowable and the fatigue obligation, and they travel into every entry of the
    scorecard, because a BTH-1 margin quoted without them cannot be checked.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    rated_load: Quantity
    self_weight: Quantity
    category: DesignCategory
    service_class: ServiceClass

    @property
    def design_load(self) -> Quantity:
        """Rated load plus the device's own weight — the load at the upper attachment."""
        return Quantity(
            magnitude=self.rated_load.to("N").magnitude + self.self_weight.to("N").magnitude,
            unit="N",
        )

    def __str__(self) -> str:
        return (
            f"{self.name}: rated {self.rated_load}, Category {self.category.value}, "
            f"Service Class {self.service_class.value}"
        )


def bth1_allowable_for(allowables: BTH1Allowables, limit_state: BTH1LimitState) -> Quantity:
    """The one of the five ASME BTH-1 allowables that ``limit_state`` names."""
    if not isinstance(allowables, BTH1Allowables):
        raise ValueError(f"allowables must be a BTH1Allowables; got {allowables!r}")
    if not isinstance(limit_state, BTH1LimitState):
        raise ValueError(f"limit_state must be a BTH1LimitState; got {limit_state!r}")
    return {
        BTH1LimitState.TENSION_GROSS: allowables.tension_gross,
        BTH1LimitState.TENSION_NET: allowables.tension_net,
        BTH1LimitState.SHEAR: allowables.shear,
        BTH1LimitState.BENDING: allowables.bending,
        BTH1LimitState.PIN_BEARING: allowables.pin_bearing,
    }[limit_state]


def bth1_pin_plate_scorecard(
    plate: LifterPinPlate, *, allowables: BTH1Allowables
) -> tuple[ScorecardEntry, ScorecardEntry]:
    """Screen a pin-connected plate's two ASME BTH-1 limit states.

    Net-section tension P/((W − d)·t) against F_t = S_u/(1.20·N_d), and pin bearing
    P/(d·t) against F_p = 1.25·S_y/N_d.

    **The two allowables come off different strengths, and that is the part a generic
    lug check gets wrong.** :func:`~anvilate.packs.screen_lifting_lug` screens both
    states against *yield* at a caller-chosen margin, which is a reasonable general
    check but is not this one: BTH-1 puts the net section against *ultimate* over
    1.20·N_d, because a net section that has yielded has not failed — it tears. On
    A36 (S_y 250, S_u 400 MPa) at Category B the net allowable here is 111 MPa where
    yield over the same 3.00 gives 83 MPa, so the generic check is 33% conservative on
    tension; on a high-yield low-ratio steel the sign of that gap reverses.

    Returns the two entries in that order.
    """
    if not isinstance(plate, LifterPinPlate):
        raise ValueError(f"plate must be a LifterPinPlate; got {plate!r}")
    if not isinstance(allowables, BTH1Allowables):
        raise ValueError(f"allowables must be a BTH1Allowables; got {allowables!r}")
    width = plate.width.to("mm").magnitude
    hole = plate.hole_diameter.to("mm").magnitude
    thickness = plate.thickness.to("mm").magnitude
    for value, name in (
        (width, "width"),
        (hole, "hole_diameter"),
        (thickness, "thickness"),
    ):
        if value <= 0:
            raise ValueError(f"{plate.name}: {name} must be positive; got {value} mm")
    if hole >= width:
        raise ValueError(
            f"{plate.name}: hole_diameter ({plate.hole_diameter}) must be below the "
            f"plate width ({plate.width}); check they are not swapped"
        )
    if not plate.load.has_dimension("[force]"):
        raise ValueError(f"{plate.name}: load must be a [force] quantity; got {plate.load}")
    force = abs(plate.load.to("N").magnitude)
    net_tension = Quantity(magnitude=force / ((width - hole) * thickness), unit="MPa")
    bearing = Quantity(magnitude=force / (hole * thickness), unit="MPa")
    return (
        bth1_member_scorecard(
            f"{plate.name} net tension",
            stress=net_tension,
            allowable=allowables.tension_net,
            category=allowables.category,
        ),
        bth1_member_scorecard(
            f"{plate.name} pin bearing",
            stress=bearing,
            allowable=allowables.pin_bearing,
            category=allowables.category,
        ),
    )


def screen_lifter_device(
    device: LifterDevice,
    *,
    allowables: BTH1Allowables,
    members: tuple[LifterMemberStress, ...] = (),
    pin_plates: tuple[LifterPinPlate, ...] = (),
    stress_range: Quantity | None = None,
    allowable_stress_range: Quantity | None = None,
) -> tuple[ScorecardEntry, ...]:
    """Screen a whole lifter: its members, its pin plates, and its fatigue obligation.

    Every entry is routed to its own ASME BTH-1 §3-2/§3-3 allowable through
    :class:`BTH1LimitState`, so the design factor reaches every check from
    ``device.category`` and cannot be quietly different in two places. The first entry
    is the device's identification — rated load, design load, category and service
    class — which is not a computed check but is the context every margin below it needs
    in order to mean anything.

    ``allowables`` must have been built for the same category the device declares;
    a mismatch is rejected rather than silently screened at the wrong factor.

    At least one member or pin plate is required: a device with neither would produce a
    scorecard whose only entries are the identification line and a Class 0 fatigue
    exemption, and roll up green having screened nothing.

    ``stress_range`` and ``allowable_stress_range`` feed
    :func:`bth1_fatigue_scorecard`; omit them and a Class 1+ device reports
    NOT_EVALUATED for fatigue, which is the honest answer and not a pass.

    Returns the entries; wrap them in a :class:`~anvilate.scorecard.Scorecard` to roll
    them up.
    """
    if not isinstance(device, LifterDevice):
        raise ValueError(f"device must be a LifterDevice; got {device!r}")
    if not isinstance(allowables, BTH1Allowables):
        raise ValueError(f"allowables must be a BTH1Allowables; got {allowables!r}")
    if allowables.category is not device.category:
        raise ValueError(
            f"the allowables were built for Category {allowables.category.value} but "
            f"{device.name} declares Category {device.category.value}; every margin "
            f"would be computed at the wrong design factor"
        )
    if not members and not pin_plates:
        # The identification entry is context, not a computed check, and Class 0 fatigue
        # is a legitimate exemption — so a device with neither members nor pin plates
        # rolled up as a PASSING scorecard with two entries and nothing screened. That is
        # the empty-card silent green `Scorecard` guards against, reached by walking in
        # through the side door.
        raise ValueError(
            f"{device.name}: no members and no pin plates were given, so nothing would be "
            f"screened — and the identification and fatigue entries alone roll up as a "
            f"PASS. Supply the stresses to check, or do not call this a screen"
        )
    rated = device.rated_load.to("kN").magnitude
    weight = device.self_weight.to("kN").magnitude
    identification = ScorecardEntry(
        name=f"{device.name} rating",
        status=CheckStatus.PASS,
        detail=(
            f"rated load {rated:.4g} kN plus a device self weight of {weight:.4g} kN "
            f"gives {device.design_load.to('kN').magnitude:.4g} kN at the upper "
            f"attachment; Category {device.category.value} (N_d = "
            f"{device.category.design_factor:.2f}), Service Class "
            f"{device.service_class.value}"
        ),
        reference=_CLAUSE_CATEGORY,
    )
    entries: list[ScorecardEntry] = [identification]
    for member in members:
        entries.append(
            bth1_member_scorecard(
                member.name,
                stress=member.stress,
                allowable=bth1_allowable_for(allowables, member.limit_state),
                category=device.category,
            )
        )
    for plate in pin_plates:
        entries.extend(bth1_pin_plate_scorecard(plate, allowables=allowables))
    entries.append(
        bth1_fatigue_scorecard(
            f"{device.name} fatigue",
            service_class=device.service_class,
            stress_range=stress_range,
            allowable_stress_range=allowable_stress_range,
        )
    )
    return tuple(entries)
