"""Worked example: converting a material's elastic constants for an FEA model.

An isotropic material's elasticity is fixed by any two constants, and analysis tools want different
pairs: a datasheet lists Young's modulus and Poisson's ratio, but a finite-element solver or the
elastic-wave relations want the bulk and shear moduli. This example converts a steel's E and Poisson
ratio into the bulk modulus and Lamé parameter, then closes the loop by recovering Young's modulus
from the bulk and shear moduli.

Steel has a Young's modulus of 200 GPa and a Poisson ratio of 0.3. Its bulk modulus works out to
about 167 GPa (resistance to uniform compression) and its Lamé first parameter to about 115 GPa.
With the shear modulus of about 77 GPa (E/2(1+nu)), the round-trip E = 9KG/(3K+G) recovers the
200 GPa, confirming the constants are consistent. The example reports the bulk modulus, the Lamé
parameter, and the Young's modulus recovered from the bulk and shear moduli.

Run it directly (``python examples/elastic_constants_conversion.py``);
:func:`convert_constants` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bulk_modulus_from_youngs_poisson,
    lame_first_parameter,
    youngs_modulus_from_bulk_shear,
)
from anvilate.units import Quantity

YOUNGS_MODULUS = Quantity.parse("200 GPa")
POISSON_RATIO = 0.3
SHEAR_MODULUS = Quantity(magnitude=200.0 / (2.0 * (1.0 + 0.3)), unit="GPa")  # E/2(1+nu) ~ 76.9 GPa


def convert_constants() -> dict[str, float]:
    """Return the bulk modulus, the Lamé parameter, and Young's modulus from bulk and shear."""
    bulk = bulk_modulus_from_youngs_poisson(
        elastic_modulus=YOUNGS_MODULUS, poisson_ratio=POISSON_RATIO
    )
    lame = lame_first_parameter(elastic_modulus=YOUNGS_MODULUS, poisson_ratio=POISSON_RATIO)
    youngs = youngs_modulus_from_bulk_shear(bulk_modulus=bulk, shear_modulus=SHEAR_MODULUS)
    return {
        "bulk_modulus_gpa": bulk.to("GPa").magnitude,
        "lame_parameter_gpa": lame.to("GPa").magnitude,
        "recovered_youngs_gpa": youngs.to("GPa").magnitude,
    }


def main() -> None:
    d = convert_constants()
    print(f"bulk modulus: {d['bulk_modulus_gpa']:.0f} GPa")
    print(f"Lame first parameter: {d['lame_parameter_gpa']:.0f} GPa")
    print(f"Young's modulus recovered from K and G: {d['recovered_youngs_gpa']:.0f} GPa")


if __name__ == "__main__":
    main()
