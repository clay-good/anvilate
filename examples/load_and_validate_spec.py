"""Worked example: load a Design Spec from YAML, validate it, round-trip it.

Anvilate's first principle is that *the spec is the product, not the chat* — every
prompt compiles into a typed Design Spec IR the engineer can read, diff, save, and
rerun. This example works with that artifact directly, no LLM in sight: it loads
the golden-path ``nema23_bracket.spec.yaml``, checks that every external reference
it names (its material and standard components) resolves against the bundled
databases and that its dimension/chain graph is internally consistent, and proves
the IR round-trips through YAML unchanged.

The two validations are the gates the spec must pass before anything downstream
(geometry, checks, export) runs — reference resolution catches a typo'd material
or an unstocked part, and graph validation catches a chain that names a dimension
that was never declared.

Run it directly (``python examples/load_and_validate_spec.py``);
:func:`load_and_validate` is also exercised in the test suite.
"""

from __future__ import annotations

from pathlib import Path

from anvilate.spec import (
    DesignSpec,
    dump_spec_yaml,
    load_spec_yaml,
    validate_dimension_graph,
    validate_references,
)
from anvilate.standards import default_standards_resolver

SPEC_PATH = Path(__file__).resolve().parent / "nema23_bracket.spec.yaml"


def load_and_validate() -> DesignSpec:
    """Load the golden spec, validate its references and graph, and round-trip it."""
    spec = load_spec_yaml(SPEC_PATH.read_text())

    # Both validations raise on a problem; passing them is the gate to proceed.
    validate_references(spec, default_standards_resolver())
    validate_dimension_graph(spec)

    # The IR is the source of truth, so it must survive a YAML round-trip intact.
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    if reloaded != spec:
        raise AssertionError("spec did not round-trip through YAML unchanged")
    return spec


def main() -> None:
    spec = load_and_validate()
    print(f"loaded and validated: {spec.name}")
    print(f"  material:   {spec.material.ref}")
    print(f"  components: {', '.join(i.ref for i in spec.interfaces)}")
    print(f"  tiers:      {', '.join(t.value for t in spec.acceptance.tiers)}")


if __name__ == "__main__":
    main()
