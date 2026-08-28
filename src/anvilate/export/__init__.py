"""Anvilate export layer: turn checked geometry into fabrication artifacts.

The first exporter is :mod:`anvilate.export.dxf`, which writes a 2D plate outline
(the "code-checked plate geometry" a structural-pack lug, gusset, or base plate
implies) to a DXF drawing. Export pulls in optional dependencies (``ezdxf`` for
DXF), installed via the ``export`` extra — the core stays dependency-light.

Every entry point that emits an artifact takes an
:class:`~anvilate.export.gate.ExportAuthorization`: export is gated on the part's acceptance
checks passing, an unvalidated part leaves only under an explicit override, and either way
the file carries the screening watermark in its own metadata. :mod:`anvilate.export.gate`
holds that decision, and it imports nothing optional, so it is available without the extra.
"""

from __future__ import annotations
