"""Anvilate export layer: turn checked geometry into fabrication artifacts.

The first exporter is :mod:`anvilate.export.dxf`, which writes a 2D plate outline
(the "code-checked plate geometry" a structural-pack lug, gusset, or base plate
implies) to a DXF drawing. Export pulls in optional dependencies (``ezdxf`` for
DXF), installed via the ``export`` extra — the core stays dependency-light.
"""

from __future__ import annotations
