"""Every signed field in every registered element, negated: the sign changes the card or is
declared to carry no information.

A field in `signed_fields` is exempt from the guard that refuses a negative magnitude, on
the ground that its sign means something. The screens did not always read it. A base plate
under 200 kN of uplift passed concrete bearing, because `strength_scorecard` takes the
stress's magnitude; a column in tension was buckled, and a tension member in compression
was screened for yielding. Six other screens computed a negative safety factor from a
negative demand and reported it as "the load is zero".

The library's contract, stated in tests/test_contract.py, is that a non-positive demand
screens to NOT_EVALUATED. So each signed field is negated in turn from the valid document in
`tests/element_params.json`, and the card must differ from the card of the original, unless
the field is one whose direction the physics does not see, named below with its cause.
"""

from __future__ import annotations

import copy
import inspect
import sys
from pathlib import Path

from anvilate.screening import element_registry

_PARAMS = Path(__file__).resolve().parent / "element_params.json"

# Fields whose sign is a direction the screened limit states do not depend on.
_DIRECTION_FREE = {
    "beam_column_member.moment": "a bending moment of either sign stresses the section alike",
    "beam_member.load": "a transverse load either way bends the beam by the same magnitude",
    "lifting_lug.load": "a pin load is along the lug's axis whichever way the scalar is written",
    "shear_plate.load": "shear yielding and rupture do not depend on the shear's direction",
    "welded_connection.load": "a fillet weld's throat shear does not depend on its direction",
}


def _card(model: type, screen: object, document: dict) -> object:
    keywords = (
        {"required_safety_factor": 2.0}
        if "required_safety_factor" in inspect.signature(screen).parameters
        else {}
    )
    try:
        element = model.model_validate(document)
        card = screen(element, **keywords)
    except (ValueError, LookupError) as refusal:
        return f"refused: {refusal}"
    return tuple(
        (entry.name, entry.status, entry.safety_factor, entry.detail) for entry in card.entries
    )


def _verdicts(card: object) -> object:
    """What the sign has to change: a detail may name a direction (an overhang's back span
    bowing up rather than down) without the verdict moving."""
    if isinstance(card, str):
        return card
    return tuple((name, status, factor) for name, status, factor, _detail in card)


def _flips() -> list[tuple[str, str, object, object]]:
    from test_element_zero_sweep import _corpus

    registry = element_registry()
    flips = []
    for label, element_type, document in _corpus():
        model, screen = registry[element_type]
        for field in getattr(model, "signed_fields", ()):
            value = document.get(field)
            if not isinstance(value, dict) or "magnitude" not in value:
                continue
            flipped = copy.deepcopy(document)
            flipped[field]["magnitude"] = -value["magnitude"]
            flips.append(
                (
                    f"{label}.{field}",
                    f"{element_type}.{field}",
                    _card(model, screen, document),
                    _card(model, screen, flipped),
                )
            )
    return flips


def test_a_signed_field_changes_the_card_or_is_declared_direction_free():
    flips = _flips()
    # The floor goes first: a corpus that lost its signed fields would find nothing.
    assert len(flips) >= 16, f"only {len(flips)} signed fields were negated"
    discarded = {
        field
        for _label, field, original, flipped in flips
        if _verdicts(original) == _verdicts(flipped)
    }
    read = {
        field
        for _label, field, original, flipped in flips
        if _verdicts(original) != _verdicts(flipped)
    }
    assert discarded <= set(_DIRECTION_FREE), (
        "these signed fields are screened by magnitude, so their sign is thrown away: "
        f"{sorted(discarded - set(_DIRECTION_FREE))}"
    )
    assert not (read & set(_DIRECTION_FREE)), (
        f"declared direction-free but now read their sign: {sorted(read & set(_DIRECTION_FREE))}"
    )
    assert set(_DIRECTION_FREE) <= discarded, sorted(set(_DIRECTION_FREE) - discarded)


def test_a_negative_demand_is_never_described_as_zero():
    said_zero = [
        f"{label}: {detail}"
        for label, _field, _original, flipped in _flips()
        if isinstance(flipped, tuple)
        for _name, _status, _factor, detail in flipped
        if " is zero" in detail
    ]
    assert not said_zero, "\n".join(said_zero)


def test_the_sweep_sees_a_screen_that_discards_the_sign(monkeypatch):
    """The adversary: screen the base plate on the load's magnitude again, as it was before
    this sweep existed, and the gate must name it."""
    from anvilate.packs import structural
    from anvilate.units import Quantity

    original = structural.screen_base_plate

    def by_magnitude(plate, *, required_safety_factor):  # type: ignore[no-untyped-def]
        load = plate.axial_load
        positive = Quantity(magnitude=abs(load.magnitude), unit=str(load.unit))
        return original(
            plate.model_copy(update={"axial_load": positive}),
            required_safety_factor=required_safety_factor,
        )

    registry = element_registry()
    model, _screen = registry["base_plate"]
    monkeypatch.setitem(registry, "base_plate", (model, by_magnitude))
    monkeypatch.setattr(sys.modules[__name__], "element_registry", lambda: registry)
    discarded = [field for _label, field, a, b in _flips() if _verdicts(a) == _verdicts(b)]
    assert "base_plate.axial_load" in discarded
