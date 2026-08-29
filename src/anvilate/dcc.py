"""Digital Calibration Certificates: a measured value with the instrument behind it.

Anvilate's provenance chain has always ended at a table — "ASTM A36 specified minimum",
"ISO 286 H7". A Digital Calibration Certificate (DCC, the open PTB schema) lets it end
somewhere better for the values that were actually measured: at a calibrated instrument,
with the certificate's identifier, the laboratory that issued it, and the measurement
uncertainty the laboratory stated. A measured shaft diameter feeding an interference-fit
check stops being a number somebody typed.

Reading one is XML parsing. The part that matters is what happens to the values afterward,
and it is the same rule the requirements pass already enforces: **an offered value is a
draft, and a draft is not an input.** A DCC arrives as a set of
:class:`~anvilate.ingest.ExtractedValue` drafts and goes through the same per-value,
per-person confirmation. A calibration certificate is a better source than an RFQ table; it
is not a person deciding that this measurement is the one the design should use.

Three positions in the reading:

**A signature nobody checked is not a signature.** Verifying an XML digital signature needs
the issuer's certificate and a trust anchor, and a local, offline screening tool has
neither. So :class:`~anvilate.ingest.SignatureStatus` has no ``VERIFIED`` member: a
certificate is either unsigned or signed-and-unverified, the value is usable after
confirmation either way, and the provenance says which. The laboratory's own
``cryptElectronicSeal`` flag is carried as a separate *claim*, because a document asserting
that it is sealed is not evidence that it is.

**A unit we cannot map is not a unit we guess at.** D-SI writes units as escape sequences
(``\\milli\\metre``, ``\\kilo\\gram\\metre\\tothe{2}\\second\\tothe{-2}``) over a vocabulary
that the published schema leaves as an open string. Every token this module accepts is in a
declared table; anything else is recorded as a line it did not take, with the offending
token named. Silently resolving ``\\bar`` to something plausible is how a pressure lands in
a check three orders of magnitude out.

**A stated uncertainty is a distribution, not a footnote.** An expanded uncertainty *U* at
coverage factor *k* is a standard uncertainty of ``U/k``, which is exactly what
:class:`~anvilate.uncertainty.Symmetric` means by a half-width at a sigma level — so the
certificate's own number reaches the margin sampler as a typed input distribution rather
than being read once by a human and forgotten. A certificate that declares a non-Gaussian
distribution yields *no* distribution and says why: mapping a rectangular uncertainty onto a
Gaussian one because the shapes both have a width is the kind of quiet substitution this
library exists to refuse.

Anchored against the published schemas: PTB DCC v3.3.0 (``dcc.xsd``, LGPL, from
https://gitlab.com/ptb/dcc/xsd-dcc) over D-SI v2.2.1 (``SI_Format.xsd``). Standard library
only — the parsing is ``xml.etree``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from math import isclose, isfinite
from xml.etree import ElementTree as ET

from pydantic import BaseModel, ConfigDict, model_validator

from ._models import RevalidatedModel
from .ingest import (
    CertificateProvenance,
    ExtractedValue,
    SignatureStatus,
    SourceLocation,
    UnparsedLine,
)
from .uncertainty import InputDistribution, Normal, Symmetric
from .units import Quantity, UnitError

__all__ = [
    "DCC_NAMESPACE",
    "SI_NAMESPACE",
    "CalibratedValue",
    "CalibrationCertificate",
    "d_si_quantity",
    "parse_dcc",
]

DCC_NAMESPACE = "https://ptb.de/dcc"
SI_NAMESPACE = "https://ptb.de/si"
_DSIG_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"

_NS = {"dcc": DCC_NAMESPACE, "si": SI_NAMESPACE, "ds": _DSIG_NAMESPACE}

# The D-SI unit vocabulary this module accepts, token to Pint symbol. The published schema
# types a unit as an unrestricted string, so there is no enumeration to validate against —
# which makes an explicit table the only honest option. Everything here is an SI base unit,
# an SI derived unit, or one of the non-SI units accepted for use with the SI; anything
# outside it is refused by name rather than guessed at, and the table is the thing to extend
# when a real certificate needs more.
_D_SI_UNITS: dict[str, str] = {
    # SI base
    "metre": "m",
    "kilogram": "kg",
    "second": "s",
    "ampere": "A",
    "kelvin": "K",
    "mole": "mol",
    "candela": "cd",
    # gram carries the prefixes in D-SI; kilogram is spelled out as its own token
    "gram": "g",
    # SI derived
    "hertz": "Hz",
    "newton": "N",
    "pascal": "Pa",
    "joule": "J",
    "watt": "W",
    "coulomb": "C",
    "volt": "V",
    "farad": "F",
    "ohm": "ohm",
    "siemens": "S",
    "weber": "Wb",
    "tesla": "T",
    "henry": "H",
    "lumen": "lm",
    "lux": "lx",
    "becquerel": "Bq",
    "gray": "Gy",
    "sievert": "Sv",
    "katal": "kat",
    "radian": "rad",
    "steradian": "sr",
    "degreecelsius": "degC",
    # non-SI units accepted for use with the SI
    "minute": "min",
    "hour": "hour",
    "day": "day",
    "degree": "degree",
    "arcminute": "arcminute",
    "arcsecond": "arcsecond",
    "litre": "L",
    "tonne": "t",
    "electronvolt": "eV",
    "dalton": "Da",
    "astronomicalunit": "au",
}

# Decimal SI prefixes: token to (Pint symbol, power of ten). The power is what makes the
# concatenated symbol checkable — see `d_si_quantity`, where the prefixed spelling is only
# used once it has been proved to mean prefix x unit. The binary prefixes (kibi, mebi, ...)
# are deliberately absent: they belong to information quantities, not to measurements a
# check consumes, and admitting them would mean admitting the units they prefix.
_D_SI_PREFIXES: dict[str, tuple[str, int]] = {
    "deca": ("da", 1),
    "hecto": ("h", 2),
    "kilo": ("k", 3),
    "mega": ("M", 6),
    "giga": ("G", 9),
    "tera": ("T", 12),
    "peta": ("P", 15),
    "exa": ("E", 18),
    "zetta": ("Z", 21),
    "yotta": ("Y", 24),
    "deci": ("d", -1),
    "centi": ("c", -2),
    "milli": ("m", -3),
    "micro": ("u", -6),
    "nano": ("n", -9),
    "pico": ("p", -12),
    "femto": ("f", -15),
    "atto": ("a", -18),
    "zepto": ("z", -21),
    "yocto": ("y", -24),
}

# Units a prefix must not be attached to. Degrees Celsius is the one that matters: it is an
# offset unit, so "millidegreecelsius" is not a scaled temperature and a compound containing
# it is not a product at all. The rest are non-decimal or already-fixed magnitudes.
_UNPREFIXABLE = frozenset(
    {
        "degreecelsius",
        "kilogram",
        "minute",
        "hour",
        "day",
        "degree",
        "arcminute",
        "arcsecond",
        "astronomicalunit",
        "dalton",
    }
)

_TOTHE = re.compile(r"^tothe\{(?P<exponent>-?\d+)\}$")

# The uncertainty distributions this module will map. A certificate that names anything else
# is answered with no distribution and the name it gave, rather than with a Gaussian that
# happens to have the same width.
_GAUSSIAN_DISTRIBUTIONS = frozenset({"normal", "gaussian"})

# Where a value's line number comes from. ElementTree does not report source lines, so the
# raw text is scanned once for the quantity value elements in document order and zipped with
# the quantities as they are parsed. The scan must be anchored to the *D-SI* namespace
# prefix, not to any element named "value": a DCC's identification block carries
# `<dcc:value>` elements, and matching those put every measured value's line number in the
# administrative header, pointing a reader at a serial number instead of a measurement.
_SI_PREFIX = re.compile(r"""xmlns:([A-Za-z_][\w.-]*)\s*=\s*["']https://ptb\.de/si["']""")


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    stripped = element.text.strip()
    return stripped or None


def _content(parent: ET.Element | None) -> str | None:
    """A ``dcc:textType``'s text — the first ``dcc:content`` under it."""
    if parent is None:
        return None
    return _text(parent.find("dcc:content", _NS))


def _decimal(raw: str | None) -> float | None:
    """A D-SI decimal, or ``None`` when it is absent or not a usable number.

    ``si:decimalType`` admits the literal ``NaN``, which is a legitimate thing for a
    laboratory to write and an illegitimate thing to hand a check.
    """
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if isfinite(value) else None


def d_si_quantity(value: float, unit: str) -> Quantity:
    """A D-SI value and unit expression as a dimension-checked :class:`Quantity`.

    ``unit`` is the D-SI escape form — ``"\\milli\\metre"``,
    ``"\\kilo\\gram\\metre\\tothe{2}\\second\\tothe{-2}"``. Every token must be in this
    module's declared vocabulary; an unknown prefix or unit raises
    :class:`~anvilate.units.UnitError` naming the token, because the published schema types
    a unit as a free string and there is nothing to validate against but the table.

    **The prefixed spelling is proved, not assumed.** Gluing a prefix symbol onto a unit
    symbol produces a token Pint may already own as something else entirely: ``centi`` +
    ``t`` is ``ct``, which is a *carat* — still a mass, so ``\\centi\\tonne`` came back as
    0.0002 kg where the certificate said 10 kg and no downstream dimension check could
    notice. Eight of the table's 820 prefix-unit pairs collide that way (``kt`` knot, ``ft``
    foot, ``pt`` pint, ``at`` technical atmosphere, ``Tt`` tex, ``mcd`` microday …). So the
    quantity is *computed* from the bare unit and the prefix's power of ten, and the
    prefixed spelling is adopted only when it converts back to exactly that. A collision
    falls back to the bare unit with the magnitude scaled — right answer, plainer rendering.
    """
    if not unit.strip():
        raise UnitError("a D-SI unit expression is empty; a measured value must state its unit")
    if not unit.lstrip().startswith("\\"):
        raise UnitError(
            f"{unit!r} is not a D-SI unit expression; every token begins with a backslash "
            "(for example '\\\\milli\\\\metre')"
        )

    # One entry per factor: its bare Pint symbol, its prefixed spelling, the prefix's power
    # of ten, and the exponent. Kept apart so the two expressions can be built and compared.
    factors: list[list] = []
    pending: tuple[str, int] | None = None  # the prefix waiting for its unit
    pending_token: str | None = None
    named: list[str] = []
    for token in (t.strip() for t in unit.strip().split("\\")):
        if not token:
            continue
        exponent = _TOTHE.match(token)
        if exponent is not None:
            if not factors:
                raise UnitError(f"{unit!r} applies an exponent before naming a unit")
            power = int(exponent.group("exponent"))
            if power == 0:
                # A unit to the zeroth power is dimensionless. Legal arithmetic, and a
                # measured quantity that states it has said nothing about what it measured.
                raise UnitError(
                    f"{unit!r} raises a unit to the zeroth power, which leaves no unit at "
                    "all; a measured value must state what it measures"
                )
            factors[-1][3] = power
            continue
        if token in _D_SI_PREFIXES:
            if pending is not None:
                raise UnitError(f"{unit!r} stacks two prefixes: {pending_token!r} then {token!r}")
            pending, pending_token = _D_SI_PREFIXES[token], token
            continue
        if token not in _D_SI_UNITS:
            raise UnitError(
                f"unknown D-SI token {token!r} in {unit!r}; this module accepts "
                f"{len(_D_SI_UNITS)} units and {len(_D_SI_PREFIXES)} prefixes, and refuses "
                "the rest rather than guessing at what was meant"
            )
        if pending is not None and token in _UNPREFIXABLE:
            raise UnitError(
                f"{unit!r} prefixes {token!r}, which does not take one — "
                "an offset or fixed-magnitude unit is not scaled by a prefix"
            )
        symbol = _D_SI_UNITS[token]
        prefix_symbol, prefix_power = pending if pending is not None else ("", 0)
        factors.append([symbol, f"{prefix_symbol}{symbol}", prefix_power, 1])
        named.append(token)
        pending, pending_token = None, None

    if pending is not None:
        raise UnitError(f"{unit!r} ends with the prefix {pending_token!r} and no unit after it")
    if not factors:
        raise UnitError(f"{unit!r} names no unit")
    # Degrees Celsius is an offset unit: it is a temperature on its own and nothing at all
    # inside a product, where Pint would have to pick an origin it has not been given.
    if "degreecelsius" in named and len(factors) > 1:
        raise UnitError(
            f"{unit!r} multiplies degrees Celsius by another unit; an offset temperature has "
            "no meaning in a product — the certificate should state kelvin"
        )

    bare = _expression(factors, prefixed=False)
    prefixed = _expression(factors, prefixed=True)
    scale = 1.0
    for _symbol, _spelled, power, exponent in factors:
        scale *= 10.0 ** (power * exponent)

    try:
        plain = Quantity(magnitude=value * scale, unit=bare).to(bare)
    except Exception as exc:  # pragma: no cover - the table is what keeps this unreachable
        raise UnitError(f"{unit!r} maps to {bare!r}, which is not a unit: {exc}") from exc
    if prefixed == bare:
        return plain
    # The proof: the prefixed spelling has to be the same physical quantity. A collision
    # either changes dimension (which raises here) or changes magnitude (which fails the
    # comparison); both fall through to the bare form, which was computed from the powers
    # of ten and cannot collide with anything.
    #
    # The proof runs on a magnitude of ONE, never on the measured value. Proving it on the
    # value meant a reading of exactly zero compared 0.0 against 0.0 and adopted the
    # colliding spelling unchallenged: `\centi\tonne` of 0.0 came back as `0 ct`, a carat,
    # and the certificate's uncertainty was then scaled into a unit five million times too
    # small — while the neighbouring non-zero reading on the same certificate was right.
    if not _spelling_holds(prefixed, bare, scale):
        return plain
    return Quantity(magnitude=value, unit=prefixed).to(prefixed)


def _spelling_holds(prefixed: str, bare: str, scale: float) -> bool:
    """Whether ``prefixed`` really means ``scale`` times ``bare``.

    Independent of any measured value, so the answer is a property of the unit expression
    rather than of the reading that happened to arrive.
    """
    try:
        converted = Quantity(magnitude=1.0, unit=prefixed).to(bare)
    except Exception:
        return False
    return isclose(converted.magnitude, scale, rel_tol=1e-9)


def _expression(factors: list[list], *, prefixed: bool) -> str:
    """The factor list as a Pint expression, in bare or prefixed spelling.

    An exponent of 1 is written without parentheses so an ordinary single unit renders as
    ``"mm"`` rather than ``"(mm) ** 1"`` — and so an offset unit like ``degC``, which Pint
    will not raise to a power, stays writable.
    """
    parts = []
    for symbol, spelled, _power, exponent in factors:
        token = spelled if prefixed else symbol
        parts.append(token if exponent == 1 else f"({token}) ** {exponent}")
    return " * ".join(parts)


def _distribution(
    real: ET.Element, nominal: float, scale: float
) -> tuple[InputDistribution | None, str | None]:
    """The certificate's stated uncertainty as an input distribution, or why there is none.

    Returns ``(distribution, reason)`` with exactly one of them set. ``nominal`` and the
    uncertainties are expressed in the *converted* quantity's unit — ``scale`` is the factor
    from the certificate's own unit to it — so the distribution and the quantity are always
    two views of the same number. Without that they could differ by the whole prefix: a
    shaft stated in micrometres gave a quantity of 25000.4 µm and a distribution nobody
    could tell was not in millimetres.

    An expanded uncertainty *U* at coverage factor *k* is a standard uncertainty of
    ``U/k``, which is what
    :class:`~anvilate.uncertainty.Symmetric` means by a half-width at a sigma level, so the
    mapping is the definition rather than an approximation. The deprecated ``si:expandedUnc``
    and ``si:coverageInterval`` spellings are read as well, because certificates written
    against D-SI 1.x are in the world.
    """
    univariate = real.find("si:measurementUncertaintyUnivariate", _NS)

    expanded = None if univariate is None else univariate.find("si:expandedMU", _NS)
    if expanded is not None:
        return _expanded(
            nominal,
            _scaled(_decimal(_text(expanded.find("si:valueExpandedMU", _NS))), scale),
            _decimal(_text(expanded.find("si:coverageFactor", _NS))),
            _text(expanded.find("si:distribution", _NS)),
        )

    standard = None if univariate is None else univariate.find("si:standardMU", _NS)
    if standard is None and univariate is not None:
        # A coverage-interval statement also carries the standard uncertainty, which is the
        # part a distribution is built from; the interval itself is a reporting convention.
        standard = univariate.find("si:coverageIntervalMU", _NS)
    if standard is not None:
        return _standard(
            nominal,
            _scaled(_decimal(_text(standard.find("si:valueStandardMU", _NS))), scale),
            _text(standard.find("si:distribution", _NS)),
        )

    deprecated = real.find("si:expandedUnc", _NS)
    if deprecated is not None:
        return _expanded(
            nominal,
            _scaled(_decimal(_text(deprecated.find("si:uncertainty", _NS))), scale),
            _decimal(_text(deprecated.find("si:coverageFactor", _NS))),
            _text(deprecated.find("si:distribution", _NS)),
        )

    interval = real.find("si:coverageInterval", _NS)
    if interval is not None:
        return _standard(
            nominal,
            _scaled(_decimal(_text(interval.find("si:standardUnc", _NS))), scale),
            _text(interval.find("si:distribution", _NS)),
        )

    return None, "the certificate states no measurement uncertainty for this value"


def _scaled(value: float | None, scale: float) -> float | None:
    """An uncertainty in the certificate's unit, expressed in the converted one."""
    return None if value is None else value * scale


def _non_gaussian(declared: str | None) -> str | None:
    """The refusal reason for a declared distribution this module will not map, or ``None``."""
    if declared is None or declared.strip().lower() in _GAUSSIAN_DISTRIBUTIONS:
        return None
    return (
        f"the certificate declares a {declared.strip()!r} distribution; only a Gaussian one "
        "is mapped, because a rectangular uncertainty and a normal one of the same width are "
        "different statements about the measurement"
    )


def _expanded(
    nominal: float, uncertainty: float | None, coverage_factor: float | None, declared: str | None
) -> tuple[InputDistribution | None, str | None]:
    refusal = _non_gaussian(declared)
    if refusal is not None:
        return None, refusal
    if uncertainty is None:
        return None, "the certificate's expanded uncertainty is not a usable number"
    if coverage_factor is None or coverage_factor <= 0:
        # Without k the expanded uncertainty is a width with no stated confidence, and the
        # conventional k=2 is a convention, not this certificate's statement. Assuming it
        # would silently halve or double the standard uncertainty a check then samples.
        return None, (
            "the certificate states an expanded uncertainty with no usable coverage factor, "
            "so the standard uncertainty behind it is unknown"
        )
    return (
        Symmetric(
            nominal=nominal,
            half_width=uncertainty,
            distribution="normal",
            sigma_level=coverage_factor,
        ),
        None,
    )


def _standard(
    nominal: float, uncertainty: float | None, declared: str | None
) -> tuple[InputDistribution | None, str | None]:
    refusal = _non_gaussian(declared)
    if refusal is not None:
        return None, refusal
    if uncertainty is None:
        return None, "the certificate's standard uncertainty is not a usable number"
    return Normal(mean=nominal, std=uncertainty), None


class CalibratedValue(RevalidatedModel):
    """One measured quantity a certificate offers, with its uncertainty and its origin."""

    model_config = ConfigDict(frozen=True)

    label: str
    quantity: Quantity
    source: SourceLocation
    certificate: CertificateProvenance
    # The certificate's stated uncertainty as a typed input distribution, ready for the
    # margin sampler. ``None`` when the certificate stated none or stated one this module
    # will not map, in which case ``uncertainty_note`` says which. Its numbers are in
    # :attr:`quantity`'s unit — always, by construction — which is the whole reason
    # :meth:`distribution_in` exists rather than callers reading the floats raw.
    distribution: InputDistribution | None = None
    uncertainty_note: str | None = None
    # The unit the distribution's numbers are in, stored rather than derived. Deriving it
    # from `quantity.unit` made it true by definition and therefore unable to catch
    # anything: a copy that changed the quantity's unit from mm to m kept the same
    # magnitude, so the centre still matched and the thousandfold drift was invisible to a
    # validator that could only compare numbers.
    distribution_unit: str | None = None

    @model_validator(mode="after")
    def _the_distribution_is_the_same_number(self) -> CalibratedValue:
        """The distribution's centre must be the quantity, in the quantity's unit.

        A distribution is bare floats and a quantity is unit-checked, so nothing else in the
        library can catch them drifting apart. They did: the uncertainty was built from the
        certificate's raw magnitude while the quantity had been converted, so a shaft stated
        in micrometres carried a 25000.4-centred distribution against a millimetre limit —
        wrong by a factor of a thousand, dimensionally invisible, and with no unit recorded
        anywhere for a consumer to notice.
        """
        if self.distribution is None:
            return self
        centre = self.distribution.mean
        # No absolute floor. `abs_tol=1e-12` disarmed the relative tolerance for small
        # magnitudes exactly the way this repository's known `pytest.approx` trap does: a
        # 1e-13 m reading accepted a distribution centred anywhere up to 1.1e-12 — a
        # tenfold error — and accepted one centred on zero. Zero is handled as its own case
        # because a relative tolerance against zero admits nothing else.
        if self.distribution_unit is None:
            raise ValueError(
                f"the uncertainty distribution for {self.label!r} does not say what unit its "
                "numbers are in; a distribution is bare floats, so the unit has to be stated "
                "or it is not recoverable"
            )
        if self.distribution_unit != self.quantity.unit:
            raise ValueError(
                f"the uncertainty distribution for {self.label!r} is in "
                f"{self.distribution_unit!r} but the measured value is in "
                f"{self.quantity.unit!r}; a distribution in a different unit from its own "
                "quantity is a factor nothing downstream can see"
            )
        magnitude = self.quantity.magnitude
        exact_zero = magnitude == 0.0 and centre == 0.0
        if not exact_zero and not isclose(centre, magnitude, rel_tol=1e-9):
            raise ValueError(
                f"the uncertainty distribution for {self.label!r} is centred on {centre} "
                f"but the measured value is {self.quantity}; a distribution in a different "
                "unit from its own quantity is a factor nothing downstream can see"
            )
        return self

    def distribution_in(self, unit: str) -> InputDistribution | None:
        """The stated uncertainty as a distribution in ``unit``, or ``None`` if there is none.

        The margin sampler works on bare floats, so the unit has to be settled *before* the
        response function sees them. Ask for the unit the check works in and the conversion
        happens here, where the quantity is still a :class:`~anvilate.units.Quantity`,
        instead of in a caller that has only numbers left to reason about.
        """
        if self.distribution is None:
            return None
        # The centre converts with the full affine transform and the width with the scale
        # alone, taken as the difference between two converted points. Dividing the
        # converted value by the original would divide by zero on a certificate reporting
        # exactly zero, and multiplying a width by an offset unit's conversion would add
        # 273.15 to an uncertainty of 0.2 K.
        centre = self.quantity.to(unit).magnitude
        own = self.quantity.unit
        factor = (
            Quantity(magnitude=2.0, unit=own).to(unit).magnitude
            - Quantity(magnitude=1.0, unit=own).to(unit).magnitude
        )
        if isinstance(self.distribution, Symmetric):
            return self.distribution.model_copy(
                update={
                    "nominal": centre,
                    "half_width": self.distribution.half_width * factor,
                }
            )
        return Normal(mean=centre, std=self.distribution.std * factor)

    def as_extracted(self, field: str, *, load_bearing: bool = True) -> ExtractedValue:
        """This measurement as a draft input for the standard per-value confirmation flow.

        A draft, not an input — the same rule a requirements sheet gets. A calibration
        certificate is a better source than an RFQ table; it is still not a person deciding
        that this measurement is the one the design should use.
        """
        return ExtractedValue(
            field=field,
            quantity=self.quantity,
            source=self.source,
            load_bearing=load_bearing,
            certificate=self.certificate,
        )

    def __str__(self) -> str:
        spread = "no distribution" if self.distribution is None else "distribution available"
        return f"{self.label} = {self.quantity} [{spread}] {self.certificate}"


class CalibrationCertificate(BaseModel):
    """A parsed DCC: what it says about itself, and the values it offers."""

    model_config = ConfigDict(frozen=True)

    provenance: CertificateProvenance
    values: tuple[CalibratedValue, ...] = ()
    # Quantities the pass did not take, and why — a unit outside the accepted vocabulary, a
    # value that is not a number. Visible and countable, never silently dropped, so a reader
    # can see what the certificate offered that Anvilate declined.
    unparsed: tuple[UnparsedLine, ...] = ()

    def labelled(self, label: str) -> CalibratedValue:
        """The one offered value with this label, or a refusal naming what is on offer.

        Ambiguity is refused rather than resolved. ``dcc:quantity/dcc:name`` is optional, so
        a result reporting several readings gives them all the same fallback label — and
        returning the first would make the others unreachable while looking like a lookup
        that worked. Reach for :attr:`values` by position when a certificate does that.
        """
        matches = [value for value in self.values if value.label == label]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise KeyError(
                f"no measured value labelled {label!r} on certificate "
                f"{self.provenance.identifier}; it offers {sorted(v.label for v in self.values)}"
            )
        raise KeyError(
            f"certificate {self.provenance.identifier} carries {len(matches)} values "
            f"labelled {label!r} ({', '.join(str(m.quantity) for m in matches)}); picking one "
            "would make the rest unreachable — index into `values` instead"
        )

    def summary(self) -> str:
        """One line: the certificate, what it offered, and the signature situation."""
        with_spread = sum(1 for v in self.values if v.distribution is not None)
        return (
            f"{len(self.values)} measured value(s) from certificate "
            f"{self.provenance.identifier} ({self.provenance.laboratory}), "
            f"{with_spread} with a usable uncertainty, {len(self.unparsed)} not taken — "
            f"{self.provenance.signature_line()}"
        )


# The element path a measured quantity sits on, innermost last. `dcc:list` may nest, so the
# `data` end of the path is matched with the list levels skipped. Anchoring the line scan to
# this exact path is what keeps it honest: `si:value` also appears under `influenceConditions`
# and `itemQuantities`, both of which a plain document-order count would fold into the
# sequence and shift every measured value's reported line onto somebody else's number.
_QUANTITY_PATH = (
    f"{{{DCC_NAMESPACE}}}result",
    f"{{{DCC_NAMESPACE}}}data",
    f"{{{DCC_NAMESPACE}}}quantity",
)


def _on_the_quantity_path(stack: list[str]) -> bool:
    """Whether the open-element stack is exactly a measured quantity's own path."""
    if len(stack) < 4 or stack[-1] != _QUANTITY_PATH[2]:
        return False
    depth = len(stack) - 2
    while depth >= 0 and stack[depth] == f"{{{DCC_NAMESPACE}}}list":
        depth -= 1
    return (
        depth >= 1 and stack[depth] == _QUANTITY_PATH[1] and stack[depth - 1] == _QUANTITY_PATH[0]
    )


def _xml_lines(text: str) -> list[str]:
    """``text`` split the way XML counts lines, with the line ends kept.

    ``str.splitlines`` also breaks on U+0085, U+2028 and U+2029, which XML 1.0 treats as
    ordinary characters. Any of them anywhere in the document — a NEL inside an item name,
    say — pushed every later quantity's reported line number out by one, and the shaft
    diameter ended up citing the ambient temperature's value: exactly the failure this scan
    was rewritten to prevent, coming back through the splitter instead of the element match.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    return [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])


def _quantity_lines(text: str) -> list[tuple[int, int | None]]:
    """For each measured quantity in document order, ``(quantity line, value line)``.

    ElementTree hands back no source lines, so the document is fed to a pull parser one line
    at a time and the open-element stack is tracked: a start event that arrives while a line
    is being consumed started on that line. The stack is what makes it exact — the path is
    checked rather than the element name, so a `si:value` in an influence condition or an
    item quantity cannot displace a measurement's line, and a certificate that binds D-SI to
    a default namespace is read the same as one that uses a prefix.

    The walk order here is the walk order of :func:`_quantities`, so the nth pair belongs to
    the nth quantity — the same document, the same order, and no counting by hand.
    """
    parser = ET.XMLPullParser(events=("start", "end"))
    stack: list[str] = []
    found: list[tuple[int, int | None]] = []
    value_tag = f"{{{SI_NAMESPACE}}}value"
    real_tag = f"{{{SI_NAMESPACE}}}real"
    for number, line in enumerate(_xml_lines(text), start=1):
        parser.feed(line)
        for event, element in parser.read_events():
            if event == "start":
                stack.append(element.tag)
                if _on_the_quantity_path(stack):
                    found.append((number, None))
                elif (
                    element.tag == value_tag
                    and len(stack) >= 2
                    and stack[-2] == real_tag
                    and found
                    and found[-1][1] is None
                ):
                    found[-1] = (found[-1][0], number)
            elif stack:
                stack.pop()
    return found


def _quantities(node: ET.Element) -> Iterator[ET.Element]:
    """Every ``dcc:quantity`` under a node, in document order, lists included."""
    for child in node:
        if child.tag == f"{{{DCC_NAMESPACE}}}quantity":
            yield child
        elif child.tag == f"{{{DCC_NAMESPACE}}}list":
            yield from _quantities(child)


def _provenance(root: ET.Element) -> CertificateProvenance:
    administrative = root.find("dcc:administrativeData", _NS)
    if administrative is None:
        raise ValueError("this is not a usable DCC: it carries no administrativeData block")
    core = administrative.find("dcc:coreData", _NS)
    laboratory = administrative.find("dcc:calibrationLaboratory", _NS)
    if core is None:
        raise ValueError("this is not a usable DCC: its administrativeData carries no coreData")

    identifier = _text(None if core is None else core.find("dcc:uniqueIdentifier", _NS))
    lab_name = _content(
        None if laboratory is None else laboratory.find("dcc:contact/dcc:name", _NS)
    )
    signed = root.find("ds:Signature", _NS) is not None
    # The schema lets the laboratory claim a seal and lets each responsible person claim one
    # separately. Reading only the laboratory's copy under-claims, which is the safe
    # direction but still a claim the certificate made and the provenance did not carry.
    claim_paths = (
        "dcc:calibrationLaboratory/dcc:cryptElectronicSeal",
        "dcc:calibrationLaboratory/dcc:cryptElectronicSignature",
        "dcc:respPersons/dcc:respPerson/dcc:cryptElectronicSeal",
        "dcc:respPersons/dcc:respPerson/dcc:cryptElectronicSignature",
    )
    claimed = any(
        (_text(found) or "").strip().lower() in {"true", "1"}
        for path in claim_paths
        for found in administrative.findall(path, _NS)
    )
    return CertificateProvenance(
        identifier=identifier or "",
        laboratory=lab_name or "",
        signature_status=(SignatureStatus.PRESENT_UNVERIFIED if signed else SignatureStatus.ABSENT),
        claims_electronic_seal=claimed,
        country=_text(core.find("dcc:countryCodeISO3166_1", _NS)),
        issue_date=_text(core.find("dcc:issueDate", _NS)),
        performance_end_date=_text(core.find("dcc:endPerformanceDate", _NS)),
        schema_version=root.get("schemaVersion"),
    )


def parse_dcc(text: str, *, document: str) -> CalibrationCertificate:
    """Parse a Digital Calibration Certificate into its provenance and its measured values.

    ``document`` is the file name the values will cite as their source — the certificate is
    only checkable if a reader can go back to it. Every ``si:real`` quantity under the
    measurement results is offered, in document order, labelled by its own name where it has
    one and by its result's name otherwise. A quantity whose unit is outside the accepted
    D-SI vocabulary, or whose value is not a usable number, is recorded in ``unparsed``
    rather than dropped or guessed at.

    Raises :class:`ValueError` when the document is not a DCC at all, or when it lacks the
    identity a measured value's provenance is made of — an anonymous certificate is not a
    weaker certificate, it is not one.
    """
    if not document.strip():
        raise ValueError("a parsed certificate must name the document it came from")
    root = ET.fromstring(text)
    if root.tag != f"{{{DCC_NAMESPACE}}}digitalCalibrationCertificate":
        raise ValueError(
            f"root element is {root.tag!r}, not a DCC "
            f"({{{DCC_NAMESPACE}}}digitalCalibrationCertificate)"
        )
    provenance = _provenance(root)

    lines = _quantity_lines(text)
    values: list[CalibratedValue] = []
    unparsed: list[UnparsedLine] = []
    seen = 0
    results = root.find("dcc:measurementResults", _NS)
    for result_index, result in enumerate(
        [] if results is None else results.findall("dcc:measurementResult", _NS), start=1
    ):
        result_name = _content(result.find("dcc:name", _NS)) or f"measurementResult {result_index}"
        data_nodes = result.findall("dcc:results/dcc:result", _NS)
        for entry in data_nodes:
            entry_name = _content(entry.find("dcc:name", _NS)) or result_name
            data = entry.find("dcc:data", _NS)
            if data is None:
                continue
            for quantity in _quantities(data):
                # The line scan and this walk cover the same path in the same order, so the
                # nth pair belongs to the nth quantity. A malformed pairing degrades to the
                # first line rather than inventing one; the excerpt still locates it.
                quantity_line, value_line = lines[seen] if seen < len(lines) else (1, None)
                seen += 1
                label = _content(quantity.find("dcc:name", _NS)) or entry_name
                real = quantity.find("si:real", _NS)
                if real is None:
                    # D-SI offers seven quantity forms and this module reads one. Dropping
                    # the other six silently would let a certificate offer a value that
                    # Anvilate neither takes nor mentions, while the summary reported
                    # "0 not taken" — a gap in the evidence with nothing pointing at it.
                    offered = [
                        child.tag.rsplit("}", 1)[-1]
                        for child in quantity
                        if child.tag.startswith(f"{{{SI_NAMESPACE}}}")
                    ]
                    unparsed.append(
                        UnparsedLine(
                            source=SourceLocation(
                                document=document,
                                line_number=quantity_line,
                                excerpt=f"{label}: {', '.join(offered) or 'no D-SI quantity'}",
                            ),
                            reason=(
                                "the quantity is stated as "
                                f"{', '.join(f'si:{o}' for o in offered) or 'no D-SI form'}; "
                                "this module reads si:real, and converting another form would "
                                "mean choosing which of its values the design should use"
                            ),
                        )
                    )
                    continue
                raw_value = _text(real.find("si:value", _NS))
                raw_unit = _text(real.find("si:unit", _NS))
                excerpt = f"{label}: {raw_value} {raw_unit}"
                source = SourceLocation(
                    document=document,
                    line_number=value_line or quantity_line,
                    excerpt=excerpt.strip(),
                )
                magnitude = _decimal(raw_value)
                if magnitude is None:
                    unparsed.append(
                        UnparsedLine(
                            source=source,
                            reason=f"the value {raw_value!r} is not a usable number",
                        )
                    )
                    continue
                try:
                    measured = d_si_quantity(magnitude, raw_unit or "")
                except UnitError as exc:
                    unparsed.append(UnparsedLine(source=source, reason=str(exc)))
                    continue
                # The factor from the certificate's own unit to the one the quantity ended
                # up in. Taken from a unit magnitude of 1 rather than from the measured
                # value, so a certificate reporting exactly zero still scales correctly.
                scale = d_si_quantity(1.0, raw_unit or "").magnitude
                distribution, note = _distribution(real, measured.magnitude, scale)
                values.append(
                    CalibratedValue(
                        label=label,
                        quantity=measured,
                        source=source,
                        certificate=provenance,
                        distribution=distribution,
                        uncertainty_note=note,
                        distribution_unit=None if distribution is None else measured.unit,
                    )
                )
    return CalibrationCertificate(
        provenance=provenance, values=tuple(values), unparsed=tuple(unparsed)
    )
