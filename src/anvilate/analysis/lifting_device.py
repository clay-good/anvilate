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
