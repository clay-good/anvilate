"""The margin ledger: every conservatism applied to a result, recorded and multiplied out.

No-silent-green refuses a pass that was not earned. This module is its mirror: a pass that
was *over*-earned in silence. A code factor of 1.5, an elected 2.0 on top, a statistical
allowable, a load contingency and a thickness snapped up to stock are each defensible alone;
their product is a part several times heavier than the physics asks, and nothing states it.

A :class:`MarginEntry` is one factor: its value, its :class:`MarginKind`, the quantity it
bears on, whether it raises the demand or lowers the capacity, the origin that introduced it
and the authority that justifies it. A blank origin or authority is refused — a factor nobody
can attribute is indistinguishable from an arbitrary one.

A :class:`MarginLedger` holds the entries and answers, per quantity, with a
:class:`MarginStack`: the cumulative factor with its multiplication itemized, the
physics-limited factor (code-required entries only), the dominant entries with ties kept as
ties, and every same-kind pair from different origins named as a possible double count.
An empty stack says the quantity carries no recorded conservatism rather than rendering blank.

The ledger informs and never decides: it does not remove, reduce or recommend relaxing any
factor, and a verdict computed with every factor stands unchanged beside it.
"""

from __future__ import annotations

from enum import StrEnum
from math import isclose, isfinite, prod
from typing import Self

from pydantic import ConfigDict, model_validator

from ._models import ItemCollection, Named, StatableModel, cited

__all__ = [
    "MarginKind",
    "MarginAction",
    "MarginEntry",
    "DoubleCount",
    "MarginStack",
    "MarginLedger",
]


class MarginKind(StrEnum):
    """Why a factor is there. Obligation and choice are different evidence."""

    CODE_REQUIRED = "code_required"
    USER_ELECTED = "user_elected"
    STATISTICAL_BASIS = "statistical_basis"
    CONTINGENCY = "contingency_or_growth"
    ROUNDING = "rounding"
    DERATING = "derating"


# The one place each kind is described, as a TOTAL map: (rendered label, whether a cited code
# obliges it, whether it is a multiplier inside a utilization). Every consumer below reads a
# kind through this table and nothing files a kind under an `else`, so a kind added to the
# enumeration and not here fails at import — loudly, before any consumer can quietly treat it
# as one of the existing six.
#
# Rounding is the one kind that is not a multiplier: a utilization computed on the stock size
# already contains it, in the geometry, and how strongly it moved the result (as t², t³) is
# the check's business. Dividing it out of that utilization would understate it.
_KINDS: dict[MarginKind, tuple[str, bool, bool]] = {
    MarginKind.CODE_REQUIRED: ("code-required", True, True),
    MarginKind.USER_ELECTED: ("user-elected", False, True),
    MarginKind.STATISTICAL_BASIS: ("statistical basis", False, True),
    MarginKind.CONTINGENCY: ("contingency/growth", False, True),
    MarginKind.ROUNDING: ("rounding", False, False),
    MarginKind.DERATING: ("derating", False, True),
}
if set(_KINDS) != set(MarginKind):
    raise RuntimeError(
        f"margin kinds without a description: {sorted(set(MarginKind) - set(_KINDS))}; "
        "every consumer of the ledger reads a kind through _KINDS"
    )


class MarginAction(StrEnum):
    """The direction a factor moves the result — both are conservative."""

    RAISES_DEMAND = "raises_demand"
    LOWERS_CAPACITY = "lowers_capacity"


_ORIGIN = cited(
    "what introduced the factor — the check, module, spec declaration or database record; "
    "a factor with no origin cannot be audited or de-duplicated"
)
_AUTHORITY = cited(
    "what justifies the factor — a standard clause with its edition, a company practice "
    "identifier, a cited reference, or the user's election recorded as such"
)


