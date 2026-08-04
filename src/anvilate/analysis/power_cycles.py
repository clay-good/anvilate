"""T1 analytical air-standard power-cycle efficiencies (closed-form).

The ideal thermal efficiency of a heat engine or gas turbine follows from its compression alone —
the air-standard cycles give clean closed forms that set the ceiling a real engine works toward.

The Otto cycle (the spark-ignition engine) depends only on the compression ratio r and the specific-
heat ratio γ: η = 1 − 1/r^(γ−1). Squeezing the charge harder raises efficiency, which is why engines
run as high a compression ratio as knock allows.

The Diesel cycle adds a cutoff ratio r_c (how far combustion extends the volume at constant
pressure): η = 1 − (1/r^(γ−1))·(r_c^γ − 1)/(γ·(r_c − 1)). At the same compression ratio a diesel is
slightly less efficient than an Otto cycle, but it tolerates far higher compression, so real
diesels win.

The Brayton cycle (the gas turbine) depends on the pressure ratio r_p:
η = 1 − 1/r_p^((γ−1)/γ). All three assume air as an ideal gas with constant specific heats; the
specific-heat ratio γ (≈ 1.4 for air) is the caller's.
"""

from __future__ import annotations

__all__ = [
    "brayton_cycle_efficiency",
    "diesel_cycle_efficiency",
    "otto_cycle_efficiency",
]


def otto_cycle_efficiency(*, compression_ratio: float, specific_heat_ratio: float = 1.4) -> float:
    """The air-standard Otto-cycle efficiency, η = 1 − 1/r^(γ−1).

    The ideal thermal efficiency of a spark-ignition engine from its ``compression_ratio`` r (the
    cylinder volume at bottom dead centre over that at top) and the ``specific_heat_ratio`` γ (≈ 1.4
    for air): η = 1 − 1/r^(γ−1). It depends on nothing but the compression ratio — the reason
    raising compression (until knock intervenes) is the efficiency lever. Returns the efficiency as
    a fraction.
    """
    if compression_ratio <= 1:
        raise ValueError("compression_ratio must be greater than 1")
    if specific_heat_ratio <= 1:
        raise ValueError("specific_heat_ratio must be greater than 1")
    return 1.0 - 1.0 / compression_ratio ** (specific_heat_ratio - 1.0)


def diesel_cycle_efficiency(
    *,
    compression_ratio: float,
    cutoff_ratio: float,
    specific_heat_ratio: float = 1.4,
) -> float:
    """The air-standard Diesel-cycle efficiency, η = 1 − (1/r^(γ−1))·(r_c^γ − 1)/(γ·(r_c − 1)).

    The ideal efficiency of a compression-ignition engine, from its ``compression_ratio`` r, the
    ``cutoff_ratio`` r_c (the volume ratio over which combustion adds heat at constant pressure),
    and the ``specific_heat_ratio`` γ: η = 1 − (1/r^(γ−1))·(r_c^γ − 1)/(γ·(r_c − 1)). The cutoff
    term is always greater than 1, so at equal compression a diesel is a little less than an Otto
    cycle — but diesels run much higher compression, so they win in practice. As r_c → 1 (heat added
    at constant volume) it reduces to the Otto efficiency. Returns the efficiency as a fraction.
    """
    if compression_ratio <= 1:
        raise ValueError("compression_ratio must be greater than 1")
    if cutoff_ratio <= 1:
        raise ValueError("cutoff_ratio must be greater than 1")
    if specific_heat_ratio <= 1:
        raise ValueError("specific_heat_ratio must be greater than 1")
    g = specific_heat_ratio
    cutoff_term = (cutoff_ratio**g - 1.0) / (g * (cutoff_ratio - 1.0))
    return 1.0 - cutoff_term / compression_ratio ** (g - 1.0)


def brayton_cycle_efficiency(*, pressure_ratio: float, specific_heat_ratio: float = 1.4) -> float:
    """The air-standard Brayton-cycle efficiency, η = 1 − 1/r_p^((γ−1)/γ).

    The ideal efficiency of a gas turbine from its ``pressure_ratio`` r_p (compressor discharge over
    inlet pressure) and the ``specific_heat_ratio`` γ: η = 1 − 1/r_p^((γ−1)/γ). A higher pressure
    ratio raises efficiency, though the useful work peaks at a finite ratio the temperature limit
    sets — a trade this ideal form does not show. Returns the efficiency as a fraction.
    """
    if pressure_ratio <= 1:
        raise ValueError("pressure_ratio must be greater than 1")
    if specific_heat_ratio <= 1:
        raise ValueError("specific_heat_ratio must be greater than 1")
    g = specific_heat_ratio
    return 1.0 - 1.0 / pressure_ratio ** ((g - 1.0) / g)
