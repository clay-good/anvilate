"""Every character the PDF report can print, drawn without a font file.

The report is set in Courier, one of the fourteen fonts every PDF reader carries, so the
document embeds no font and needs no licence. Courier's WinAnsi encoding covers most of what
the package writes. For everything else there are two sources: Courier and Symbol themselves
hold more glyphs than WinAnsi can reach, and the rest are drawn as vector glyphs in a Type 3
font this module describes.

Each character outside WinAnsi becomes one Type 3 glyph whose drawing is one of:

* **a single glyph** from Courier or Symbol, placed in a Courier-width cell. A Symbol glyph
  is centred, and narrowed when it is wider than the cell;
* **a composition** read from the character's Unicode decomposition. That covers a base
  letter with an accent, a superscript or subscript, a circled letter or a vulgar fraction;
* **a path**, for the GD&T symbols, brackets and relations that no standard font draws.

A character with none of these is drawn as an empty box. That is visible on the page and
never passes as a blank space. The PDF's ToUnicode map still names the real character, so
text extracted from the page is exact either way.

Glyph space is 1000 units to the em, and every cell is 600 wide, which is Courier's advance.
Only combining marks and U+FEFF have zero width.
"""

from __future__ import annotations

import unicodedata

__all__ = ["CELL", "COURIER_EXTRA", "SYMBOL_GLYPHS", "SYMBOL_ORDER", "drawing", "width"]

#: The width of every cell in glyph units: Courier's advance.
CELL = 600

# Courier glyphs outside WinAnsi, reached through a Differences encoding on the inner Courier
# resource at codes 1 upward. Every name is in the Courier core metrics.
COURIER_EXTRA = (
    "cacute",
    "Idotaccent",
    "partialdiff",
    "minus",
    "radical",
    "notequal",
    "lessequal",
    "greaterequal",
    "dotaccent",
    "caron",
    "ring",
    "breve",
    "fraction",
)

# Characters Courier draws directly, by glyph name, beyond its WinAnsi encoding.
_COURIER_DIRECT = {
    "ć": "cacute",
    "İ": "Idotaccent",
    "∂": "partialdiff",
    "−": "minus",
    "√": "radical",
    "≠": "notequal",
    "≤": "lessequal",
    "≥": "greaterequal",
}

# Symbol glyphs by name, with each one's advance width from the Adobe core metrics. The
# widths centre the glyph in a cell. tests/test_report_pdf.py holds every name and width
# against pdfminer's copy of those metrics.
SYMBOL_GLYPHS: dict[str, int] = {
    "Gamma": 603,
    "Pi": 768,
    "Sigma": 592,
    "Phi": 763,
    "Omega": 768,
    "alpha": 631,
    "beta": 549,
    "gamma": 411,
    "delta": 494,
    "epsilon": 439,
    "zeta": 494,
    "eta": 603,
    "theta": 521,
    "kappa": 549,
    "lambda": 549,
    "mu": 576,
    "nu": 521,
    "xi": 493,
    "pi": 549,
    "rho": 549,
    "sigma": 603,
    "tau": 439,
    "phi": 521,
    "psi": 686,
    "omega": 686,
    "omega1": 713,
    "minute": 247,
    "second": 411,
    "arrowleft": 987,
    "arrowright": 987,
    "arrowboth": 1042,
    "gradient": 713,
    "element": 713,
    "product": 823,
    "proportional": 713,
    "infinity": 713,
    "angle": 768,
    "integral": 274,
    "approxequal": 549,
    "perpendicular": 658,
    "dotmath": 250,
    "less": 549,
    "greater": 549,
    "similar": 549,
    "plusminus": 549,
    "angleleft": 329,
    "angleright": 329,
}

# The character each Symbol glyph draws. Two Greek letters are keyed by the Greek code point
# the text uses, although Adobe's metrics file them under the ohm and micro signs. Delta is
# not here: poppler's stand-in for Symbol drew nothing for it, so it is drawn as a path.
_SYMBOL_DIRECT = {
    "Γ": "Gamma",
    "Π": "Pi",
    "Σ": "Sigma",
    "Φ": "Phi",
    "Ω": "Omega",
    "\u2126": "Omega",  # the ohm sign, which Adobe files the glyph under
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "ζ": "zeta",
    "η": "eta",
    "θ": "theta",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "ν": "nu",
    "ξ": "xi",
    "π": "pi",
    "ρ": "rho",
    "σ": "sigma",
    "τ": "tau",
    "φ": "phi",
    "ψ": "psi",
    "ω": "omega",
    "ϖ": "omega1",
    "′": "minute",
    "″": "second",
    "←": "arrowleft",
    "→": "arrowright",
    "↔": "arrowboth",
    "∇": "gradient",
    "∈": "element",
    "∏": "product",
    "∝": "proportional",
    "∞": "infinity",
    "∠": "angle",
    "∫": "integral",
    "≈": "approxequal",
    "⊥": "perpendicular",
    "⋅": "dotmath",
    "⟨": "angleleft",
    "⟩": "angleright",
    "〈": "angleleft",
    "〉": "angleright",
}

