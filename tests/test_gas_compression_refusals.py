"""Gas-compression refusals identify the input and the record needed to repair it."""

import pytest

from anvilate.analysis import gas_compression as gas
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def q(text):
    return Quantity.parse(text)


@pytest.mark.parametrize(
    "function", [gas.optimal_stage_pressure_ratio, gas.multistage_compression_power]
)
@pytest.mark.parametrize("stages", [True, False, 1.5, 2.0, "2", None, 0, -1])
def test_stage_count_requires_a_positive_integer(function, stages):
    kwargs = {"overall_pressure_ratio": 9.0, "stages": stages}
    if function is gas.multistage_compression_power:
        kwargs.update(
            volumetric_flow=q("1 m**3/s"), inlet_pressure=q("100 kPa"), heat_capacity_ratio=1.4
        )
    with pytest.raises(ValueError) as caught:
        function(**kwargs)
    assert isinstance(caught.value, RefusalError)
    assert caught.value.remedies[0].subject == "stages"
    assert "compressor" in caught.value.remedies[0].source


@pytest.mark.parametrize(
    "function, kwargs, subject",
    [
        (
            gas.ideal_gas_density,
            {
                "pressure": q("0 Pa"),
                "temperature": q("300 K"),
                "specific_gas_constant": q("287 J/(kg*K)"),
            },
            "pressure, temperature, and specific_gas_constant",
        ),
        (
            gas.isothermal_compression_power,
            {"volumetric_flow": q("1 m**3/s"), "inlet_pressure": q("100 kPa"), "pressure_ratio": 1},
            "pressure_ratio",
        ),
        (
            gas.adiabatic_compression_power,
            {
                "volumetric_flow": q("1 m**3/s"),
                "inlet_pressure": q("100 kPa"),
                "pressure_ratio": 3,
                "heat_capacity_ratio": 1,
            },
            "heat_capacity_ratio",
        ),
        (
            gas.adiabatic_discharge_temperature,
            {"inlet_temperature": q("0 K"), "pressure_ratio": 3, "heat_capacity_ratio": 1.4},
            "inlet_temperature",
        ),
        (
            gas.compressor_volumetric_efficiency,
            {"clearance_fraction": 0.9, "pressure_ratio": 10, "polytropic_exponent": 1},
            "clearance_fraction, pressure_ratio, and polytropic_exponent",
        ),
        (
            gas.ideal_gas_density,
            {
                "pressure": q("1 m"),
                "temperature": q("300 K"),
                "specific_gas_constant": q("287 J/(kg*K)"),
            },
            "pressure",
        ),
        (
            gas.ideal_gas_density,
            {"pressure": 1, "temperature": q("300 K"), "specific_gas_constant": q("287 J/(kg*K)")},
            "pressure",
        ),
    ],
)
def test_refusal_has_a_machine_readable_repair(function, kwargs, subject):
    with pytest.raises(ValueError) as caught:
        function(**kwargs)
    assert isinstance(caught.value, RefusalError)
    remedy = caught.value.remedies[0]
    assert remedy.action == "replace"
    assert remedy.subject == subject
    assert remedy.source


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize(
    "function, field, kwargs",
    [
        (
            gas.isothermal_compression_power,
            "pressure_ratio",
            {"volumetric_flow": q("1 m**3/s"), "inlet_pressure": q("100 kPa")},
        ),
        (
            gas.adiabatic_compression_power,
            "heat_capacity_ratio",
            {"volumetric_flow": q("1 m**3/s"), "inlet_pressure": q("100 kPa"), "pressure_ratio": 3},
        ),
        (
            gas.multistage_compression_power,
            "heat_capacity_ratio",
            {
                "volumetric_flow": q("1 m**3/s"),
                "inlet_pressure": q("100 kPa"),
                "overall_pressure_ratio": 9,
                "stages": 2,
            },
        ),
        (
            gas.compressor_volumetric_efficiency,
            "polytropic_exponent",
            {"clearance_fraction": 0.05, "pressure_ratio": 3},
        ),
    ],
)
def test_nonfinite_scalar_names_the_input(function, field, kwargs, value):
    with pytest.raises(ValueError) as caught:
        function(**kwargs, **{field: value})
    assert isinstance(caught.value, RefusalError)
    assert caught.value.remedies[0].subject == field


def test_valid_stage_counts_keep_the_numerical_result():
    assert gas.optimal_stage_pressure_ratio(overall_pressure_ratio=27, stages=3) == pytest.approx(3)
    kwargs = {
        "volumetric_flow": q("1 m**3/s"),
        "inlet_pressure": q("100 kPa"),
        "heat_capacity_ratio": 1.4,
    }
    single = gas.adiabatic_compression_power(pressure_ratio=9, **kwargs)
    multi = gas.multistage_compression_power(overall_pressure_ratio=9, stages=1, **kwargs)
    assert multi.magnitude == pytest.approx(single.magnitude)
