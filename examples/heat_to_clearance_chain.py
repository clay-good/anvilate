"""Worked example: an internal heat source, through a chain, to a clearance verdict.

A motor inside a sealed housing dissipates 12 W through a 2.5 K/W path. That heat is not
the finding. The finding is six links away: the rise warms the aluminium rail, the rail
grows, the growth eats the running clearance at the guide, and the clearance is what fails.

Each link declares what it consumes from the one before it, so the chain is data:

    heat rise -> rail growth -> running clearance -> clearance verdict
    rail stiffness -> mount frequency -> shock amplification

``run_chain`` evaluates them in dependency order — whatever order they were declared in —
hands each check the upstream value it declared, and refuses to run a check whose input was
never produced. The rise is 30.0 K, the 420 mm rail grows 0.291 mm, and the 0.250 mm design
clearance is gone: the guide runs 0.041 mm tight and the card fails.

Drop the heat source's own input and nothing downstream is computed from a default: every
check past it comes back not evaluated, naming the output it was waiting on and the check
at the head of the chain. That is the whole reason for declaring the dependency — a
displacement computed from a temperature nobody produced is a number with a verdict on it.

Run it directly (``python examples/heat_to_clearance_chain.py``).
"""

from __future__ import annotations

from anvilate.analysis.axial import axial_stiffness
from anvilate.analysis.dynamics import half_sine_shock_amplification, natural_frequency
from anvilate.analysis.thermal import free_thermal_expansion, temperature_rise
from anvilate.dependency import (
    ChainResult,
    CheckNode,
    Consumes,
    DependencyGraph,
    Output,
    run_chain,
)
from anvilate.scorecard import CheckStatus, Comparison, LimitSense, ScorecardEntry
from anvilate.units import Quantity

POWER = Quantity(magnitude=12.0, unit="W")
RESISTANCE = Quantity(magnitude=2.5, unit="K/W")
RAIL_LENGTH = Quantity(magnitude=420.0, unit="mm")
RAIL_AREA = Quantity(magnitude=240.0, unit="mm**2")
ALUMINIUM_CTE = Quantity(magnitude=23.1e-6, unit="1/K")
ALUMINIUM_E = Quantity(magnitude=68.9, unit="GPa")
CARRIAGE_MASS = Quantity(magnitude=1.8, unit="kg")
PULSE = Quantity(magnitude=11.0, unit="ms")
DESIGN_CLEARANCE = Quantity(magnitude=0.250, unit="mm")


def graph() -> DependencyGraph:
    """The chain, declared back to front to show that declaration order does not decide."""
    return DependencyGraph(
        nodes=(
            CheckNode(
                id="shock amplification",
                consumes=(
                    Consumes(
                        upstream="mount frequency",
                        output="f_n",
                        parameter="natural_frequency",
                        dimension="[frequency]",
                    ),
                ),
            ),
            CheckNode(
                id="running clearance",
                produces=(Output(name="clearance", dimension="[length]"),),
                consumes=(
                    Consumes(
                        upstream="rail growth",
                        output="growth",
                        parameter="growth",
                        dimension="[length]",
                    ),
                ),
            ),
            CheckNode(
                id="mount frequency",
                produces=(Output(name="f_n", dimension="[frequency]"),),
                consumes=(
                    Consumes(
                        upstream="rail stiffness",
                        output="k",
                        parameter="stiffness",
                        dimension="[force] / [length]",
                    ),
                ),
            ),
            CheckNode(
                id="rail growth",
                produces=(Output(name="growth", dimension="[length]"),),
                consumes=(
                    Consumes(
                        upstream="heat rise",
                        output="delta_T",
                        parameter="temperature_change",
                        dimension="[temperature]",
                    ),
                ),
            ),
            CheckNode(
                id="heat rise", produces=(Output(name="delta_T", dimension="[temperature]"),)
            ),
            CheckNode(
                id="rail stiffness", produces=(Output(name="k", dimension="[force] / [length]"),)
            ),
        )
    )


def _passing(check: str, detail: str, outputs: dict[str, Quantity]) -> ChainResult:
    return ChainResult(
        check=check,
        entry=ScorecardEntry(name=check, status=CheckStatus.PASS, detail=detail),
        outputs=outputs,
    )


