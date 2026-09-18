"""Five cited environment profiles, so a first opto-mechanical screen needs one binding.

Each :class:`~anvilate.profile.Profile` here supplies the **environment** a class of
instrument lives in, taken from the clause that states it, and nothing about the design.
A profile never supplies an element's allowable stress, a mount's stiffness, or any other
property of the thing being screened: a screen that needs one still reports it missing by
name, whatever profile is bound. The declarations are named for the screen parameters
they feed (``cold``, ``hot``, ``peak_acceleration``, ``pulse_duration``, ``fill_pressure``,
``ambient_pressure``, ``assembly_temperature``, ``mitigation``), and every value in force
is marked on each entry that used it (:meth:`~anvilate.profile.ProfileBinding.mark`) as a
class default the user should confirm.

The MIL-STD-810H values were read from the methods themselves: Table 501.7-I (high
temperature), Table 502.7-I (low temperature), Table 516.8-IV (functional shock, terminal
peak sawtooth) and paragraph 2.3.1 of Method 500.6 (low pressure). The benchtop profile
supplies only the ISO 1 reference temperature and the ISO 2533 sea-level pressure; a
laboratory's own temperature range is the user's to state.

The applicability bounds come from the same places where they can: 45.4 kg is the
man-portable limit of Table 516.8-IX, and 136 kg is where note 1 of Table 516.8-IV lets
heavier materiel take a half-sine pulse instead. The 500 m bound on the two sea-level
profiles is this library's: the standard atmosphere is about 6% below sea level's pressure
by 500 m, and a fill or ambient pressure further off than that is a different site.
"""

from __future__ import annotations

from .profile import Applicability, Profile, SuppliedValue
from .units import Quantity

__all__ = [
    "BENCHTOP",
    "HANDHELD",
    "VEHICLE_MOUNTED",
    "AIRBORNE",
    "SEALED_AND_PURGED",
    "ENVIRONMENT_PROFILES",
    "ENVIRONMENT_DECLARATIONS",
]

q = Quantity.parse

#: Every declaration a profile here may supply. Each is a fact about where the instrument
#: lives; none is a property of the design.
ENVIRONMENT_DECLARATIONS = frozenset(
    {
        "cold",
        "hot",
        "peak_acceleration",
        "pulse_duration",
        "fill_pressure",
        "ambient_pressure",
        "assembly_temperature",
        "mitigation",
    }
)

_MASS_UNDER_136_KG = Applicability(context="item mass", maximum=q("136 kg"))

BENCHTOP = Profile(
    id="benchtop",
    version="1",
    citation=(
        "ISO 1:2022 standard reference temperature for geometrical product specification; "
        "ISO 2533:1975 standard atmosphere at sea level"
    ),
    applicability=(Applicability(context="operating altitude", maximum=q("500 m")),),
    supplies=(
        SuppliedValue(declaration="assembly_temperature", value=q("20 degC")),
        SuppliedValue(declaration="fill_pressure", value=q("101.325 kPa")),
    ),
)

HANDHELD = Profile(
    id="handheld",
    version="1",
    citation=(
        "MIL-STD-810H Method 501.7 Table 501.7-I basic hot ambient; Method 502.7 Table "
        "502.7-I basic cold ambient; Method 516.8 Table 516.8-IV functional shock for ground "
        "materiel"
    ),
    applicability=(Applicability(context="item mass", maximum=q("45.4 kg")),),
    supplies=(
        SuppliedValue(declaration="cold", value=q("-32 degC")),
        SuppliedValue(declaration="hot", value=q("43 degC")),
        SuppliedValue(declaration="peak_acceleration", value=40.0),
        SuppliedValue(declaration="pulse_duration", value=q("11 ms")),
    ),
)

VEHICLE_MOUNTED = Profile(
    id="vehicle_mounted",
    version="1",
    citation=(
        "MIL-STD-810H Method 501.7 Table 501.7-I basic hot induced; Method 502.7 Table "
        "502.7-I basic cold induced; Method 516.8 Table 516.8-IV note 3 for materiel mounted "
        "only in trucks and semi-trailers"
    ),
    applicability=(_MASS_UNDER_136_KG,),
    supplies=(
        SuppliedValue(declaration="cold", value=q("-33 degC")),
        SuppliedValue(declaration="hot", value=q("63 degC")),
        SuppliedValue(declaration="peak_acceleration", value=20.0),
        SuppliedValue(declaration="pulse_duration", value=q("11 ms")),
    ),
)

AIRBORNE = Profile(
    id="airborne",
    version="1",
    citation=(
        "MIL-STD-810H Method 501.7 Table 501.7-I basic hot ambient; Method 502.7 Table "
        "502.7-I basic cold induced; Method 516.8 Table 516.8-IV functional shock for flight "
        "vehicle materiel; Method 500.6 paragraph 2.3.1 cargo cabin altitude"
    ),
    applicability=(_MASS_UNDER_136_KG,),
    supplies=(
        SuppliedValue(declaration="cold", value=q("-33 degC")),
        SuppliedValue(declaration="hot", value=q("43 degC")),
        SuppliedValue(declaration="peak_acceleration", value=20.0),
        SuppliedValue(declaration="pulse_duration", value=q("11 ms")),
        SuppliedValue(declaration="ambient_pressure", value=q("57.2 kPa")),
    ),
)

SEALED_AND_PURGED = Profile(
    id="sealed_and_purged",
    version="1",
    citation=(
        "MIL-STD-810H Method 501.7 Table 501.7-I basic hot ambient; Method 502.7 Table "
        "502.7-I basic cold ambient; ISO 2533:1975 standard atmosphere at sea level"
    ),
    applicability=(Applicability(context="operating altitude", maximum=q("500 m")),),
    supplies=(
        SuppliedValue(declaration="cold", value=q("-32 degC")),
        SuppliedValue(declaration="hot", value=q("43 degC")),
        SuppliedValue(declaration="fill_pressure", value=q("101.325 kPa")),
        SuppliedValue(declaration="assembly_temperature", value=q("20 degC")),
        SuppliedValue(declaration="mitigation", value="purge"),
    ),
)

#: The five, in the order the spec names them.
ENVIRONMENT_PROFILES = (BENCHTOP, HANDHELD, VEHICLE_MOUNTED, AIRBORNE, SEALED_AND_PURGED)
