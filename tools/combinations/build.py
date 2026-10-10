"""Draw the picture of every worked combination for the combinations guide.

    python tools/combinations/build.py

Each picture in `docs/combinations/` is the drawing `anvilate combine --picture` writes for
the example of the same name in `examples/combinations/`. `tests/test_combination_docs.py`
holds the guide to the examples: one picture and one section each, and no others.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples" / "combinations"
PICTURES = REPO / "docs" / "combinations"


def pictures() -> dict[str, bytes]:
    """The drawing of every worked combination, by example name."""
    import yaml

    from anvilate.combination import build_combination, parse_combination, render_combination

    drawn = {}
    for path in sorted(EXAMPLES.glob("*.combination.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        image, _width, _height = render_combination(
            build_combination(parse_combination(document)), width_px=900
        )
        drawn[path.name.removesuffix(".combination.yaml")] = image
    return drawn


def main() -> int:
    PICTURES.mkdir(exist_ok=True)
    for name, image in pictures().items():
        (PICTURES / f"{name}.png").write_bytes(image)
    return 0


if __name__ == "__main__":
    sys.exit(main())