#: Symbol glyph names in code order: the inner Symbol resource maps code n + 1 to entry n.
SYMBOL_ORDER = tuple(sorted(SYMBOL_GLYPHS))

# The Courier accent glyph for each combining mark a decomposition can end in.
_ACCENT = {
    "\u0300": "grave",
    "\u0301": "acute",
    "\u0302": "circumflex",
    "\u0303": "tilde",
    "\u0304": "macron",
    "\u0306": "breve",
    "\u0307": "dotaccent",
    "\u0308": "dieresis",
    "\u030a": "ring",
    "\u030c": "caron",
}

_CAP_RAISE = 138  # Courier's cap height (572) less its x-height (434)


def _hex(data: bytes) -> str:
    return "<" + data.hex().upper() + ">"


def _courier_code(name: str) -> bytes:
    """The byte the inner Courier resource draws ``name`` with."""
    if name in COURIER_EXTRA:
        return bytes([COURIER_EXTRA.index(name) + 1])
    winansi = {
        "grave": b"`",
        "acute": b"\xb4",
        "circumflex": b"\x88",
        "tilde": b"\x98",
        "macron": b"\xaf",
        "dieresis": b"\xa8",
    }
    return winansi[name]


def _courier(text: bytes, *, size: int = 1000, x: float = 0, y: float = 0, font: str = "C") -> str:
    return f"BT /{font} {size} Tf {x:g} {y:g} Td {_hex(text)} Tj ET"


def _symbol(name: str, *, size: int = 1000, x: float | None = None, y: float = 0) -> str:
    width = SYMBOL_GLYPHS[name] * size / 1000
    scale = min(1.0, (CELL - 40) / width)
    left = (CELL - width * scale) / 2 if x is None else x
    code = bytes([SYMBOL_ORDER.index(name) + 1])
    return f"BT /S {size} Tf {scale * 100:g} Tz {left:g} {y:g} Td {_hex(code)} Tj ET"


def _stroke(path: str, *, width: int = 50) -> str:
    return f"{width} w 1 J 1 j {path} S"


def _circle(cx: float, cy: float, r: float) -> str:
    k = 0.5523 * r
    return (
        f"{cx + r:g} {cy:g} m "
        f"{cx + r:g} {cy + k:g} {cx + k:g} {cy + r:g} {cx:g} {cy + r:g} c "
        f"{cx - k:g} {cy + r:g} {cx - r:g} {cy + k:g} {cx - r:g} {cy:g} c "
        f"{cx - r:g} {cy - k:g} {cx - k:g} {cy - r:g} {cx:g} {cy - r:g} c "
        f"{cx + k:g} {cy - r:g} {cx + r:g} {cy - k:g} {cx + r:g} {cy:g} c h"
    )


def _base(char: str, *, size: int = 1000, x: float | None = None, y: float = 0) -> str | None:
    """``char`` drawn from Courier or Symbol, or ``None`` if neither holds it."""
    if char.isascii() and char.isprintable():
        left = (CELL - CELL * size / 1000) / 2 if x is None else x
        return _courier(char.encode("ascii"), size=size, x=left, y=y)
    if char in _COURIER_DIRECT:
        left = (CELL - CELL * size / 1000) / 2 if x is None else x
        return _courier(_courier_code(_COURIER_DIRECT[char]), size=size, x=left, y=y)
    if char in _SYMBOL_DIRECT:
        return _symbol(_SYMBOL_DIRECT[char], size=size, x=x, y=y)
    return None


_BOX = _stroke("80 0 m 520 0 l 520 600 l 80 600 l h", width=40)

