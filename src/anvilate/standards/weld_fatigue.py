"""Welded-joint fatigue records fitted from bundled CC BY 4.0 test points.

The pack (``data/weld_fatigue.yaml``) carries constant-amplitude S-N test points, each
campaign copied from "A Dataset of Fatigue Properties for Welded Joints" (Deng et al.,
figshare, 2025) with the conditions it was tested under. This module turns each campaign
into a :class:`~anvilate.standards.fatigue.FatigueRecord`.

**The points are the data; the curve is a fit, and says so.** The dataset publishes no
curve, so the one a record carries is the least-squares line of log N on log Δσ through
the failed specimens, with N the dependent variable as ASTM E739 sets it out. It is a
**mean** curve (:attr:`~anvilate.standards.fatigue.CurveSurvival.MEAN`), so it answers a
mean requirement and declines a design one, and it covers the tested cycle range only:
from the shortest to the longest failure, with no extrapolation either side.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache
from importlib.resources import files
from math import log10

from .._models import _near_identifiers, parse_yaml
from ..units import Quantity
from .fatigue import (
    CurveSurvival,
    DatasetProvenance,
    FatigueCurve,
    FatigueRecord,
    FatigueSegment,
    LoadingMode,
    SpecimenGeometry,
    SpecimenMetadata,
    _fatigue_record_refusal,
)

__all__ = [
    "UnknownWeldFatigueRecordError",
    "WeldFatigueTable",
    "default_weld_fatigue_records",
    "mean_curve_from_failures",
]


class UnknownWeldFatigueRecordError(KeyError):
    """A requested campaign has no record in the pack."""

    def __init__(self, name: str, suggestions: list[str]) -> None:
        self.name = name
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no welded-joint fatigue record {name!r}{hint}")


class WeldFatigueTable:
    """The bundled campaigns' fatigue records, by pack name (``SM50B-CRUCIFORM-R0``)."""

    def __init__(self, records: dict[str, FatigueRecord]) -> None:
        self._records = records

    def designations(self) -> list[str]:
        return sorted(self._records)

    def get(self, name: str) -> FatigueRecord:
        """The record for ``name``, or :class:`UnknownWeldFatigueRecordError` with the
        names it nearly matches."""
        try:
            return self._records[name]
        except KeyError:
            raise UnknownWeldFatigueRecordError(
                name, _near_identifiers(name, self._records)
            ) from None

    __getitem__ = get

    def __iter__(self) -> Iterator[str]:
        return iter(self.designations())

    def __len__(self) -> int:
        return len(self._records)

    def items(self) -> list[tuple[str, FatigueRecord]]:
        return [(name, self._records[name]) for name in self.designations()]

    def values(self) -> list[FatigueRecord]:
        return [self._records[name] for name in self.designations()]


def mean_curve_from_failures(points: tuple[tuple[float, float], ...]) -> FatigueCurve:
    """The ASTM E739 mean S-N line through ``(stress range MPa, cycles to failure)`` pairs.

    ``log10 N = A + B log10 Δσ`` by least squares with N dependent, so the S-N exponent is
    ``m = -B``. The single segment is anchored at the longest failure and runs down to the
    shortest: the range the specimens cover, and nothing past it.
    """
    if len({stress for stress, _cycles in points}) < 2:
        raise _fatigue_record_refusal(
            "an S-N line needs failures at two or more stress ranges; at one there is no "
            "slope to fit",
            subject="points",
            source="the campaign's failed specimens, tested at more than one stress range",
        )
    xs = [log10(stress) for stress, _cycles in points]
    ys = [log10(cycles) for _stress, cycles in points]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    spread = sum((x - mean_x) ** 2 for x in xs)
    slope_b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / spread
    intercept = mean_y - slope_b * mean_x
    longest = max(cycles for _stress, cycles in points)
    # The fitted stress range at the longest failure: log10 Δσ = (log10 N - A) / B.
    reference = 10 ** ((log10(longest) - intercept) / slope_b)
    return FatigueCurve(
        survival=CurveSurvival.MEAN,
        segments=(
            FatigueSegment(
                slope=-slope_b,
                reference_stress_range=Quantity(magnitude=reference, unit="MPa"),
                reference_cycles=longest,
                max_cycles=longest,
            ),
        ),
        min_cycles=min(cycles for _stress, cycles in points),
    )


_LOADING = {"axial": LoadingMode.AXIAL, "bending": LoadingMode.BENDING}


@cache
def default_weld_fatigue_records() -> WeldFatigueTable:
    """Every bundled welded-joint campaign as a fatigue record, by its pack name."""
    text = (files("anvilate.standards") / "data" / "weld_fatigue.yaml").read_text(encoding="utf-8")
    document = parse_yaml(text)
    dataset = document["dataset"]
    records: dict[str, FatigueRecord] = {}
    for name, campaign in document["campaigns"].items():
        points = tuple((float(stress), float(cycles)) for stress, cycles in campaign["points"])
        thickness = campaign.get("thickness")
        records[name] = FatigueRecord(
            name=name,
            curve=mean_curve_from_failures(points),
            specimen=SpecimenMetadata(
                material=campaign["material"],
                geometry=SpecimenGeometry.WELDED_JOINT,
                loading_mode=_LOADING[campaign["loading_mode"]],
                environment=campaign["environment"],
                temperature=Quantity(**campaign["temperature"]),
                stress_ratio=float(campaign["stress_ratio"]),
                thickness=None if thickness is None else Quantity(**thickness),
                stress_concentration_factor=campaign.get("stress_concentration_factor"),
            ),
            provenance=DatasetProvenance(
                dataset=dataset["source"],
                # The compilation's own release, not this pack's version: the curve is
                # traceable to release 2 of the dataset whatever this file is numbered.
                version=dataset["release"],
                license=dataset["license"],
                retrieved=dataset["retrieved"],
                doi=dataset["doi"],
                specimen_count=len(points),
                publication=campaign["publication"],
            ),
        )
    # Cached, so every caller shares this object; the table exposes no way to change it.
    return WeldFatigueTable(records)
