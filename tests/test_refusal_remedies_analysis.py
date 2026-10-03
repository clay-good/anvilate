"""Structured remedies on analysis-module refusals (interaction-quality 2.1).

One case per migrated module at least: the refusal is a ``RefusalError`` that is still a
``ValueError``, and its remedy names the rejected input and where a correct value comes from.
Whether every site in a module is migrated is held by tests/test_raised_refusal_ledger.py.
"""

from __future__ import annotations

import pytest

from anvilate import analysis
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


_CASES = (
    (
        "luminous_efficacy",
        {"luminous_flux": _q("800 lm"), "electrical_power": _q("0 W")},
        "electrical_power",
        "the lamp's rated or measured electrical input power",
    ),
    (
        "luminous_efficiency",
        {"luminous_efficacy": _q("1000 lm/W")},
        "luminous_efficacy",
        "the lamp's photometric test report (integrating-sphere or goniophotometer)",
    ),
    (
        "wave_speed",
        {"frequency": _q("440 Hz"), "wavelength": _q("0 m")},
        "wavelength",
        "the measured or specified wavelength",
    ),
    (
        "wavelength_from_frequency",
        {"frequency": _q("440 Hz"), "wave_speed": _q("343 m")},
        "wave_speed",
        "the cited wave speed for the propagation medium and wave type",
    ),
    (
        "flange_coupling_torque",
        {
            "bolt_shear_force": _q("10 kN"),
            "bolt_circle_radius": _q("60 mm"),
            "num_bolts": 0,
        },
        "num_bolts",
        "the coupling drawing (bolt count and bolt-circle radius)",
    ),
    (
        "flange_coupling_bolt_count",
        {
            "torque": _q("2 kN*m"),
            "bolt_circle_radius": _q("60 mm"),
            "allowable_bolt_force": _q("0 kN"),
        },
        "allowable_bolt_force",
        "the bolt's rated or allowable shear capacity from its grade record",
    ),
    (
        "power_screw_raise_torque",
        {
            "load": _q("10 kN"),
            "mean_diameter": _q("10 mm"),
            "lead": _q("40 mm"),
            "friction_coefficient": 0.9,
        },
        "friction_coefficient and lead",
        "the thread friction record and screw drawing (square-thread range)",
    ),
    (
        "lead_angle",
        {"mean_diameter": _q("30 mm"), "lead": _q("-6 mm")},
        "lead",
        "the screw drawing or thread standard (mean diameter and lead)",
    ),
    (
        "thermionic_current_density",
        {"temperature": _q("0 K"), "work_function": _q("4.5 eV")},
        "temperature",
        "the cathode's measured or specified absolute operating temperature",
    ),
    (
        "child_langmuir_current_density",
        {"anode_voltage": _q("100 V"), "gap": _q("1 s")},
        "gap",
        "the electrode drawing and supply voltage specification",
    ),
    (
        "hydraulic_press_output_force",
        {
            "input_force": _q("100 N"),
            "input_piston_area": _q("10 cm**2"),
            "output_piston_area": _q("0 cm**2"),
        },
        "output_piston_area",
        "the cylinder drawing or catalogue piston bore",
    ),
    (
        "hydraulic_press_input_stroke",
        {
            "output_stroke": _q("-1 mm"),
            "input_piston_area": _q("10 cm**2"),
            "output_piston_area": _q("100 cm**2"),
        },
        "output_stroke",
        "the press stroke requirement or measured ram travel",
    ),
    (
        "hydraulic_retention_time",
        {"volume": _q("500 m**3"), "flow_rate": _q("0 m**3/h")},
        "flow_rate",
        "the plant's design flow basis or metered flow record",
    ),
    (
        "weir_loading_rate",
        {"flow_rate": _q("100 m**3/h"), "weir_length": _q("0 m")},
        "weir_length",
        "the basin drawing (volume, surface area, and weir length)",
    ),
    (
        "slider_crank_displacement",
        {"crank_radius": _q("50 mm"), "rod_length": _q("40 mm"), "crank_angle": 0.5},
        "rod_length",
        "the mechanism drawing (crank radius and connecting-rod length)",
    ),
    (
        "slider_crank_velocity",
        {
            "crank_radius": _q("50 mm"),
            "rod_length": _q("200 mm"),
            "crank_angle": 0.5,
            "crank_speed": _q("3000 m"),
        },
        "crank_speed",
        "the crank's rated or measured rotational speed",
    ),
    (
        "sutherland_viscosity",
        {
            "temperature": _q("300 K"),
            "reference_viscosity": _q("1.716e-5 Pa*s"),
            "reference_temperature": _q("0 K"),
            "sutherland_constant": _q("110.4 K"),
        },
        "reference_temperature",
        "the cited Sutherland reference values and constant for the gas",
    ),
    (
        "prandtl_number",
        {
            "dynamic_viscosity": _q("1.8e-5 Pa*s"),
            "specific_heat": _q("-1005 J/(kg*K)"),
            "thermal_conductivity": _q("0.026 W/(m*K)"),
        },
        "specific_heat",
        "the cited gas property table at the operating state",
    ),
    (
        "conveyor_mass_flow",
        {
            "bulk_density": _q("1600 kg/m**3"),
            "cross_section_area": _q("0 m**2"),
            "belt_speed": _q("2 m/s"),
        },
        "cross_section_area",
        "the belt drawing and troughing-idler load cross-section",
    ),
    (
        "conveyor_lift_power",
        {"mass_flow": _q("100 kg/s"), "lift_height": _q("-5 m")},
        "lift_height",
        "the conveyor profile drawing (net lift)",
    ),
    (
        "rittinger_comminution_energy",
        {
            "rittinger_constant": _q("1 kW*h*mm/t"),
            "feed_size": _q("1 mm"),
            "product_size": _q("2 mm"),
        },
        "feed_size and product_size",
        "the circuit's feed and product size distributions (screen analyses)",
    ),
    (
        "air_receiver_holdup_time",
        {
            "receiver_volume": _q("1 m**3"),
            "max_pressure": _q("6 bar"),
            "min_pressure": _q("7 bar"),
            "net_demand": _q("1 m**3/min"),
            "atmospheric_pressure": _q("1 atm"),
        },
        "max_pressure and min_pressure",
        "the compressor control settings (cut-in and cut-out pressures)",
    ),
    (
        "valve_authority",
        {"valve_pressure_drop": _q("0 kPa"), "system_pressure_drop": _q("0 kPa")},
        "valve_pressure_drop and system_pressure_drop",
        "the piping system's hydraulic calculation of pressure drops",
    ),
    (
        "block_coefficient",
        {
            "displacement_volume": _q("200 m**3"),
            "waterline_length": _q("10 m"),
            "beam": _q("3 m"),
            "draft": _q("1 m"),
        },
        "displacement_volume, waterline_length, beam, and draft",
        "the lines plan or hydrostatic tables (waterline length, beam, draft, displacement)",
    ),
    (
        "cyclone_cut_diameter",
        {
            "gas_viscosity": _q("1.8e-5 Pa*s"),
            "inlet_width": _q("0.2 m"),
            "effective_turns": 6.0,
            "inlet_velocity": _q("15 m/s"),
            "particle_density": _q("1 kg/m**3"),
            "gas_density": _q("1.2 kg/m**3"),
        },
        "particle_density and gas_density",
        "the dust's measured particle density and size distribution",
    ),
    (
        "vortex_shedding_frequency",
        {"strouhal_number": 0.2, "velocity": _q("10 m/s"), "characteristic_length": _q("0 m")},
        "characteristic_length",
        "the member drawing (cross-section width or diameter) and mass properties",
    ),
    (
        "salt_rejection",
        {"permeate_concentration": _q("2 g/L"), "feed_concentration": _q("1 g/L")},
        "permeate_concentration and feed_concentration",
        "the feed and permeate water analyses",
    ),
    (
        "relativistic_velocity_addition",
        {"first_velocity": _q("3e8 m/s"), "second_velocity": _q("1 m/s")},
        "first_velocity and second_velocity",
        "the measured or specified speed relative to the observer",
    ),
    (
        "parabolic_cable_sag",
        {
            "weight_per_length": _q("100 N/m"),
            "span": _q("100 m"),
            "horizontal_tension": _q("1 N"),
        },
        "weight_per_length, span, and horizontal_tension",
        "the load, span, and tension, or the catenary forms for a deep sag",
    ),
    (
        "coefficient_of_restitution_from_rebound",
        {"drop_height": _q("1 m"), "rebound_height": _q("2 m")},
        "rebound_height and drop_height",
        "the drop-test record (drop and rebound heights)",
    ),
    (
        "cooling_tower_approach",
        {"cold_water_temperature": _q("290 K"), "wet_bulb_temperature": _q("295 K")},
        "cold_water_temperature and wet_bulb_temperature",
        "the tower's design or measured water and wet-bulb temperatures",
    ),
    (
        "led_series_resistor",
        {
            "supply_voltage": _q("2 V"),
            "forward_voltage": _q("3 V"),
            "forward_current": _q("20 mA"),
        },
        "supply_voltage and forward_voltage",
        "the LED datasheet's forward voltage and current and the supply rail",
    ),
    (
        "voltage_standing_wave_ratio",
        {"reflection_coefficient": 1.0},
        "reflection_coefficient",
        "the measured or computed reflection coefficient or VSWR",
    ),
    (
        "projectile_launch_angle_for_range",
        {"launch_speed": _q("10 m/s"), "target_range": _q("1 km"), "high_trajectory": False},
        "target_range and launch_speed",
        "the target's surveyed range",
    ),
    (
        "coupling_coefficient",
        {
            "mutual_inductance": _q("2 H"),
            "primary_inductance": _q("1 H"),
            "secondary_inductance": _q("1 H"),
        },
        "mutual_inductance, primary_inductance, and secondary_inductance",
        "the coil datasheet or measured inductances and turn count",
    ),
    (
        "barometric_altitude",
        {
            "sea_level_pressure": _q("101325 Pa"),
            "pressure": _q("110000 Pa"),
            "temperature": _q("288 K"),
        },
        "pressure and sea_level_pressure",
        "the site's surveyed altitude or measured pressure",
    ),
    (
        "point_source_illuminance",
        {"luminous_intensity": _q("100 cd"), "distance": _q("2 m"), "incidence_angle": 2.0},
        "incidence_angle",
        "the lighting layout (luminaire count, distances, and aiming angles)",
    ),
    (
        "rms_torque_over_cycle",
        {"torques": [_q("1 N*m"), _q("-1 N*m")], "durations": [_q("1 s"), _q("1 s")]},
        "torques",
        "the motion profile (travel, move time, acceleration, and duty cycle)",
    ),
)