# The characters no standard font draws, as paths or as compositions of glyphs that exist.
_DRAWN = {
    "\u0394": _stroke("80 0 m 520 0 l 300 600 l h"),  # Greek capital delta
    "\u2206": _stroke("80 0 m 520 0 l 300 600 l h"),  # increment
    "\u2113": _stroke(  # script small l: up, over the loop, down, and a hook to the right
        "150 80 m 300 250 420 520 380 620 c 350 700 260 640 250 520 c "
        "240 380 260 150 300 60 c 330 0 400 10 450 70 c"
    ),
    "\u2225": _stroke("220 -100 m 220 680 l 380 -100 m 380 680 l"),  # parallel
    "\u2300": _stroke(_circle(300, 280, 200) + " 90 30 m 510 530 l", width=45),  # diameter
    "\u2308": _stroke("400 720 m 220 720 l 220 -150 l"),  # left ceiling
    "\u2309": _stroke("200 720 m 380 720 l 380 -150 l"),  # right ceiling
    "\u230a": _stroke("220 720 m 220 -150 l 400 -150 l"),  # left floor
    "\u230b": _stroke("380 720 m 380 -150 l 200 -150 l"),  # right floor
    "\u2312": _stroke("60 150 m 150 420 450 420 540 150 c"),  # arc
    "\u2313": _stroke("60 150 m 150 420 450 420 540 150 c h"),  # segment
    "\u2316": _stroke(_circle(300, 280, 170) + " 300 20 m 300 540 l 40 280 m 560 280 l"),
    "\u232d": _stroke(_circle(300, 280, 150) + " 305 -12 m 555 422 l 45 138 m 295 572 l"),
    "\u232f": _stroke("150 400 m 450 400 l 40 280 m 560 280 l 150 160 m 450 160 l"),
    "\u2330": _stroke(
        "60 100 m 380 100 l 220 460 m 540 460 l 60 100 m 220 460 l 380 100 m 540 460 l"
    ),
    "\u25b1": _stroke("40 60 m 420 60 l 560 480 l 180 480 l h"),  # white parallelogram
    "\u25cb": _stroke(_circle(300, 280, 250)),  # white circle
    "\u25ce": _stroke(_circle(300, 280, 250) + " " + _circle(300, 280, 110)),  # bullseye
    "\u2197": f"q 0.7071 0.7071 -0.7071 0.7071 300 -140 cm {_symbol('arrowright', x=-100)} Q",
    "\u2213": f"q 1 0 0 -1 0 520 cm {_symbol('plusminus')} Q",  # minus-or-plus
    "\u226a": _symbol("less", x=-40) + " " + _symbol("less", x=180),
    "\u226b": _symbol("greater", x=-40) + " " + _symbol("greater", x=180),
    "\u2272": _symbol("less", y=160) + " " + _symbol("similar", size=700, y=-160),
    "\u2273": _symbol("greater", y=160) + " " + _symbol("similar", size=700, y=-160),
    "\u2277": _symbol("greater", size=650, y=330) + " " + _symbol("less", size=650, y=-120),
    "\u210f": _courier(b"h") + " " + _stroke("100 520 m 420 600 l", width=45),  # h-bar
    "\ufffd": _BOX,
}


def _composed(char: str) -> str | None:
    """A drawing read from ``char``'s Unicode decomposition, or ``None``."""
    decomposition = unicodedata.decomposition(char)
    if not decomposition:
        return None
    parts = decomposition.split()
    # A compatibility tag (super, sub, circle, font, fraction), read without its brackets.
    tag = parts[0].strip("<>") if parts[0].startswith("<") else None
    points = [chr(int(p, 16)) for p in (parts[1:] if tag else parts)]
    if tag is None and len(points) == 2 and points[1] in _ACCENT:
        base = _base(points[0])
        if base is None:
            return None
        raise_by = _CAP_RAISE if points[0].isupper() else 0
        accent = _courier(_courier_code(_ACCENT[points[1]]), y=raise_by)
        return f"{base} {accent}"
    if tag in ("super", "sub") and len(points) == 1:
        return _base(points[0], size=620, y=330 if tag == "super" else -150)
    if tag == "circle" and len(points) == 1:
        letter = _base(points[0], size=560, y=120)
        return None if letter is None else f"{_stroke(_circle(300, 280, 285), width=40)} {letter}"
    if tag == "font" and len(points) == 1 and points[0].isascii():
        return _courier(points[0].encode("ascii"), font="O")
    if tag == "fraction" and len(points) == 3:
        top = _base(points[0], size=520, x=-20, y=300)
        bottom = _base(points[2], size=520, x=300, y=-40)
        if top is None or bottom is None:
            return None
        return f"{top} {_courier(_courier_code('fraction'))} {bottom}"
    return None


def width(char: str) -> int:
    """The advance of ``char`` in glyph units: a cell, or nothing for a combining mark."""
    if char == "\ufeff" or unicodedata.combining(char):
        return 0
    return CELL


def drawing(char: str) -> tuple[str, bool]:
    """The glyph procedure body for ``char``, and whether it is a real drawing.

    ``False`` means the box: the character has no recipe here. The body assumes the
    Type 3 font's resources name Courier ``/C``, Courier-Oblique ``/O`` and Symbol ``/S``.
    """
    if char == "\ufeff":
        return "", True
    if unicodedata.combining(char) and char in _ACCENT:
        return f"q 1 0 0 1 -{CELL} 0 cm {_courier(_courier_code(_ACCENT[char]))} Q", True
    for found in (_DRAWN.get(char), _base(char), _composed(char)):
        if found is not None:
            return found, True
    return _BOX, False
