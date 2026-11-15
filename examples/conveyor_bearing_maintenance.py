"""Worked example: the bearing that passes, and the date it has to be changed.

`examples/conveyor_bearing_life.py` picks the bearing: the heavy 6310 is the one that
clears the 30,000-hour target on a conveyor pulley carrying 4 kN at 900 rpm. This example
is the next question, the one that passing does not answer — *when does somebody change
it?*

The L10 rating life is the life 90% of a population reaches, so running a bearing to it
is running most of a fleet past its own prediction. The plant's policy says replace at
half, with the document that says so, and that rule plus the computed life is the
interval. Nothing here picks the half: a life no declared rule reaches produces an item
reading "interval not set", never a number this library chose.

The other three items of the conveyor have no life-limited check at all, and the plan
names them. A schedule of one item on a product of four that listed only the one would
read exactly like a complete plan.

Over a ten-year service life at 4,000 running hours a year, the spares count falls out of
the same two numbers, and it rounds up: a fraction of a replacement is a whole bearing on
the shelf.

The example reports the rating life, the replacement interval, the spares count, and the
number of product items no life-limited check covers.

Run it directly (``python examples/conveyor_bearing_maintenance.py``);
:func:`conveyor_maintenance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.machinery import RollingBearing, screen_rolling_bearing
from anvilate.scorecard import CheckStatus
from anvilate.service_life import IntervalRule, TaskType, plan_service_life
from anvilate.units import Quantity

Q = Quantity.parse

PULLEY_BEARING = RollingBearing(
    designation="6310",
    dynamic_load_rating=Q("61.8 kN"),
    static_load_rating=Q("38 kN"),
    radial_load=Q("4 kN"),
    axial_load=Q("0.4 kN"),
    radial_factor=1.0,
    axial_factor=0.5,
    speed=Q("900 rpm"),
    required_life_hours=Q("30000 hour"),
)

#: Declared with the document that declares it. The library supplies no default fraction,
#: and a rule that named no check would be refused: a rule covering everything by saying
#: nothing is the default this module exists to refuse.
REPLACE_AT_HALF_LIFE = IntervalRule(
    name="replace rolling bearings at half of rating life",
    task=TaskType.TIME_DIRECTED,
    source="the plant's rotating-equipment maintenance policy, rev 4 §5.2",
    applies_to=("bearing rating life",),
    fraction_of_life=0.5,
)

SERVICE_LIFE = Q("10 year")
DUTY_PER_YEAR = Q("4000 hour")
PRODUCT_ITEMS = (
    "conveyor/pulley bearing",
    "conveyor/shaft seal",
    "conveyor/pulley shaft",
    "conveyor/frame",
)


def conveyor_maintenance() -> dict[str, float]:
    """Screen the bearing, then schedule the replacement its rating life implies."""
    card = screen_rolling_bearing(PULLEY_BEARING)
    plan = plan_service_life(
        card,
        rules=(REPLACE_AT_HALF_LIFE,),
        item_paths={"bearing rating life": "conveyor/pulley bearing"},
        spares={"bearing rating life": "6310-2RS1"},
        product_items=PRODUCT_ITEMS,
        service_life=SERVICE_LIFE,
        duty_per_year=DUTY_PER_YEAR,
    )
    item = plan.items[0]
    spare = plan.spares()[0]
    return {
        "rating_life_hours": item.life.value.to("hour").magnitude,
        "interval_hours": item.interval.to("hour").magnitude,
        "spares_over_service_life": float(spare.quantity),
        "items_without_a_life_basis": float(len(plan.without_a_life_basis)),
        "card_is_passing": float(card.status is CheckStatus.PASS),
        "plan_is_not_a_record": float(plan.status is CheckStatus.NOT_EVALUATED),
    }


def main() -> None:
    card = screen_rolling_bearing(PULLEY_BEARING)
    plan = plan_service_life(
        card,
        rules=(REPLACE_AT_HALF_LIFE,),
        item_paths={"bearing rating life": "conveyor/pulley bearing"},
        spares={"bearing rating life": "6310-2RS1"},
        product_items=PRODUCT_ITEMS,
        service_life=SERVICE_LIFE,
        duty_per_year=DUTY_PER_YEAR,
    )
    print(card)
    for entry in card.entries:
        print(f"[{entry.status.name}] {entry.name}: {entry.detail}")
    print()
    print(plan.summary())
    print(plan.schedule())
    print()
    for line in plan.spares():
        print(line)


if __name__ == "__main__":
    main()