@pytest.mark.parametrize(
    ("function_name", "kwargs", "subject", "source"),
    _CASES,
    ids=[f"{case[0]}-{case[2]}" for case in _CASES],
)
def test_analysis_refusal_carries_a_structured_remedy(function_name, kwargs, subject, source):
    with pytest.raises(ValueError) as refused:
        getattr(analysis, function_name)(**kwargs)

    assert isinstance(refused.value, RefusalError)
    assert [remedy.model_dump() for remedy in refused.value.remedies] == [
        {"action": "replace", "subject": subject, "source": source}
    ]


def _migrated_modules() -> set[str]:
    """Analysis modules with no line in the ledger of bare refusals."""
    from pathlib import Path

    root = Path(__file__).parents[1]
    ledger = root / "docs/api/raised-refusals-without-remedies.txt"
    pending = {
        line.rsplit(" ", 1)[0]
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    return {
        path.stem
        for path in (root / "src/anvilate/analysis").glob("*.py")
        if not path.stem.startswith("_") and path.relative_to(root).as_posix() not in pending
    }


def test_a_migrated_module_names_a_parameter_in_every_remedy_it_raises():
    """Bind every required parameter to a bare number, as the front-door probe does.

    In a module with no bare refusal left, whatever refusal the call meets must carry a
    remedy whose subject names one of the function's own parameters. The per-case table
    above pins the exact source text; this sweep is what reaches every migrated function.
    """
    import inspect

    migrated = _migrated_modules()
    probed, failures = [], []
    for name in sorted(analysis.__all__):
        function = getattr(analysis, name)
        if not inspect.isfunction(function):
            continue
        if function.__module__.rsplit(".", 1)[-1] not in migrated:
            continue
        parameters = [
            p.name
            for p in inspect.signature(function).parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        ]
        if not parameters:
            continue
        probed.append(name)
        try:
            function(**dict.fromkeys(parameters, 1.0))
        except RefusalError as refusal:
            if not any(
                parameter in remedy.subject
                for remedy in refusal.remedies
                for parameter in parameters
            ):
                failures.append(f"{name}: {[str(r) for r in refusal.remedies]}")
        except ValueError as refusal:
            failures.append(f"{name}: unstructured {type(refusal).__name__}: {refusal}")

    # The floor goes first in spirit: an empty migration list would pass vacuously.
    assert len(probed) > 100, f"only {len(probed)} migrated functions were probed"
    assert not failures, "\n".join(failures)


def test_every_literal_remedy_subject_names_a_public_parameter():
    """interaction-quality 7.3: a remedy's subject must be something a caller can resolve.

    Fifty subjects read as prose — "sun and ring tooth counts", "doubly reinforced section
    inputs" — which a person follows and a program cannot. Each subject written as a literal
    must contain the name of a parameter of one of its module's public functions; a subject
    computed at run time is held by the bare-number sweep above instead.
    """
    import ast
    import re
    from pathlib import Path

    from conftest import parsed_source

    root = Path(__file__).parents[1] / "src/anvilate/analysis"
    checked, prose = 0, []
    for path in sorted(root.glob("*.py")):
        tree = parsed_source(path)
        public = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                arguments = node.args
                public |= {
                    a.arg for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs
                }
                if arguments.vararg is not None:
                    public.add(arguments.vararg.arg)
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                public |= {
                    field.target.id
                    for field in node.body
                    if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name)
                }
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and not method.name.startswith("_"):
                        arguments = method.args
                        public |= {a.arg for a in arguments.args + arguments.kwonlyargs}
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.keyword)
                and node.arg == "subject"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            checked += 1
            if not set(re.findall(r"[A-Za-z_]\w*", node.value.value)) & public:
                prose.append(f"{path.name}:{node.value.lineno}: {node.value.value!r}")

    assert checked > 800, f"only {checked} literal subjects found"
    assert not prose, "\n".join(prose)


