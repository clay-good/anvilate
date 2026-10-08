"""The bundled datasets as versioned things: which tables, which version, which bytes.

Every table under ``standards/data`` opens with a ``dataset`` header: its name, its version,
its licence and the date its values were retrieved. That header is the dataset's contract
with anyone who reads the file, Anvilate or not (docs/datasets.md), and this module is how
the evidence names it. A bundle that records each table's version and the digest of its
bytes makes a data change a visible provenance change, which is what the standards-data
requirement "Anvilate SHALL consume the dataset by pinned version" asks of a dataset that
lives in this repository rather than beside it.
"""

from __future__ import annotations

import hashlib
from functools import cache

from pydantic import ConfigDict

from .._models import Named, StatableModel, parse_yaml

__all__ = ["DatasetVersion", "bundled_datasets"]


class DatasetVersion(StatableModel):
    """One bundled table as the evidence pins it: name, version, file, digest and licence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    version: Named
    file: Named
    sha256: Named
    license: Named

    def __str__(self) -> str:
        return (
            f"{self.name} {self.version} ({self.file}, sha256 {self.sha256[:12]}, {self.license})"
        )


@cache
def bundled_datasets() -> tuple[DatasetVersion, ...]:
    """Every bundled table's pin, in file order. Read once: the files ship with the package."""
    from importlib.resources import files

    pins = []
    for entry in sorted(files("anvilate.standards").joinpath("data").iterdir(), key=str):
        if not entry.name.endswith(".yaml"):
            continue
        data = entry.read_bytes()
        header = parse_yaml(data.decode("utf-8"))["dataset"]
        pins.append(
            DatasetVersion(
                name=header["name"],
                version=str(header["version"]),
                file=entry.name,
                sha256=hashlib.sha256(data).hexdigest(),
                license=header["license"],
            )
        )
    return tuple(pins)
