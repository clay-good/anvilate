# Anvilate documentation

Forty-six pages, arranged by what you are trying to do. The [README](../README.md) is the
argument for the whole thing; this is the map.

## Start here

You have a part and you want a verdict.

| | |
| --- | --- |
| [Quickstart](quickstart.md) | Install, screen a lifting lug, read the verdict. Ten minutes, no network, no CAD. |
| [`anvilate` on the command line](headless-cli.md) | Screen a spec, export its bundle, verify an attestation, diff two revisions. The exit codes are the interface, and **2 is not a pass**. |
| [Screening a Design Spec](spec-screening.md) | What a spec document alone can be screened on, and the tier that has to name a gap rather than run. |
| [Calculation reports](calculation-reports.md) | The submittal a reviewer reads: formula, substitution, result, clause. |
| [Values and units](units-and-quantities.md) | What a `Quantity` is, and the arithmetic it refuses so a value is never computed in one unit and read in another. |
| [What a citation means](citations.md) | What a clause reference does and does not claim, and where every bundled number came from. |

## Screening by discipline

Each pack takes a declared element and returns a cited scorecard.

| | |
| --- | --- |
| [Hot-rolled steel](hot-rolled-steel.md) · [Cold-formed steel](cold-formed-steel.md) · [Aluminum](aluminum-screening.md) | AISC 360, AISI S100, ADM 2020. |
| [Reinforced concrete](reinforced-concrete.md) · [Masonry](masonry-screening.md) · [Timber](timber-screening.md) | ACI 318, TMS 402, NDS. |
| [Geotechnical](geotechnical-screening.md) · [Hydraulics](hydraulics-screening.md) | Foundations, walls, seepage; pipes, channels, pumps. |
| [Pressure equipment](pressure-equipment.md) · [Process piping](process-piping.md) | ASME VIII Div 1, ASME B31.3. |
| [Lifting devices](lifting-devices.md) · [Industrial covers](industrial-covers.md) | ASME BTH-1; flat covers and guard panels. |
| [Building services](building-services-screening.md) | Noise dose, lighting, ventilation, feeders. |
| [Thermal](thermal-screening.md) · [Weld fatigue](weld-fatigue-screening.md) · [Fitness-for-service](fitness-for-service-screening.md) · [Embodied carbon](embodied-carbon-screening.md) | Resistance networks, EN 1993-1-9 detail categories, FAD assessment, EN 15978. |

## Deciding what the answer is worth

| | |
| --- | --- |
| [Uncertainty-aware margins](uncertainty-margins.md) | Input scatter to a shortfall probability, and what the number does not mean. |
| [Load combinations](load-combinations.md) | The governing combination named, including the uplift case a gravity-only check misses. |
| [Design-space exploration](design-space-exploration.md) | An exact Pareto front, because every check is closed-form. |
| [Typed repair feedback](repair-feedback.md) | The parameter and the value that fixes a failing check. |
| [Verification planning](verification-planning.md) | The physical test each check implies — and why a plan is never evidence. |
| [Responsible-charge review](responsible-charge-review.md) | What a licensed engineer needs before sealing. |

## Declaring the part

| | |
| --- | --- |
| [Requirements ingestion](requirements-ingestion.md) | An RFQ sheet to a *draft* spec, with a confirmation checklist. |
| [Semantic GD&T](semantic-gdt.md) · [Typed MBD callouts](typed-callouts.md) | Feature control frames and finish/plating/heat-treat as check inputs. |
| [Analysis interop](analysis-interop.md) | Externally computed forces and section properties, with every convention declared. |
| [Standards effectivity](standards-effectivity.md) | Which edition a citation means. |

## Getting the answer out

| | |
| --- | --- |
| [The evidence bundle](evidence-bundle.md) | One roll-up, never better than its worst section. |
| [Attested evidence](evidence-attestation.md) | The bundle sealed so somebody else can re-check it. |
| [The export gate](export-gating.md) | Nothing leaves past a failing card without a watermark saying so. |
| [Quality interchange](quality-interchange.md) | QIF Results out, calibration certificates in. |
| [Export targets](export-targets.md) | Where the export layer is pointed, and what was actually verified. |

## Driving it from an agent

| | |
| --- | --- |
| [Driving Anvilate from a coding agent](agent-mcp-integration.md) | The loop that works, and the half that is not callable yet. |
| [The MCP tool surface](mcp-tool-contracts.md) | Eight operations, two dispatch modes, and the four a stateless server cannot serve. |
| [The agent skill](agent-skill.md) | What correct use looks like, bound to the library by CI. |
| [The published contracts](published-contracts.md) | Spec IR and scorecard as JSON Schema 2020-12. |
| [Agent-driving evals](agent-driving-evals.md) | Whether a given local model can drive this, measured. |
| [A valid spec can still be the wrong spec](valid-is-not-correct.md) | Why schema validity is not correctness. |

## Contributing

[Adding a check to the analysis library](contributing-analysis.md) — the seven contract
rules, which of them a gate actually enforces, and the sweeps that find what the gates miss.