def test_a_public_functions_remedy_subjects_name_only_its_own_parameters():
    """The stricter form of the gate above, where the enclosing function is known.

    "Names a public parameter of the module" let a subject like "the tight_tension and
    slack_tension values" or "radius and tooth geometry" through on one matching word.
    Inside a public function (or a public class's methods and validators), a literal
    subject is a list of names joined by commas and "and", and every one of them must be a
    parameter of that function or a field of that class. Private helpers serve several
    public functions and stay under the module-level rule.
    """
    import ast
    import re
    from pathlib import Path

    from conftest import parsed_source

    def parameters(function: ast.FunctionDef) -> set[str]:
        a = function.args
        found = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
        return found | {x.arg for x in (a.vararg, a.kwarg) if x is not None}

    root = Path(__file__).parents[1] / "src/anvilate/analysis"
    checked, stray = 0, []
    for path in sorted(root.glob("*.py")):
        for top in parsed_source(path).body:
            scopes: list[tuple[ast.FunctionDef, set[str]]] = []
            if isinstance(top, ast.FunctionDef) and not top.name.startswith("_"):
                scopes = [(top, set())]
            if isinstance(top, ast.ClassDef) and not top.name.startswith("_"):
                fields = {
                    f.target.id
                    for f in top.body
                    if isinstance(f, ast.AnnAssign) and isinstance(f.target, ast.Name)
                }
                scopes = [(m, fields) for m in top.body if isinstance(m, ast.FunctionDef)]
            for function, fields in scopes:
                allowed = parameters(function) | fields
                for node in ast.walk(function):
                    if not (
                        isinstance(node, ast.keyword)
                        and node.arg == "subject"
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str)
                    ):
                        continue
                    checked += 1
                    named = [
                        name
                        for name in re.split(r",\s*|\s+and\s+|\s+", node.value.value)
                        if name and name != "and"
                    ]
                    unknown = [name for name in named if name not in allowed]
                    if unknown:
                        stray.append(
                            f"{path.name}:{node.value.lineno} {function.name}: "
                            f"{node.value.value!r} names {unknown}"
                        )

    assert checked > 3_000, f"only {checked} subjects inside public functions were checked"
    assert not stray, "\n".join(stray)


