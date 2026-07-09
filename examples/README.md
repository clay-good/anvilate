# Anvilate examples

Runnable, self-contained scripts that each exercise one deterministic Anvilate
vertical end to end — no LLM, no network. Every script here is executed by
`tests/test_examples.py` in CI, so they stay green as the library moves.

Run any of them directly:

```bash
python examples/cantilever_bracket_check.py
```

Each script exposes one named function (the one the test calls) so you can import
and reuse it. The DXF example additionally needs the `export` extra
(`pip install 'anvilate[export]'`).

## Structural pack — code-checked members (AISC 360 / ASME BTH-1)

| Example | What it shows |
|---|---|
| `cantilever_bracket_check.py` | A cantilever bracket screened for bending yield *and* deflection — passes yield but fails the deflection limit, so the scorecard is FAIL (no silent green). |
| `mezzanine_structure.py` | A whole structure — a floor beam on two posts — screened into one scorecard via `screen_structure`. |
| `brace_tie_check.py` | A bolted single-angle tension brace (AISC §D2): gross yielding passes comfortably, but shear lag makes net-section rupture govern. |
| `lifting_padeye.py` | A welded lifting padeye assembly (lug + fillet weld) screened together; flags an under-sized pin against the rigging safety factor. |
| `lug_drawing.py` | The full white-space vertical: code-check a lifting lug (ASME BTH-1), then export its plan outline to a fabrication DXF. |

## Mechanical — T1 analytical screens

| Example | What it shows |
|---|---|
| `bolted_joint_check.py` | A bolted lap joint: preload from torque, plate bearing, and bolt shear, all from the materials DB. |
| `motor_mount_resonance.py` | A cantilevered motor mount whose fundamental frequency falls below the running speed — a resonance FAIL. |
| `shrink_fit_check.py` | An ISO 286 interference fit (Ø40 H7/s6) turned into a thick-wall contact pressure and hub bore hoop stress, screened against yield. Ties the tolerance, analysis, and materials layers together. |
| `wheel_rail_contact.py` | A crane wheel on a rail screened for Hertzian line-contact surface pressure — annealed steel fails, the lesson that rolling-contact parts must be surface-hardened. |

## Tolerance & manufacturability

| Example | What it shows |
|---|---|
| `tolerance_stackup.py` | A 1D assembly stack-up analyzed worst-case, RSS, and Monte Carlo: worst-case rejects the design, yet the predicted assembly yield is 99%+. |
| `dfm_process_check.py` | A tolerance call-out screened against a process's capability floor — flags an unachievable band and suggests processes that can hold it. |

## Provenance

| Example | What it shows |
|---|---|
| `evidence_bundle.py` | Rolls every standards record a spec references (material, standard components, ISO 2768 / ISO 286 / ISO 1101) into an auditable, cited evidence trail. |

## Design Spec IR

| Example | What it shows |
|---|---|
| `load_and_validate_spec.py` | Loads the golden Design Spec from YAML, validates its references and dimension graph against the bundled databases, and proves it round-trips unchanged — the spec is the source of truth. |

`nema23_bracket.spec.yaml` is that golden-path Design Spec IR (schema 1.0.0),
loadable with `anvilate.spec.load_spec_yaml` — the typed, diffable representation a
prompt compiles into.