def run_check(check: str, inputs: dict[str, Quantity]) -> ChainResult:
    """One link, computed with the library's own closed-form functions."""
    if check == "heat rise":
        rise = temperature_rise(power=POWER, thermal_resistance=RESISTANCE)
        return _passing(check, f"{POWER} through {RESISTANCE} raises it {rise}", {"delta_T": rise})
    if check == "rail stiffness":
        stiffness = axial_stiffness(length=RAIL_LENGTH, area=RAIL_AREA, elastic_modulus=ALUMINIUM_E)
        return _passing(check, f"A·E/L = {stiffness}", {"k": stiffness})
    if check == "rail growth":
        growth = free_thermal_expansion(
            length=RAIL_LENGTH,
            thermal_expansion_coefficient=ALUMINIUM_CTE,
            temperature_change=inputs["temperature_change"],
        )
        return _passing(check, f"α·L·ΔT = {growth}", {"growth": growth})
    if check == "mount frequency":
        frequency = natural_frequency(stiffness=inputs["stiffness"], mass=CARRIAGE_MASS)
        return _passing(check, f"f_n = {frequency}", {"f_n": frequency})
    if check == "shock amplification":
        amplification = half_sine_shock_amplification(
            pulse_duration=PULSE, natural_frequency=inputs["natural_frequency"]
        )
        return ChainResult(
            check=check,
            entry=ScorecardEntry(
                name=check,
                status=CheckStatus.PASS,
                detail=f"a half-sine {PULSE} pulse is amplified {amplification:.2f}x",
            ),
        )
    if check == "running clearance":
        left = DESIGN_CLEARANCE.to("mm").magnitude - inputs["growth"].to("mm").magnitude
        remaining = Quantity(magnitude=left, unit="mm")
        comparison = Comparison(
            measured=remaining,
            limit=Quantity(magnitude=0.0, unit="mm"),
            sense=LimitSense.AT_LEAST,
            measured_label="clearance left",
            limit_label="minimum",
        )
        return ChainResult(
            check=check,
            entry=ScorecardEntry(
                name=check,
                status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
                detail=f"{DESIGN_CLEARANCE} design clearance less {inputs['growth']} of growth",
                comparison=comparison,
            ),
            outputs={"clearance": remaining},
        )
    raise AssertionError(f"no such check: {check}")  # pragma: no cover - the graph is fixed


def _cold_start(check: str, inputs: dict[str, Quantity]) -> ChainResult:
    """The same chain with the heat source unmeasured, to show the gap propagating."""
    if check == "heat rise":
        return ChainResult(
            check=check,
            entry=ScorecardEntry(
                name=check,
                status=CheckStatus.NOT_EVALUATED,
                detail="the dissipation of this motor was never measured",
            ),
        )
    return run_check(check, inputs)


def chain_figures() -> dict[str, object]:
    """Every figure this example's prose quotes, computed."""
    run = run_chain(graph(), run_check)
    clearance = run.result("running clearance")
    blocked = run_chain(graph(), _cold_start)
    return {
        "rise_K": run.result("heat rise").outputs["delta_T"].to("K").magnitude,
        "growth_mm": run.result("rail growth").outputs["growth"].to("mm").magnitude,
        "clearance_left_mm": clearance.outputs["clearance"].to("mm").magnitude,
        "tight_by_mm": -clearance.outputs["clearance"].to("mm").magnitude,
        "design_clearance_mm": DESIGN_CLEARANCE.to("mm").magnitude,
        "status": run.card().status,
        "blocked_count": sum(
            1 for result in blocked.results if result.entry.status is CheckStatus.NOT_EVALUATED
        ),
        "order": run.order,
    }


def main() -> None:
    run = run_chain(graph(), run_check)
    print(run)
    # The card, not the raw results: each check that ran on upstream values names them.
    for entry in run.card().entries:
        print(f"  {entry.name}: {entry.detail}")
    clearance = run.result("running clearance")
    assert clearance.entry.comparison is not None
    print(f"  {clearance.entry.comparison.sentence()}")
    left = clearance.outputs["clearance"].to("mm").magnitude
    print(f"  the guide runs {-left:.3f} mm tight")
    print(f"\ncard: {run.card().status.value.upper()}")
    print("\nwith the heat source unmeasured:")
    print(run_chain(graph(), _cold_start))
    print("  " + run_chain(graph(), _cold_start).result("running clearance").entry.detail)


if __name__ == "__main__":
    main()
