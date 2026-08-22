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
from math import isfinite
from xml.etree import ElementTree as ET

from pydantic import BaseModel, ConfigDict

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

# Decimal SI prefixes, token to Pint symbol. The binary prefixes (kibi, mebi, …) are
# deliberately absent: they belong to information quantities, not to measurements a check
# consumes, and admitting them would mean admitting the units they prefix.
_D_SI_PREFIXES: dict[str, str] = {
    "deca": "da",
    "hecto": "h",
    "kilo": "k",
    "mega": "M",
    "giga": "G",
    "tera": "T",
    "peta": "P",
    "exa": "E",
    "zetta": "Z",
    "yotta": "Y",
    "deci": "d",
    "centi": "c",
    "milli": "m",
    "micro": "u",
    "nano": "n",
    "pico": "p",
    "femto": "f",
    "atto": "a",
    "zepto": "z",
    "yocto": "y",
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
    """
    if not unit.strip():
        raise UnitError("a D-SI unit expression is empty; a measured value must state its unit")
    if not unit.lstrip().startswith("\\"):
        raise UnitError(
            f"{unit!r} is not a D-SI unit expression; every token begins with a backslash "
            "(for example '\\\\milli\\\\metre')"
        )

    factors: list[str] = []
    pending: str | None = None  # the prefix symbol waiting for its unit
    pending_token: str | None = None
    named: list[str] = []
    for token in (t.strip() for t in unit.strip().split("\\")):
        if not token:
            continue
        exponent = _TOTHE.match(token)
        if exponent is not None:
            if not factors:
                raise UnitError(f"{unit!r} applies an exponent before naming a unit")
            factors[-1] = f"({factors[-1]}) ** {int(exponent.group('exponent'))}"
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
        factors.append(f"{pending or ''}{_D_SI_UNITS[token]}")
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
    expression = " * ".join(factors)
    try:
        built = Quantity(magnitude=value, unit=expression)
    except UnitError as exc:  # pragma: no cover - the table is what keeps this unreachable
        raise UnitError(f"{unit!r} maps to {expression!r}, which is not a unit: {exc}") from exc
    # Canonicalize the spelling. The assembled expression carries the parentheses the
    # exponents needed ("kg * (m) ** 2 * (s) ** -2"), and a quantity that renders like that
    # in a scorecard reads as a bug even though it is arithmetically identical.
    return built.to(expression)


def _distribution(real: ET.Element, nominal: float) -> tuple[InputDistribution | None, str | None]:
    """The certificate's stated uncertainty as an input distribution, or why there is none.

    Returns ``(distribution, reason)`` with exactly one of them set. An expanded uncertainty
    *U* at coverage factor *k* is a standard uncertainty of ``U/k``, which is what
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
            _decimal(_text(expanded.find("si:valueExpandedMU", _NS))),
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
            _decimal(_text(standard.find("si:valueStandardMU", _NS))),
            _text(standard.find("si:distribution", _NS)),
        )

    deprecated = real.find("si:expandedUnc", _NS)
    if deprecated is not None:
        return _expanded(
            nominal,
            _decimal(_text(deprecated.find("si:uncertainty", _NS))),
            _decimal(_text(deprecated.find("si:coverageFactor", _NS))),
            _text(deprecated.find("si:distribution", _NS)),
        )

    interval = real.find("si:coverageInterval", _NS)
    if interval is not None:
        return _standard(
            nominal,
            _decimal(_text(interval.find("si:standardUnc", _NS))),
            _text(interval.find("si:distribution", _NS)),
        )

    return None, "the certificate states no measurement uncertainty for this value"


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


class CalibratedValue(BaseModel):
    """One measured quantity a certificate offers, with its uncertainty and its origin."""

    model_config = ConfigDict(frozen=True)

    label: str
    quantity: Quantity
    source: SourceLocation
    certificate: CertificateProvenance
    # The certificate's stated uncertainty as a typed input distribution, ready for the
    # margin sampler. ``None`` when the certificate stated none or stated one this module
    # will not map, in which case ``uncertainty_note`` says which.
    distribution: InputDistribution | None = None
    uncertainty_note: str | None = None

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
        """The offered value with this label, or a refusal naming what is on offer."""
        for value in self.values:
            if value.label == label:
                return value
        raise KeyError(
            f"no measured value labelled {label!r} on certificate "
            f"{self.provenance.identifier}; it offers {sorted(v.label for v in self.values)}"
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


def _value_lines(text: str) -> list[int]:
    """The source line of each D-SI quantity value element, in document order.

    Empty when the document does not bind the D-SI namespace to a prefix (it may use a
    default namespace), in which case the caller falls back rather than guessing at lines.
    """
    prefixes = set(_SI_PREFIX.findall(text))
    if not prefixes:
        return []
    # `valueExpandedMU` and `valueStandardMU` do not match: the tag has to end at `value`.
    tag = re.compile("|".join(f"<{re.escape(p)}:value>" for p in sorted(prefixes)))
    lines: list[int] = []
    for number, line in enumerate(text.splitlines(), start=1):
        lines.extend(number for _ in tag.finditer(line))
    return lines


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
    seal = (
        None
        if laboratory is None
        else _text(laboratory.find("dcc:cryptElectronicSeal", _NS))
        or _text(laboratory.find("dcc:cryptElectronicSignature", _NS))
    )
    return CertificateProvenance(
        identifier=identifier or "",
        laboratory=lab_name or "",
        signature_status=(SignatureStatus.PRESENT_UNVERIFIED if signed else SignatureStatus.ABSENT),
        claims_electronic_seal=(seal or "").strip().lower() in {"true", "1"},
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

    lines = _value_lines(text)
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
                real = quantity.find("si:real", _NS)
                if real is None:
                    continue
                label = _content(quantity.find("dcc:name", _NS)) or entry_name
                raw_value = _text(real.find("si:value", _NS))
                raw_unit = _text(real.find("si:unit", _NS))
                # The line scan and the parse walk the same document in the same order, so
                # the nth value element is the nth quantity. A malformed pairing degrades to
                # the first line rather than inventing one, and the excerpt still locates it.
                line = lines[seen] if seen < len(lines) else 1
                seen += 1
                excerpt = f"{label}: {raw_value} {raw_unit}"
                source = SourceLocation(
                    document=document, line_number=line, excerpt=excerpt.strip()
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
                distribution, note = _distribution(real, magnitude)
                values.append(
                    CalibratedValue(
                        label=label,
                        quantity=measured,
                        source=source,
                        certificate=provenance,
                        distribution=distribution,
                        uncertainty_note=note,
                    )
                )
    return CalibrationCertificate(
        provenance=provenance, values=tuple(values), unparsed=tuple(unparsed)
    )
