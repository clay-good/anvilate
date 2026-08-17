"""The magnitude guard every pack input model inherits.

Pack models validated their :class:`~anvilate.units.Quantity` fields by *dimension* and
never by *magnitude*. Dimension is the easy half: it catches a length typed where a
pressure belongs, which is a typo. Magnitude is the half that catches an arithmetic
mistake, and an arithmetic mistake is what a user actually makes.

The case that motivated this: ``TensionMember`` bounded ``net_area`` against
``gross_area`` by their *ordering* — net cannot exceed gross — and never against zero.
A net area of −500 mm², which is what you get by hand when you deduct one bolt hole too
many, satisfies that ordering trivially and screened to a **passing** scorecard on both
AISC §D2 limit states. Elsewhere the same gap produced a complex number: a negative
bearing area reaches ``√(A₂/A₁)`` and comes back with an imaginary part.

So the rule is uniform and lives in one place: a pack input model rejects a negative or
non-finite magnitude on every ``Quantity`` field. Zero is *allowed* — a cohesionless
sand has c = 0, a drained slope has u = 0, an untensioned bolt group has T = 0 — because
zero is a real engineering value, and the places where it divides already raise loudly
rather than passing quietly.

A field that is genuinely signed names itself in :attr:`GuardedInputs.signed_fields`.
That is a declaration, not an escape hatch: a hogging moment is negative for a reason,
and writing it down is how the next reader knows the omission was deliberate. The
contract gate in ``tests/test_contract.py`` requires every pack model carrying a
``Quantity`` field to inherit this class, so a new one cannot ship without the guard.
"""

from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, model_validator

from ..units import Quantity

__all__ = ["GuardedInputs"]


def _check_nested(model: BaseModel, prefix: str, _depth: int = 0) -> None:
    """Reject a negative or non-finite Quantity anywhere inside a nested input model.

    Nested models are geometry — a CrossSection, a section's properties — and geometry is
    positive-definite throughout, so there is no signed-field exemption to honour here.
    Depth is bounded because a self-referential model would otherwise recurse forever.
    """
    if _depth > 4:  # pragma: no cover - no input model nests this deep
        return
    for name in type(model).model_fields:
        value = getattr(model, name, None)
        # Quantity before BaseModel, always: Quantity IS a pydantic model, so testing for
        # BaseModel first recurses into it and checks nothing. That ordering mistake made
        # this whole guard silently inert once already.
        if isinstance(value, Quantity):
            if not isfinite(value.magnitude):
                raise ValueError(f"{prefix}.{name} must be a finite quantity; got {value}")
            if value.magnitude < 0:
                raise ValueError(
                    f"{prefix}.{name} must not be negative; got {value}. Nested input "
                    f"models describe geometry, which is positive-definite — a negative "
                    f"value here produces a negative section property that reads as extra "
                    f"capacity downstream."
                )
        elif isinstance(value, BaseModel):
            _check_nested(value, f"{prefix}.{name}", _depth + 1)


class GuardedInputs(BaseModel):
    """Base class for pack input models: no negative or non-finite quantity magnitudes.

    Subclasses list any genuinely signed field in :attr:`signed_fields`, which is checked
    for finiteness only. Everything else must be zero or positive.
    """

    #: Fields whose sign carries meaning (a hogging moment, a position measured either
    #: way from a datum). Checked for finiteness, not for sign.
    signed_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _quantity_magnitudes_are_sane(self) -> GuardedInputs:
        signed = set(type(self).model_fields["signed_fields"].default or ())
        for name in type(self).model_fields:
            if name == "signed_fields":
                continue
            value = getattr(self, name, None)
            # Quantity is ITSELF a pydantic model, so the nested-model branch has to come
            # second or it swallows every quantity field and the guard checks nothing.
            if not isinstance(value, Quantity):
                # A nested model is where the guard used to stop. Every member model
                # carries a CrossSection, a plain BaseModel with no sign validation of its
                # own, so an extreme_fibre of -25 mm produced a NEGATIVE section modulus
                # and turned a beam-column FAIL at 1.19 into a PASS at 6.34 — the same
                # silent green this guard was written for, one level down. A negative area
                # on the same object reaches sqrt(I/A) and comes back complex.
                if isinstance(value, BaseModel) and not isinstance(value, GuardedInputs):
                    _check_nested(value, name)
                continue
            if not isfinite(value.magnitude):
                raise ValueError(
                    f"{name} must be a finite quantity; got {value}. A NaN or an infinity "
                    f"here is an arithmetic accident upstream, and carrying it into a "
                    f"screen produces a verdict nobody can read."
                )
            if name not in signed and value.magnitude < 0:
                raise ValueError(
                    f"{name} must not be negative; got {value}. If the sign is meant to "
                    f"carry information, declare the field in this model's signed_fields."
                )
        return self