class MarginEntry(StatableModel):
    """One conservatism applied to one quantity, attributed.

    ``value`` is the factor as a multiplier of conservatism: 1.5 means the demand was raised,
    or the capacity lowered, by 1.5. A value below 1 would be *un*-conservative and is not a
    margin; exactly 1 is recorded honestly as a factor that moved nothing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Named
    kind: MarginKind
    value: float
    quantity: Named
    action: MarginAction
    origin: _ORIGIN
    authority: _AUTHORITY

    @model_validator(mode="after")
    def _a_margin(self) -> Self:
        if not isfinite(self.value) or self.value < 1.0:
            raise ValueError(
                f"margin '{self.label}' has value {self.value}; a conservatism factor is a "
                "finite number of at least 1 (1.5 raises a demand or lowers a capacity by "
                "1.5), and anything below 1 makes the result less conservative, not more"
            )
        return self

    @classmethod
    def rounding(
        cls,
        *,
        label: str,
        nominal: float,
        delivered: float,
        quantity: str,
        origin: str,
        authority: str,
    ) -> MarginEntry:
        """A capacity dimension snapped up to a stock size, as the ratio delivered/nominal.

        The ratio is the factor on the dimension itself; how strongly it moves a stress
        (as t², or t³) is the check's business and is not guessed here.
        """
        if not (isfinite(nominal) and nominal > 0 and isfinite(delivered)):
            raise ValueError(
                f"rounding '{label}' needs a positive finite nominal and a finite delivered "
                f"value; got nominal {nominal}, delivered {delivered}"
            )
        if delivered < nominal:
            raise ValueError(
                f"rounding '{label}' snapped {nominal:g} down to {delivered:g}; rounding in the "
                "unsafe direction is not a margin and must not be recorded as one"
            )
        return cls(
            label=f"{label} ({nominal:g} -> {delivered:g})",
            kind=MarginKind.ROUNDING,
            value=delivered / nominal,
            quantity=quantity,
            action=MarginAction.LOWERS_CAPACITY,
            origin=origin,
            authority=authority,
        )

    @property
    def code_required(self) -> bool:
        return _KINDS[self.kind][1]

    def __str__(self) -> str:
        on = "demand" if self.action is MarginAction.RAISES_DEMAND else "capacity"
        return (
            f"{self.label}: x{self.value:.4g} on {self.quantity} {on} "
            f"[{_KINDS[self.kind][0]}; {self.authority}; from {self.origin}]"
        )


class DoubleCount(StatableModel):
    """Two or more entries of one kind on one quantity, from different origins.

    Named, not resolved: every entry stays in the product, and the engineer decides.
    """

    model_config = ConfigDict(frozen=True)

    quantity: Named
    kind: MarginKind
    entries: tuple[MarginEntry, ...]

    @property
    def combined(self) -> float:
        return prod(e.value for e in self.entries)

    def __str__(self) -> str:
        origins = ", ".join(sorted({e.origin for e in self.entries}))
        return (
            f"possible double count on {self.quantity}: {len(self.entries)} "
            f"{_KINDS[self.kind][0]} factors combine to x{self.combined:.4g} (from {origins})"
        )


class MarginStack(StatableModel):
    """Every entry bearing on one quantity, and what they add up to."""

    model_config = ConfigDict(frozen=True)

    quantity: Named
    entries: tuple[MarginEntry, ...] = ()

    @property
    def cumulative(self) -> float:
        """The product of every factor — 1.0 over no entries."""
        return prod(e.value for e in self.entries)

    @property
    def physics_limited(self) -> float:
        """The product of the code-required factors alone."""
        return prod(e.value for e in self.entries if e.code_required)

    @property
    def elected(self) -> float:
        """The share of :attr:`cumulative` no cited code obliges."""
        return prod(e.value for e in self.entries if not e.code_required)

    def elected_entries(self) -> tuple[MarginEntry, ...]:
        return tuple(e for e in self.entries if not e.code_required)

    def physics_limited_utilization(self, delivered: float) -> float:
        """The utilization the same size reports with code-required factors only.

        ``delivered`` is the utilization computed at the delivered size with every factor
        applied. Each elected multiplier scales it linearly, so removing them divides by
        their product. Rounding is not divided out: it is already in the delivered size, so
        this is the delivered part judged at code minimum, not a smaller part. Information
        only: the delivered verdict is the one that stands.
        """
        if not isfinite(delivered) or delivered < 0:
            raise ValueError(
                f"delivered utilization must be a finite non-negative number; got {delivered}"
            )
        return delivered / prod(
            e.value for e in self.entries if not e.code_required and _KINDS[e.kind][2]
        )

    def multiplication(self) -> str:
        """The product itemized, e.g. ``1.5 x 1.333 x 1.1 = 2.2``."""
        if not self.entries:
            return f"no conservatism recorded on {self.quantity}"
        factors = " x ".join(f"{e.value:.4g}" for e in self.entries)
        return f"{factors} = {self.cumulative:.4g}"

    def dominant(self) -> tuple[MarginEntry, ...]:
        """The entry whose removal most reduces the product — every one of them on a tie.

        Removing entry *e* divides the product by *e*'s value, so the largest value dominates.
        Equal values are reported together rather than ranked by position.
        """
        if not self.entries:
            return ()
        top = max(e.value for e in self.entries)
        return tuple(e for e in self.entries if isclose(e.value, top, rel_tol=1e-12))

    def double_counts(self) -> tuple[DoubleCount, ...]:
        """Same kind, same quantity, more than one origin — keyed on kind, never on wording."""
        found = []
        for kind in MarginKind:
            same = tuple(e for e in self.entries if e.kind is kind)
            if len({e.origin for e in same}) > 1:
                found.append(DoubleCount(quantity=self.quantity, kind=kind, entries=same))
        return tuple(found)

    def __str__(self) -> str:
        if not self.entries:
            return f"{self.quantity}: no conservatism recorded"
        leaders = " and ".join(e.label for e in self.dominant())
        tie = " (tied)" if len(self.dominant()) > 1 else ""
        return (
            f"{self.quantity}: cumulative x{self.cumulative:.4g} ({self.multiplication()}), "
            f"code-required x{self.physics_limited:.4g}, elected x{self.elected:.4g}; "
            f"dominant{tie}: {leaders}"
        )


class MarginLedger(ItemCollection, StatableModel):
    """Every margin entry in a build. Entries are kept in the order they were applied."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[MarginEntry, ...] = ()

    def quantities(self) -> tuple[str, ...]:
        """Each quantity that carries at least one entry, in first-applied order."""
        return tuple(dict.fromkeys(e.quantity for e in self.entries))

    def stack(self, quantity: str) -> MarginStack:
        """The stack for ``quantity`` — an empty one, stated as such, if nothing bears on it."""
        return MarginStack(
            quantity=quantity,
            entries=tuple(e for e in self.entries if e.quantity == quantity),
        )

    def stacks(self) -> tuple[MarginStack, ...]:
        return tuple(self.stack(q) for q in self.quantities())

    def double_counts(self) -> tuple[DoubleCount, ...]:
        return tuple(d for s in self.stacks() for d in s.double_counts())

    def with_entry(self, entry: MarginEntry) -> MarginLedger:
        return MarginLedger(entries=(*self.entries, entry))

    def __str__(self) -> str:
        if not self.entries:
            return "margin ledger: no conservatism recorded"
        lines = [f"margin ledger: {len(self.entries)} entries"]
        lines += [f"  {s}" for s in self.stacks()]
        lines += [f"  {d}" for d in self.double_counts()]
        return "\n".join(lines)