def test_a_split_guard_names_only_its_own_functions_parameters():
    """A guard over several inputs is split into `for subject, magnitude in ((name, x), ...)`.

    The names in that tuple are what the remedy will say, and they are strings, so neither
    subject gate above reads them. One said `"length"` for `rod_length`: the split had
    traced a local variable to a parameter of a different function in the same module.
    """
    import ast
    from pathlib import Path

    from conftest import parsed_source

    class Splits(ast.NodeVisitor):
        def __init__(self, path: Path) -> None:
            self.path, self.parameters = path, [set()]

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            a = node.args
            self.parameters.append({x.arg for x in a.posonlyargs + a.args + a.kwonlyargs})
            self.generic_visit(node)
            self.parameters.pop()

        def visit_For(self, node: ast.For) -> None:
            if (
                isinstance(node.target, ast.Tuple)
                and isinstance(node.target.elts[0], ast.Name)
                and node.target.elts[0].id == "subject"
                and isinstance(node.iter, ast.Tuple)
            ):
                for entry in node.iter.elts:
                    if isinstance(entry, ast.Tuple) and isinstance(entry.elts[0], ast.Constant):
                        found.append(entry.elts[0].value)
                        if entry.elts[0].value not in self.parameters[-1]:
                            stray.append(f"{self.path.name}:{entry.lineno}")
            self.generic_visit(node)

    found: list[str] = []
    stray: list[str] = []
    for path in sorted((Path(__file__).parents[1] / "src/anvilate").rglob("*.py")):
        Splits(path).visit(parsed_source(path))
    checked = len(found)

    assert checked > 600, f"only {checked} split-guard names found"
    assert not stray, "\n".join(stray)
