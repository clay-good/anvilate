"""Tests for Digital Calibration Certificate ingestion (PTB DCC v3.3.0 over D-SI v2.2.1).

The certificate below is a real one in the only sense that matters here: it validates
against the published ``dcc.xsd``. That is checked by the opt-in test at the bottom, which
skips rather than passes when the schema package is not present — so the rest of the suite
is reading a document whose shape was anchored to the standard, not to this module's
expectations of it.

What is pinned: the provenance a measured value carries, the honest signature vocabulary
(there is no "verified"), the D-SI unit table's refusals, and the uncertainty handoff — an
expanded uncertainty *U* at coverage factor *k* is a standard uncertainty of ``U/k``, and
that is what reaches the margin sampler.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from anvilate.dcc import CalibrationCertificate, d_si_quantity, parse_dcc
from anvilate.ingest import ConfirmationState, DraftSpec, SignatureStatus
from anvilate.uncertainty import Normal, Symmetric
from anvilate.units import UnitError

_SHAFT_QUANTITY = """\
            <dcc:quantity>
              <dcc:name><dcc:content lang="en">shaft diameter</dcc:content></dcc:name>
              <si:real>
                <si:value>25.0004</si:value>
                <si:unit>\\milli\\metre</si:unit>
                <si:measurementUncertaintyUnivariate>
                  <si:expandedMU>
                    <si:valueExpandedMU>0.0012</si:valueExpandedMU>
                    <si:coverageFactor>2</si:coverageFactor>
                    <si:coverageProbability>0.95</si:coverageProbability>
                  </si:expandedMU>
                </si:measurementUncertaintyUnivariate>
              </si:real>
            </dcc:quantity>
            <dcc:quantity>
              <dcc:name><dcc:content lang="en">ambient temperature</dcc:content></dcc:name>
              <si:real>
                <si:value>20.1</si:value>
                <si:unit>\\degreecelsius</si:unit>
                <si:measurementUncertaintyUnivariate>
                  <si:standardMU>
                    <si:valueStandardMU>0.2</si:valueStandardMU>
                  </si:standardMU>
                </si:measurementUncertaintyUnivariate>
              </si:real>
            </dcc:quantity>
"""


def _certificate(
    quantities: str = _SHAFT_QUANTITY,
    *,
    signature: bool = False,
    seal_claim: str = "false",
) -> str:
    """A schema-valid DCC around the given quantity block."""
    # A ds:Signature with no content is not a valid signature, and it is not meant to be:
    # what is being tested is that Anvilate reports its presence without claiming to have
    # checked it. The opt-in schema test uses the default (unsigned) document.
    signed = (
        '  <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" />\n' if signature else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<dcc:digitalCalibrationCertificate
    xmlns:dcc="https://ptb.de/dcc"
    xmlns:si="https://ptb.de/si"
    schemaVersion="3.3.0">
  <dcc:administrativeData>
    <dcc:dccSoftware>
      <dcc:software>
        <dcc:name><dcc:content lang="en">CalibrationWriter</dcc:content></dcc:name>
        <dcc:release>2.1.0</dcc:release>
      </dcc:software>
    </dcc:dccSoftware>
    <dcc:coreData>
      <dcc:countryCodeISO3166_1>DE</dcc:countryCodeISO3166_1>
      <dcc:usedLangCodeISO639_1>en</dcc:usedLangCodeISO639_1>
      <dcc:mandatoryLangCodeISO639_1>en</dcc:mandatoryLangCodeISO639_1>
      <dcc:uniqueIdentifier>PTB-2026-04711</dcc:uniqueIdentifier>
      <dcc:beginPerformanceDate>2026-05-04</dcc:beginPerformanceDate>
      <dcc:endPerformanceDate>2026-05-05</dcc:endPerformanceDate>
      <dcc:performanceLocation>laboratory</dcc:performanceLocation>
      <dcc:issueDate>2026-05-11</dcc:issueDate>
    </dcc:coreData>
    <dcc:items>
      <dcc:item>
        <dcc:name><dcc:content lang="en">ground shaft, drive end</dcc:content></dcc:name>
        <dcc:model>SH-25</dcc:model>
        <dcc:identifications>
          <dcc:identification>
            <dcc:issuer>manufacturer</dcc:issuer>
            <dcc:value>SN-88213</dcc:value>
          </dcc:identification>
        </dcc:identifications>
      </dcc:item>
    </dcc:items>
    <dcc:calibrationLaboratory>
      <dcc:contact>
        <dcc:name>
          <dcc:content lang="en">Physikalisch-Technische Bundesanstalt</dcc:content>
        </dcc:name>
        <dcc:location>
          <dcc:city>Braunschweig</dcc:city>
          <dcc:countryCode>DE</dcc:countryCode>
        </dcc:location>
      </dcc:contact>
      <dcc:cryptElectronicSeal>{seal_claim}</dcc:cryptElectronicSeal>
    </dcc:calibrationLaboratory>
    <dcc:respPersons>
      <dcc:respPerson>
        <dcc:person>
          <dcc:name><dcc:content lang="en">A. Metrologist</dcc:content></dcc:name>
        </dcc:person>
        <dcc:mainSigner>true</dcc:mainSigner>
      </dcc:respPerson>
    </dcc:respPersons>
    <dcc:customer>
      <dcc:name><dcc:content lang="en">Anvilate Engineering</dcc:content></dcc:name>
      <dcc:location><dcc:city>Leipzig</dcc:city></dcc:location>
    </dcc:customer>
  </dcc:administrativeData>
  <dcc:measurementResults>
    <dcc:measurementResult>
      <dcc:name><dcc:content lang="en">dimensional calibration</dcc:content></dcc:name>
      <dcc:results>
        <dcc:result>
          <dcc:name><dcc:content lang="en">shaft diameter</dcc:content></dcc:name>
          <dcc:data>
{quantities}          </dcc:data>
        </dcc:result>
      </dcc:results>
    </dcc:measurementResult>
  </dcc:measurementResults>
{signed}</dcc:digitalCalibrationCertificate>
"""


def _quantity_block(unit: str, value: str = "25.0004", uncertainty: str = "") -> str:
    return f"""\
            <dcc:quantity>
              <dcc:name><dcc:content lang="en">shaft diameter</dcc:content></dcc:name>
              <si:real>
                <si:value>{value}</si:value>
                <si:unit>{unit}</si:unit>
{uncertainty}              </si:real>
            </dcc:quantity>
"""


def _parsed(text: str | None = None) -> CalibrationCertificate:
    return parse_dcc(text if text is not None else _certificate(), document="PTB-2026-04711.xml")


# --- provenance -------------------------------------------------------------------------


def test_the_certificates_identity_travels_with_its_values():
    provenance = _parsed().provenance
    assert provenance.identifier == "PTB-2026-04711"
    assert provenance.laboratory == "Physikalisch-Technische Bundesanstalt"
    assert provenance.country == "DE"
    assert provenance.issue_date == "2026-05-11"
    assert provenance.performance_end_date == "2026-05-05"
    assert provenance.schema_version == "3.3.0"


def test_an_unsigned_certificate_says_so_rather_than_saying_nothing():
    provenance = _parsed().provenance
    assert provenance.signature_status is SignatureStatus.ABSENT
    assert "no signature" in provenance.signature_line()


def test_a_signature_is_reported_present_and_explicitly_unverified():
    """There is no VERIFIED state, because verifying one needs a trust anchor this tool
    does not have. Reporting a signature as checked would be the lie."""
    provenance = _parsed(_certificate(signature=True)).provenance
    assert provenance.signature_status is SignatureStatus.PRESENT_UNVERIFIED
    assert "NOT verified" in provenance.signature_line()
    assert not hasattr(SignatureStatus, "VERIFIED")


def test_a_claimed_seal_is_a_claim_not_a_signature():
    """A document asserting that it is sealed is not evidence that it is, so the claim and
    the fact are two fields and the summary refuses to conflate them."""
    provenance = _parsed(_certificate(seal_claim="true")).provenance
    assert provenance.claims_electronic_seal is True
    assert provenance.signature_status is SignatureStatus.ABSENT
    assert "claims an electronic seal it does not carry" in provenance.signature_line()


@pytest.mark.parametrize(
    ("mangled", "expected"),
    [
        ("<dcc:uniqueIdentifier>PTB-2026-04711</dcc:uniqueIdentifier>", "unique identifier"),
        (
            '<dcc:content lang="en">Physikalisch-Technische Bundesanstalt</dcc:content>',
            "name the laboratory",
        ),
    ],
)
def test_an_anonymous_certificate_is_not_a_weaker_certificate(mangled, expected):
    text = _certificate().replace(mangled, "")
    with pytest.raises(ValueError, match=expected):
        _parsed(text)


def test_a_document_that_is_not_a_dcc_is_refused_by_name():
    with pytest.raises(ValueError, match="not a DCC"):
        parse_dcc("<other xmlns='https://example.test'/>", document="x.xml")


def test_the_source_document_must_be_named():
    with pytest.raises(ValueError, match="name the document"):
        parse_dcc(_certificate(), document="  ")


# --- the values -------------------------------------------------------------------------


def test_the_measured_values_come_through_with_their_units():
    certificate = _parsed()
    assert [v.label for v in certificate.values] == ["shaft diameter", "ambient temperature"]
    shaft = certificate.labelled("shaft diameter")
    assert shaft.quantity.magnitude == pytest.approx(25.0004)
    assert shaft.quantity.unit == "mm"
    assert certificate.labelled("ambient temperature").quantity.to("K").magnitude == pytest.approx(
        293.25
    )


def test_a_values_source_line_points_at_the_measurement_not_the_serial_number():
    """A DCC's identification block carries `<dcc:value>` elements too. Scanning for any
    element named "value" put every measured value's line number in the administrative
    header, which sends a reader to a serial number to check a diameter."""
    text = _certificate()
    shaft = _parsed(text).labelled("shaft diameter")
    line = text.splitlines()[shaft.source.line_number - 1]
    assert "25.0004" in line
    assert "SN-88213" not in line


def test_an_unknown_unit_is_recorded_not_guessed_at():
    """The published schema types a unit as a free string, so an unrecognized token has
    nothing to be validated against — resolving it to something plausible is how a value
    lands in a check orders of magnitude out."""
    certificate = _parsed(_certificate(_quantity_block("\\milli\\furlong")))
    assert certificate.values == ()
    assert len(certificate.unparsed) == 1
    assert "furlong" in certificate.unparsed[0].reason


def test_a_value_that_is_not_a_number_is_recorded_not_dropped():
    certificate = _parsed(_certificate(_quantity_block("\\milli\\metre", value="NaN")))
    assert certificate.values == ()
    assert "not a usable number" in certificate.unparsed[0].reason


def test_the_summary_counts_what_was_taken_and_what_was_not():
    certificate = _parsed(_certificate(_SHAFT_QUANTITY + _quantity_block("\\furlong")))
    summary = certificate.summary()
    assert "2 measured value(s)" in summary
    assert "1 not taken" in summary


def test_asking_for_a_label_that_is_not_there_names_what_is():
    with pytest.raises(KeyError, match="shaft diameter"):
        _parsed().labelled("bore diameter")


# --- uncertainty handoff ----------------------------------------------------------------


def test_an_expanded_uncertainty_becomes_a_distribution_at_its_coverage_factor():
    """U at coverage factor k is a standard uncertainty of U/k — which is exactly what a
    half-width at a sigma level means, so this is the definition, not an approximation."""
    shaft = _parsed().labelled("shaft diameter")
    assert isinstance(shaft.distribution, Symmetric)
    assert shaft.distribution.half_width == pytest.approx(0.0012)
    assert shaft.distribution.sigma_level == pytest.approx(2.0)
    assert shaft.distribution.std == pytest.approx(0.0006)
    assert shaft.uncertainty_note is None


def test_a_standard_uncertainty_becomes_a_normal_directly():
    ambient = _parsed().labelled("ambient temperature")
    assert isinstance(ambient.distribution, Normal)
    assert ambient.distribution.std == pytest.approx(0.2)


def test_the_deprecated_expanded_spelling_is_read_too():
    """Certificates written against D-SI 1.x are in the world."""
    uncertainty = """\
                <si:expandedUnc>
                  <si:uncertainty>0.004</si:uncertainty>
                  <si:coverageFactor>2</si:coverageFactor>
                  <si:coverageProbability>0.95</si:coverageProbability>
                </si:expandedUnc>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert isinstance(value.distribution, Symmetric)
    assert value.distribution.std == pytest.approx(0.002)


def test_a_coverage_interval_hands_over_its_standard_uncertainty():
    uncertainty = """\
                <si:measurementUncertaintyUnivariate>
                  <si:coverageIntervalMU>
                    <si:valueStandardMU>0.0007</si:valueStandardMU>
                    <si:intervalMin>24.9990</si:intervalMin>
                    <si:intervalMax>25.0018</si:intervalMax>
                    <si:coverageProbability>0.95</si:coverageProbability>
                  </si:coverageIntervalMU>
                </si:measurementUncertaintyUnivariate>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert isinstance(value.distribution, Normal)
    assert value.distribution.std == pytest.approx(0.0007)


def test_a_non_gaussian_distribution_yields_none_and_names_itself():
    """A rectangular uncertainty and a normal one of the same width are different
    statements about the measurement; substituting one for the other is silent."""
    uncertainty = """\
                <si:measurementUncertaintyUnivariate>
                  <si:standardMU>
                    <si:valueStandardMU>0.0007</si:valueStandardMU>
                    <si:distribution>rectangular</si:distribution>
                  </si:standardMU>
                </si:measurementUncertaintyUnivariate>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert value.distribution is None
    assert "rectangular" in value.uncertainty_note


def test_an_expanded_uncertainty_with_no_coverage_factor_is_not_assumed_to_be_two():
    """k=2 is a convention, not this certificate's statement. Assuming it halves or doubles
    the standard uncertainty a check then samples."""
    uncertainty = """\
                <si:expandedUnc>
                  <si:uncertainty>0.004</si:uncertainty>
                  <si:coverageFactor>NaN</si:coverageFactor>
                  <si:coverageProbability>0.95</si:coverageProbability>
                </si:expandedUnc>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert value.distribution is None
    assert "coverage factor" in value.uncertainty_note


def test_a_certificate_with_no_stated_uncertainty_says_so():
    value = _parsed(_certificate(_quantity_block("\\milli\\metre"))).labelled("shaft diameter")
    assert value.distribution is None
    assert "states no measurement uncertainty" in value.uncertainty_note


# --- the confirmation flow --------------------------------------------------------------


def test_a_measured_value_is_a_draft_until_somebody_confirms_it():
    """A calibration certificate is a better source than an RFQ table. It is still not a
    person deciding that this measurement is the one the design should use."""
    shaft = _parsed().labelled("shaft diameter")
    draft = DraftSpec(
        values=(shaft.as_extracted("shaft_diameter"),), documents=("PTB-2026-04711.xml",)
    )
    assert draft.values[0].state is ConfirmationState.DRAFT
    with pytest.raises(ValueError, match="draft is not an input"):
        draft.release()

    confirmed = draft.with_confirmation("shaft_diameter", by="R. Engineer")
    released = confirmed.release()
    assert released["shaft_diameter"].to("mm").magnitude == pytest.approx(25.0004)


def test_the_certificate_provenance_survives_confirmation():
    """The whole point of the chain is that the confirmed value still names the instrument."""
    shaft = _parsed().labelled("shaft diameter")
    draft = DraftSpec(values=(shaft.as_extracted("shaft_diameter"),))
    value = draft.with_confirmation("shaft_diameter", by="R. Engineer").confirmed()[0]
    assert value.certificate is not None
    assert value.certificate.identifier == "PTB-2026-04711"
    assert value.certificate.signature_status is SignatureStatus.ABSENT
    assert "PTB-2026-04711" in str(value)


def test_an_unverified_signature_does_not_block_the_value():
    """The certificate is usable after confirmation whether or not it is signed. What must
    never happen is the value being presented as attested."""
    shaft = _parsed(_certificate(signature=True)).labelled("shaft diameter")
    draft = DraftSpec(values=(shaft.as_extracted("shaft_diameter"),))
    value = draft.with_confirmation("shaft_diameter", by="R. Engineer").confirmed()[0]
    assert value.usable is True
    assert "NOT verified" in value.certificate.signature_line()


# --- the D-SI unit vocabulary -----------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "unit", "magnitude"),
    [
        ("\\metre", "m", 1.0),
        ("\\milli\\metre", "mm", 1.0),
        ("\\micro\\metre", "µm", 1.0),
        ("\\mega\\pascal", "MPa", 1.0),
        ("\\kilo\\gram", "kg", 1.0),
        ("\\degreecelsius", "°C", 1.0),
        ("\\newton\\metre", "m * N", 1.0),
    ],
)
def test_the_unit_table_maps_what_it_declares(expression, unit, magnitude):
    quantity = d_si_quantity(magnitude, expression)
    assert quantity.unit == unit


def test_an_exponent_applies_to_the_unit_before_it():
    force = d_si_quantity(1.0, "\\kilo\\gram\\metre\\tothe{2}\\second\\tothe{-2}")
    assert force.to("J").magnitude == pytest.approx(1.0)


def test_a_negative_exponent_inverts():
    assert d_si_quantity(1.0, "\\metre\\tothe{-1}").to("1/mm").magnitude == pytest.approx(0.001)


@pytest.mark.parametrize(
    ("expression", "complaint"),
    [
        ("", "empty"),
        ("mm", "not a D-SI unit expression"),
        ("\\milli\\furlong", "unknown D-SI token"),
        ("\\milli\\kilo\\metre", "stacks two prefixes"),
        ("\\milli\\degreecelsius", "does not take one"),
        ("\\metre\\milli", "ends with the prefix"),
        ("\\tothe{2}", "exponent before naming a unit"),
        ("\\degreecelsius\\metre", "offset temperature has no meaning in a product"),
    ],
)
def test_the_unit_table_refuses_rather_than_guesses(expression, complaint):
    with pytest.raises(UnitError, match=complaint):
        d_si_quantity(1.0, expression)


# --- the anchor -------------------------------------------------------------------------


def test_the_fixture_validates_against_the_published_dcc_schema():
    """The real conformance check, opt-in because the schemas are a separate download.

    Point ``ANVILATE_DCC_XSD`` at a directory holding ``dcc.xsd`` (PTB, LGPL, from
    https://gitlab.com/ptb/dcc/xsd-dcc) with ``lxml`` installed and its imports resolvable,
    and this validates the fixture every other test in this file reads. Skipped otherwise —
    an unrunnable check is reported as not run, never as a pass.
    """
    etree = pytest.importorskip("lxml.etree")
    location = os.environ.get("ANVILATE_DCC_XSD")
    if not location:
        pytest.skip("set ANVILATE_DCC_XSD to a directory holding the PTB dcc.xsd")
    schema_file = Path(location) / "dcc.xsd"
    if not schema_file.exists():
        pytest.skip(f"no dcc.xsd under {location}")
    schema = etree.XMLSchema(etree.parse(str(schema_file)))
    document = etree.fromstring(_certificate().encode("utf-8"))
    assert schema.validate(document), "\n".join(str(e) for e in schema.error_log)


# --- what a five-agent audit found the day this module shipped --------------------------
#
# Every test below is a defect that was live in the first commit of this module. Two of them
# were wrong *numbers* with the right dimension, which is the shape that gets past every
# other guard in the library.


def test_no_prefix_and_unit_pair_maps_to_a_different_unit():
    """The one that mattered: gluing a prefix symbol onto a unit symbol builds tokens Pint
    already owns. ``centi`` + ``t`` is ``ct``, a *carat* — so ``\\centi\\tonne`` came back
    as 0.0002 kg where the certificate said 10 kg, and it stayed a mass, so nothing
    downstream could notice. Eight of the 820 pairs collided (kt knot, ft foot, pt pint, at
    technical atmosphere, dat, Tt tex, mcd microday).

    This sweeps every pair against an independent registry and the prefix's own power of
    ten, so a new unit added to the table cannot reintroduce the class.
    """
    pint = pytest.importorskip("pint")
    from anvilate.dcc import _D_SI_PREFIXES, _D_SI_UNITS, _UNPREFIXABLE

    # The SI definition of each token, spelled in long form so the comparison never routes
    # through the same two-letter symbols the defect was made of.
    long_form = {
        "metre": "meter",
        "kilogram": "kilogram",
        "second": "second",
        "ampere": "ampere",
        "kelvin": "kelvin",
        "mole": "mole",
        "candela": "candela",
        "gram": "gram",
        "hertz": "hertz",
        "newton": "newton",
        "pascal": "pascal",
        "joule": "joule",
        "watt": "watt",
        "coulomb": "coulomb",
        "volt": "volt",
        "farad": "farad",
        "ohm": "ohm",
        "siemens": "siemens",
        "weber": "weber",
        "tesla": "tesla",
        "henry": "henry",
        "lumen": "lumen",
        "lux": "lux",
        "becquerel": "becquerel",
        "gray": "gray",
        "sievert": "sievert",
        "katal": "katal",
        "radian": "radian",
        "steradian": "steradian",
        "degreecelsius": "degC",
        "minute": "minute",
        "hour": "hour",
        "day": "day",
        "degree": "degree",
        "arcminute": "arcminute",
        "arcsecond": "arcsecond",
        "litre": "liter",
        "tonne": "metric_ton",
        "electronvolt": "electron_volt",
        "dalton": "dalton",
        "astronomicalunit": "astronomical_unit",
    }
    assert set(long_form) == set(_D_SI_UNITS), (
        "a D-SI unit was added or removed without its independent reference; the sweep "
        "below is the only thing standing between the table and a silent unit swap"
    )
    # The prefixes' powers of ten, written out here rather than read from the module. Taking
    # them from `_D_SI_PREFIXES` made the comparison circular: a prefix whose power drifted
    # was checked against its own drifted value and the sweep stayed green.
    powers = {
        "deca": 1,
        "hecto": 2,
        "kilo": 3,
        "mega": 6,
        "giga": 9,
        "tera": 12,
        "peta": 15,
        "exa": 18,
        "zetta": 21,
        "yotta": 24,
        "deci": -1,
        "centi": -2,
        "milli": -3,
        "micro": -6,
        "nano": -9,
        "pico": -12,
        "femto": -15,
        "atto": -18,
        "zepto": -21,
        "yocto": -24,
    }
    assert set(powers) == set(_D_SI_PREFIXES), (
        "a D-SI prefix was added or removed without its independent power of ten"
    )
    registry = pint.UnitRegistry()
    wrong = []
    for token, _symbol in _D_SI_UNITS.items():
        reference = registry.Unit(long_form[token])
        # The bare token first. 34 of the 41 never appeared anywhere in this file, so a
        # one-character slip in the table ("tonne": "kg") read a 1.2 tonne measurement as
        # 1.2 kg — a thousandfold understatement with a valid dimension.
        bare = d_si_quantity(1.0, f"\\{token}").pint
        expected = registry.Quantity(1.0, reference)
        if bare.dimensionality != expected.dimensionality:
            wrong.append(f"\\{token} -> {bare} (should be {expected})")
        elif token != "degreecelsius" and not (
            abs(bare.to_base_units().magnitude - expected.to_base_units().magnitude)
            <= 1e-9 * abs(expected.to_base_units().magnitude)
        ):
            wrong.append(f"\\{token} -> {bare} (should be {expected})")
        if token in _UNPREFIXABLE:
            continue
        for prefix in _D_SI_PREFIXES:
            got = d_si_quantity(1.0, f"\\{prefix}\\{token}").pint.to_base_units()
            want = registry.Quantity(10.0 ** powers[prefix], reference).to_base_units()
            if got.dimensionality != want.dimensionality or not (
                abs(got.magnitude - want.magnitude) <= 1e-9 * abs(want.magnitude)
            ):
                wrong.append(f"\\{prefix}\\{token} -> {got} (should be {want})")
    assert not wrong, "prefix-unit pairs that map to the wrong unit:\n  " + "\n  ".join(wrong)


def test_the_collision_case_that_started_it():
    """A named regression: 10 centitonnes is 100 kg, not 2 grams of carat."""
    assert d_si_quantity(10.0, "\\centi\\tonne").to("kg").magnitude == pytest.approx(100.0)
    assert d_si_quantity(1.0, "\\milli\\candela").to("cd").magnitude == pytest.approx(1e-3)


def test_a_measurements_line_is_not_displaced_by_an_influence_condition():
    """`si:value` appears in influence conditions and item quantities too. Counting them
    document-wide shifted every measured value's line onto somebody else's number, which
    sends a reviewer checking a diameter to an ambient temperature."""
    influence = """\
              <dcc:influenceConditions>
                <dcc:influenceCondition>
                  <dcc:name><dcc:content lang="en">ambient</dcc:content></dcc:name>
                  <dcc:data>
                    <dcc:quantity>
                      <si:real>
                        <si:value>20.5</si:value>
                        <si:unit>\\degreecelsius</si:unit>
                      </si:real>
                    </dcc:quantity>
                  </dcc:data>
                </dcc:influenceCondition>
              </dcc:influenceConditions>
"""
    text = _certificate().replace("      <dcc:results>", influence + "      <dcc:results>", 1)
    shaft = _parsed(text).labelled("shaft diameter")
    assert "25.0004" in text.splitlines()[shaft.source.line_number - 1]


def test_a_default_namespace_document_still_reports_real_lines():
    """A certificate may bind D-SI as the default namespace. Scanning for `si:value` found
    nothing and every value was reported at line 1, with nothing marking it as a guess."""
    text = _certificate().replace('xmlns:si="https://ptb.de/si"', 'xmlns:d="https://ptb.de/si"')
    text = text.replace("<si:", "<d:").replace("</si:", "</d:")
    shaft = _parsed(text).labelled("shaft diameter")
    assert shaft.source.line_number > 1
    assert "25.0004" in text.splitlines()[shaft.source.line_number - 1]


def test_a_quantity_in_another_d_si_form_is_recorded_not_dropped():
    """D-SI offers seven quantity forms and this module reads one. The other six vanished
    without an `unparsed` line, so a certificate could offer a value Anvilate neither took
    nor mentioned while the summary said "0 not taken"."""
    hybrid = """\
            <dcc:quantity>
              <dcc:name><dcc:content lang="en">bore diameter</dcc:content></dcc:name>
              <si:hybrid>
                <si:real><si:value>12.7</si:value><si:unit>\\milli\\metre</si:unit></si:real>
                <si:real><si:value>0.5</si:value><si:unit>\\milli\\metre</si:unit></si:real>
              </si:hybrid>
            </dcc:quantity>
"""
    certificate = _parsed(_certificate(_SHAFT_QUANTITY + hybrid))
    assert len(certificate.values) == 2
    assert len(certificate.unparsed) == 1
    assert "si:hybrid" in certificate.unparsed[0].reason
    assert "bore diameter" in certificate.unparsed[0].source.excerpt
    assert "1 not taken" in certificate.summary()


def test_two_values_under_one_label_are_refused_rather_than_silently_first():
    """`dcc:quantity/dcc:name` is optional, so a result reporting several readings labels
    them all the same. Returning the first made the rest unreachable while looking like a
    lookup that worked."""
    second = _quantity_block("\\milli\\metre", value="18.2")
    certificate = _parsed(_certificate(_SHAFT_QUANTITY + second))
    assert len(certificate.values) == 3
    with pytest.raises(KeyError, match="carries 2 values"):
        certificate.labelled("shaft diameter")
    # Still reachable by position — the refusal is about ambiguity, not about the data.
    assert [v.quantity.magnitude for v in certificate.values if v.label == "shaft diameter"] == [
        pytest.approx(25.0004),
        pytest.approx(18.2),
    ]


def test_a_zeroth_power_is_refused_as_a_unit_not_as_a_crash():
    """`Quantity` raises `UnitError` inside a pydantic validator, so pydantic wrapped it in
    a ValidationError that `parse_dcc`'s `except UnitError` never saw — one malformed unit
    took the whole certificate down instead of one line."""
    with pytest.raises(UnitError, match="zeroth power"):
        d_si_quantity(1.0, "\\metre\\tothe{0}")
    certificate = _parsed(_certificate(_quantity_block("\\metre\\tothe{0}")))
    assert certificate.values == ()
    assert "zeroth power" in certificate.unparsed[0].reason


def test_a_responsible_persons_seal_claim_is_carried_too():
    """The schema lets the laboratory claim a seal and lets each responsible person claim
    one separately. Reading only the laboratory's copy under-claimed."""
    text = _certificate().replace(
        "<dcc:mainSigner>true</dcc:mainSigner>",
        "<dcc:mainSigner>true</dcc:mainSigner>"
        "<dcc:cryptElectronicSeal>true</dcc:cryptElectronicSeal>",
    )
    assert _parsed(text).provenance.claims_electronic_seal is True


def test_the_distribution_is_in_the_quantitys_own_unit_whatever_the_certificate_said():
    """The same shaft in micrometres. `quantity` is unit-checked and `distribution` is bare
    floats, so nothing else in the library can catch them drifting apart — and they did:
    the uncertainty was built from the raw magnitude while the quantity had been converted,
    so a micrometre certificate handed a 25000.4-centred distribution to a millimetre
    limit. Wrong by a factor of a thousand, dimensionally invisible, no unit recorded
    anywhere."""
    expanded = """\
                <si:measurementUncertaintyUnivariate>
                  <si:expandedMU>
                    <si:valueExpandedMU>1.2</si:valueExpandedMU>
                    <si:coverageFactor>2</si:coverageFactor>
                    <si:coverageProbability>0.95</si:coverageProbability>
                  </si:expandedMU>
                </si:measurementUncertaintyUnivariate>
"""
    micro = _parsed(
        _certificate(_quantity_block("\\micro\\metre", value="25000.4", uncertainty=expanded))
    ).labelled("shaft diameter")
    milli = _parsed().labelled("shaft diameter")

    # Each distribution is centred on its own quantity, in its own unit.
    assert micro.distribution_unit == "µm"
    assert micro.distribution.mean == pytest.approx(micro.quantity.magnitude)
    assert milli.distribution_unit == "mm"
    assert milli.distribution.mean == pytest.approx(milli.quantity.magnitude)
    # And converting both to one unit gives one physical statement.
    for value in (micro, milli):
        in_mm = value.distribution_in("mm")
        assert in_mm.mean == pytest.approx(25.0004)
        assert in_mm.std == pytest.approx(0.0006)


def test_a_prefix_collisions_fallback_keeps_the_distribution_with_its_quantity():
    """`\\centi\\tonne` falls back to the bare unit with a scaled magnitude. An uncertainty
    left on the raw number would then be centred a hundredfold away from its own value."""
    standard = """\
                <si:measurementUncertaintyUnivariate>
                  <si:standardMU><si:valueStandardMU>0.5</si:valueStandardMU></si:standardMU>
                </si:measurementUncertaintyUnivariate>
"""
    value = _parsed(
        _certificate(_quantity_block("\\centi\\tonne", value="10.0", uncertainty=standard))
    ).labelled("shaft diameter")
    assert value.quantity.to("kg").magnitude == pytest.approx(100.0)
    assert value.distribution.mean == pytest.approx(value.quantity.magnitude)
    in_kg = value.distribution_in("kg")
    assert in_kg.mean == pytest.approx(100.0)
    assert in_kg.std == pytest.approx(5.0)


def test_a_distribution_that_is_not_its_own_quantity_is_refused_at_construction():
    """The invariant is enforced where it can be, not only where it happened to hold."""
    from anvilate.dcc import CalibratedValue
    from anvilate.uncertainty import Normal

    good = _parsed().labelled("shaft diameter")
    with pytest.raises(ValueError, match="different unit from its own quantity"):
        CalibratedValue(
            label=good.label,
            quantity=good.quantity,
            source=good.source,
            certificate=good.certificate,
            distribution=Normal(mean=25000.4, std=0.6),
            distribution_unit=good.quantity.unit,
        )


def test_a_certificate_reporting_exactly_zero_still_scales_its_uncertainty():
    """The conversion factor is taken from a unit magnitude, not from the measured value —
    dividing by the value would make a zero reading a ZeroDivisionError."""
    standard = """\
                <si:measurementUncertaintyUnivariate>
                  <si:standardMU><si:valueStandardMU>0.5</si:valueStandardMU></si:standardMU>
                </si:measurementUncertaintyUnivariate>
"""
    value = _parsed(
        _certificate(_quantity_block("\\micro\\metre", value="0.0", uncertainty=standard))
    ).labelled("shaft diameter")
    assert value.quantity.magnitude == pytest.approx(0.0)
    assert value.distribution.std == pytest.approx(0.5)
    assert value.distribution_in("mm").std == pytest.approx(0.0005)


def test_a_table_of_points_in_a_dcc_list_is_read_not_skipped():
    """`dcc:list` is the standard container for a table of readings. The recursion into it
    had no test at all: deleting it left the suite green while every listed quantity
    disappeared the same silent way a dropped quantity does."""
    listed = """\
            <dcc:list>
              <dcc:name><dcc:content lang="en">run-out sweep</dcc:content></dcc:name>
              <dcc:quantity>
                <dcc:name><dcc:content lang="en">run-out at 0 deg</dcc:content></dcc:name>
                <si:real><si:value>0.004</si:value><si:unit>\\milli\\metre</si:unit></si:real>
              </dcc:quantity>
              <dcc:quantity>
                <dcc:name><dcc:content lang="en">run-out at 90 deg</dcc:content></dcc:name>
                <si:real><si:value>0.006</si:value><si:unit>\\milli\\metre</si:unit></si:real>
              </dcc:quantity>
            </dcc:list>
"""
    certificate = _parsed(_certificate(_SHAFT_QUANTITY + listed))
    assert [v.label for v in certificate.values] == [
        "shaft diameter",
        "ambient temperature",
        "run-out at 0 deg",
        "run-out at 90 deg",
    ]
    assert certificate.labelled("run-out at 90 deg").quantity.to("mm").magnitude == pytest.approx(
        0.006
    )


def test_the_deprecated_expanded_spelling_also_refuses_a_non_gaussian_distribution():
    uncertainty = """\
                <si:expandedUnc>
                  <si:uncertainty>0.004</si:uncertainty>
                  <si:coverageFactor>2</si:coverageFactor>
                  <si:coverageProbability>0.95</si:coverageProbability>
                  <si:distribution>rectangular</si:distribution>
                </si:expandedUnc>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert value.distribution is None
    assert "rectangular" in value.uncertainty_note


@pytest.mark.parametrize("spelling", ["cryptElectronicSeal", "cryptElectronicSignature"])
@pytest.mark.parametrize("truth", ["true", "1"])
def test_every_spelling_of_the_seal_claim_is_read(spelling, truth):
    text = _certificate().replace(
        "<dcc:cryptElectronicSeal>false</dcc:cryptElectronicSeal>",
        f"<dcc:{spelling}>{truth}</dcc:{spelling}>",
    )
    assert _parsed(text).provenance.claims_electronic_seal is True


def test_the_extracted_value_keeps_the_certificates_own_source_line():
    """`as_extracted` hands the measurement to the confirmation flow. If it invented a
    location instead of passing the certificate's, the audit trail would end at the door."""
    shaft = _parsed().labelled("shaft diameter")
    extracted = shaft.as_extracted("shaft_diameter")
    assert extracted.source == shaft.source
    assert extracted.quantity == shaft.quantity
    assert extracted.certificate == shaft.certificate


def test_converting_an_uncertainty_across_an_offset_unit_keeps_it_a_width():
    """A degree Celsius converts affinely and an uncertainty in it does not. Multiplying the
    width by the value's own conversion would turn a 0.2 K uncertainty into 273.35."""
    ambient = _parsed().labelled("ambient temperature")
    in_kelvin = ambient.distribution_in("K")
    assert in_kelvin.mean == pytest.approx(293.25)
    assert in_kelvin.std == pytest.approx(0.2)


@pytest.mark.parametrize("token", sorted(__import__("anvilate.dcc", fromlist=["x"])._UNPREFIXABLE))
def test_a_prefix_on_a_unit_that_does_not_take_one_is_refused(token):
    """Only ``degreecelsius`` was tested. The other nine are the non-decimal and
    fixed-magnitude units whose whole point is that a decimal prefix on them is meaningless
    — under drift, Pint invents a magnitude for `\\milli\\hour` and nothing objects."""
    with pytest.raises(UnitError, match="does not take one"):
        d_si_quantity(1.0, f"\\milli\\{token}")


def test_the_certificates_own_coverage_factor_is_what_is_used():
    """Every fixture stated k=2, so `sigma_level=coverage_factor` could have been written
    `sigma_level=2.0` and the suite would not have noticed. k=3 is ordinary on accredited
    certificates, and reading it as 2 inflates the standard uncertainty by 50%."""
    for factor, expected_std in ((1, 0.0012), (3, 0.0004), (4, 0.0003)):
        uncertainty = f"""\
                <si:measurementUncertaintyUnivariate>
                  <si:expandedMU>
                    <si:valueExpandedMU>0.0012</si:valueExpandedMU>
                    <si:coverageFactor>{factor}</si:coverageFactor>
                    <si:coverageProbability>0.95</si:coverageProbability>
                  </si:expandedMU>
                </si:measurementUncertaintyUnivariate>
"""
        value = _parsed(
            _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
        ).labelled("shaft diameter")
        assert value.distribution.sigma_level == pytest.approx(float(factor))
        assert value.distribution.std == pytest.approx(expected_std)


@pytest.mark.parametrize("spelling", ["normal", "Normal", "gaussian", " GAUSSIAN ", "  normal "])
def test_every_accepted_spelling_of_a_gaussian_distribution_is_taken(spelling):
    """`gaussian` is the commoner spelling on European accredited certificates. Losing it
    does not produce a wrong number — it produces no distribution at all, so the sampler
    treats a well-characterized measurement as having no scatter and the fragility verdict
    goes quiet."""
    uncertainty = f"""\
                <si:measurementUncertaintyUnivariate>
                  <si:standardMU>
                    <si:valueStandardMU>0.0006</si:valueStandardMU>
                    <si:distribution>{spelling}</si:distribution>
                  </si:standardMU>
                </si:measurementUncertaintyUnivariate>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert value.distribution is not None
    assert value.distribution.std == pytest.approx(0.0006)
    assert value.uncertainty_note is None


@pytest.mark.parametrize("factor", ["0", "0.0"])
def test_a_non_positive_coverage_factor_degrades_visibly_rather_than_fatally(factor):
    """The suite only ever reached the `None` arm of the guard. A certificate stating k=0
    crashed `parse_dcc` with a pydantic traceback instead of recording a note — and this
    module's whole contract is that a bad certificate degrades visibly, not fatally."""
    uncertainty = f"""\
                <si:expandedUnc>
                  <si:uncertainty>0.0012</si:uncertainty>
                  <si:coverageFactor>{factor}</si:coverageFactor>
                  <si:coverageProbability>0.95</si:coverageProbability>
                </si:expandedUnc>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert value.distribution is None
    assert "coverage factor" in value.uncertainty_note


def test_a_backslash_with_no_token_after_it_is_refused():
    """A guard the raise-site instrument found had never executed under the whole suite."""
    with pytest.raises(UnitError, match="names no unit"):
        d_si_quantity(1.0, "\\")


def test_a_document_with_no_administrative_block_is_refused():
    text = _certificate()
    start = text.index("<dcc:administrativeData>")
    end = text.index("</dcc:administrativeData>") + len("</dcc:administrativeData>")
    with pytest.raises(ValueError, match="no administrativeData"):
        _parsed(text[:start] + text[end:])


def test_a_document_with_no_core_data_is_refused():
    text = _certificate()
    start = text.index("<dcc:coreData>")
    end = text.index("</dcc:coreData>") + len("</dcc:coreData>")
    with pytest.raises(ValueError, match="no coreData"):
        _parsed(text[:start] + text[end:])


def test_the_d_si_1_x_coverage_interval_spelling_is_read_too():
    """The deprecated branch could be deleted whole and the suite stayed green — and a
    certificate that states its uncertainty would come back reporting that it stated none,
    which is a false statement about the document rather than a missing feature."""
    uncertainty = """\
                <si:coverageInterval>
                  <si:standardUnc>0.0007</si:standardUnc>
                  <si:intervalMin>24.9990</si:intervalMin>
                  <si:intervalMax>25.0018</si:intervalMax>
                  <si:coverageProbability>0.95</si:coverageProbability>
                </si:coverageInterval>
"""
    value = _parsed(
        _certificate(_quantity_block("\\milli\\metre", uncertainty=uncertainty))
    ).labelled("shaft diameter")
    assert value.distribution is not None
    assert value.distribution.std == pytest.approx(0.0007)
    assert value.uncertainty_note is None


def test_every_value_gets_its_own_line_not_just_the_first():
    """The line scan was pinned only for the first quantity: a scan returning four entries
    where two were right left the shaft correct by being index 0 while every value after it
    silently cited somebody else's number."""
    text = _certificate()
    certificate = _parsed(text)
    lines = text.splitlines()
    for value in certificate.values:
        assert str(value.quantity.magnitude) in lines[value.source.line_number - 1], (
            f"{value.label} cites line {value.source.line_number}, which reads "
            f"{lines[value.source.line_number - 1].strip()!r}"
        )


# --- what a second audit wave found in the first wave's fixes ---------------------------


def test_a_prefixed_unit_with_an_exponent_scales_by_the_exponent_too():
    r"""No test used a prefixed unit with a `tothe{}` exponent at all, so the whole
    prefix-times-exponent path was unpinned: dropping the exponent from the scale gave
    `\milli\metre\tothe{2}` as 0.001 m^2 instead of 1e-6 m^2 — a thousandfold error, and the
    same factor reaches the uncertainty, which is scaled by the same number."""
    assert d_si_quantity(1.0, "\\milli\\metre\\tothe{2}").to("m ** 2").magnitude == pytest.approx(
        1e-6
    )
    assert d_si_quantity(1.0, "\\centi\\metre\\tothe{3}").to("m ** 3").magnitude == pytest.approx(
        1e-6
    )
    assert d_si_quantity(1.0, "\\milli\\metre\\tothe{-1}").to("1/m").magnitude == pytest.approx(
        1000.0
    )
    assert d_si_quantity(2.0, "\\kilo\\gram\\tothe{-1}").to("1/kg").magnitude == pytest.approx(2.0)


def test_a_zero_reading_does_not_get_to_skip_the_prefix_proof():
    r"""The proof was skipped whenever the computed magnitude was exactly 0.0 — 0.0 compared
    equal to 0.0 — so a reading of zero adopted the colliding spelling unchallenged.
    `\centi\tonne` came back as carats, and `parse_dcc` then scaled the certificate's
    uncertainty into a unit five million times too small, while the neighbouring non-zero
    reading on the same certificate was right."""
    zero = d_si_quantity(0.0, "\\centi\\tonne")
    nonzero = d_si_quantity(1.0, "\\centi\\tonne")
    assert zero.unit == nonzero.unit == "t"
    standard = """\
                <si:measurementUncertaintyUnivariate>
                  <si:standardMU><si:valueStandardMU>0.5</si:valueStandardMU></si:standardMU>
                </si:measurementUncertaintyUnivariate>
"""
    for magnitude in ("0.0", "0.001"):
        value = _parsed(
            _certificate(_quantity_block("\\centi\\tonne", value=magnitude, uncertainty=standard))
        ).labelled("shaft diameter")
        # 0.5 centitonne is 5 kg whatever the reading itself was.
        assert value.distribution_in("kg").std == pytest.approx(5.0)


def test_the_prefix_proof_refuses_a_near_miss_not_just_an_order_of_magnitude():
    """The only collisions the fixtures exercise are order-of-magnitude ones, so the proof's
    tolerance could be loosened to 50% and nothing complained. A spelling within a factor of
    1.5 of the truth is still the wrong unit."""
    from anvilate.dcc import _spelling_holds

    assert _spelling_holds("mm", "m", 1e-3)
    assert not _spelling_holds("mm", "m", 1e-3 * 1.0001)
    assert not _spelling_holds("mm", "m", 1e-3 * 1.5)
    # A dimension mismatch is a refusal, not an exception.
    assert not _spelling_holds("kn", "t", 1e3)


def test_the_distribution_invariant_refuses_a_small_relative_drift():
    """`rel_tol` was unpinned: the guard that exists to catch a distribution drifting from
    its own quantity would have accepted a 10% mismatch."""
    from anvilate.dcc import CalibratedValue
    from anvilate.uncertainty import Normal

    good = _parsed().labelled("shaft diameter")
    with pytest.raises(ValueError, match="different unit from its own quantity"):
        CalibratedValue(
            label=good.label,
            quantity=good.quantity,
            source=good.source,
            certificate=good.certificate,
            distribution=Normal(mean=good.quantity.magnitude * 1.01, std=0.0006),
            distribution_unit=good.quantity.unit,
        )


def test_the_distribution_invariant_is_not_disarmed_at_small_magnitudes():
    """`abs_tol=1e-12` disarmed the relative tolerance exactly the way this repository's known
    `pytest.approx` trap does: a 1e-13 m reading accepted a distribution centred anywhere up
    to 1.1e-12 — a tenfold error — and accepted one centred on zero."""
    from anvilate.dcc import CalibratedValue
    from anvilate.uncertainty import Normal

    good = _parsed().labelled("shaft diameter")
    tiny = good.quantity.model_copy(update={"magnitude": 1e-13})
    for wrong_centre in (1e-12, 5e-13, 0.0):
        with pytest.raises(ValueError, match="different unit from its own quantity"):
            CalibratedValue(
                label=good.label,
                quantity=tiny,
                source=good.source,
                certificate=good.certificate,
                distribution=Normal(mean=wrong_centre, std=1e-15),
                distribution_unit=tiny.unit,
            )
    # A genuine zero reading with a zero-centred distribution is still legitimate.
    zero = good.quantity.model_copy(update={"magnitude": 0.0})
    CalibratedValue(
        label=good.label,
        quantity=zero,
        source=good.source,
        certificate=good.certificate,
        distribution=Normal(mean=0.0, std=1e-6),
        distribution_unit=zero.unit,
    )


def test_the_distribution_invariant_survives_model_copy():
    """`model_copy` does not run a `mode="after"` validator, so the only check in the library
    that can catch these two drifting apart was one call away from being walked around."""
    from anvilate.uncertainty import Normal

    good = _parsed().labelled("shaft diameter")
    with pytest.raises(ValueError, match="different unit from its own quantity"):
        good.model_copy(update={"distribution": Normal(mean=99.0, std=0.01)})
    with pytest.raises(ValueError, match="different unit from its own quantity"):
        good.model_copy(update={"quantity": good.quantity.model_copy(update={"unit": "m"})})
    # An unrelated copy still works, and keeps everything it carried.
    relabelled = good.model_copy(update={"label": "journal diameter"})
    assert relabelled.label == "journal diameter"
    assert relabelled.distribution == good.distribution
    assert relabelled.certificate == good.certificate


@pytest.mark.parametrize("separator", ["", " ", " "])
def test_a_unicode_line_separator_does_not_shift_every_reported_line(separator):
    """`str.splitlines()` breaks on U+0085, U+2028 and U+2029, which XML 1.0 treats as
    ordinary characters. Each one pushed every later quantity's reported line out by one, and
    the shaft diameter ended up citing the ambient temperature's value — the exact failure
    this scan was rewritten to prevent, coming back through the splitter."""
    text = _certificate().replace(
        "ground shaft, drive end", f"ground{separator}shaft,{separator}drive end"
    )
    certificate = _parsed(text)
    lines = text.split("\n")
    for value in certificate.values:
        assert str(value.quantity.magnitude) in lines[value.source.line_number - 1]


def test_a_stray_value_element_cannot_steal_a_measurements_line():
    """The `si:real` parent check had no test behind it, so a `si:value` sitting anywhere
    inside a quantity could take a measurement's line number."""
    decoy = """\
            <dcc:quantity>
              <dcc:name><dcc:content lang="en">bore diameter</dcc:content></dcc:name>
              <si:hybrid>
                <si:real><si:value>99.9</si:value><si:unit>\\milli\\metre</si:unit></si:real>
              </si:hybrid>
            </dcc:quantity>
"""
    text = _certificate(decoy + _SHAFT_QUANTITY)
    shaft = _parsed(text).labelled("shaft diameter")
    assert "25.0004" in text.split("\n")[shaft.source.line_number - 1]


def test_the_unparsed_reason_names_only_the_d_si_forms_it_found():
    """Without the namespace filter the refusal listed the quantity's `dcc:name` too, so the
    record a reader is meant to trust said "the quantity is stated as si:name" — an untrue
    sentence in the one place the module puts what it declined."""
    other = """\
            <dcc:quantity>
              <dcc:name><dcc:content lang="en">bore diameter</dcc:content></dcc:name>
              <si:complex>
                <si:real><si:value>1.0</si:value><si:unit>\\milli\\metre</si:unit></si:real>
                <si:real><si:value>2.0</si:value><si:unit>\\milli\\metre</si:unit></si:real>
              </si:complex>
            </dcc:quantity>
"""
    certificate = _parsed(_certificate(_SHAFT_QUANTITY + other))
    reason = certificate.unparsed[0].reason
    assert "si:complex" in reason
    assert "si:name" not in reason


def test_a_value_element_outside_si_real_cannot_take_a_measurements_line():
    """`parse_dcc` reads well-formed XML; it does not validate. So a certificate that is not
    schema-valid — and those exist — must still not misreport where a measurement was read.
    The `si:real` parent check is what stops any stray `si:value` in the quantity's subtree
    from claiming the line, and it had no test behind it."""
    stray = """\
            <dcc:quantity>
              <dcc:name><dcc:content lang="en">shaft diameter</dcc:content></dcc:name>
              <dcc:description>
                <dcc:content lang="en">re-measured</dcc:content>
                <si:value>99.9</si:value>
              </dcc:description>
              <si:real>
                <si:value>25.0004</si:value>
                <si:unit>\\milli\\metre</si:unit>
              </si:real>
            </dcc:quantity>
"""
    text = _certificate(stray)
    shaft = _parsed(text).labelled("shaft diameter")
    cited = text.split("\n")[shaft.source.line_number - 1]
    assert "25.0004" in cited
    assert "99.9" not in cited


def test_a_value_says_why_it_carries_no_distribution():
    """ "no distribution" was two different facts printed as one: a certificate that stated no
    uncertainty, and one that stated an uncertainty this module will not map.

    `uncertainty_note` says which — its own field docstring says it says which — and nothing
    rendered it, so a reader could not tell an absent claim from an unread one.
    """
    from anvilate.dcc import CalibratedValue
    from anvilate.ingest import CertificateProvenance, SignatureStatus, SourceLocation
    from anvilate.units import Quantity

    provenance = CertificateProvenance(
        identifier="PTB-2026-1", laboratory="PTB", signature_status=SignatureStatus.ABSENT
    )
    location = SourceLocation(document="cert.xml", line_number=1, excerpt="d = 25 mm")
    value = CalibratedValue(
        label="shaft diameter",
        quantity=Quantity.parse("25 mm"),
        source=location,
        certificate=provenance,
    )
    assert "[no distribution]" in str(value)

    unread = value.model_copy(
        update={
            "uncertainty_note": "the certificate states a coverage factor this module does not map"
        }
    )
    assert "no distribution: the certificate states a coverage factor" in str(unread)


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("not XML at all", "{}"),
        ("a truncated document", "<dcc:digitalCalibrationCertificate"),
        (
            "an external entity reference",
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE dcc [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>\n'
            '<dcc:digitalCalibrationCertificate xmlns:dcc="https://ptb.de/dcc">'
            "<x>&xxe;</x></dcc:digitalCalibrationCertificate>",
        ),
        (
            "an entity expansion bomb",
            '<?xml version="1.0"?>\n'
            "<!DOCTYPE dcc [\n"
            ' <!ENTITY a "aaaaaaaaaa">\n'
            ' <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">\n'
            ' <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">\n'
            ' <!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">\n'
            ' <!ENTITY e "&d;&d;&d;&d;&d;&d;&d;&d;&d;&d;">\n'
            ' <!ENTITY f "&e;&e;&e;&e;&e;&e;&e;&e;&e;&e;">\n'
            ' <!ENTITY g "&f;&f;&f;&f;&f;&f;&f;&f;&f;&f;">\n'
            "]>\n"
            '<dcc:digitalCalibrationCertificate xmlns:dcc="https://ptb.de/dcc">'
            "<x>&g;</x></dcc:digitalCalibrationCertificate>",
        ),
    ],
)
def test_a_malformed_certificate_is_refused_by_the_documented_exception(label, text):
    """`ParseError` is a `SyntaxError`, not a `ValueError`.

    `parse_dcc`'s docstring says it raises `ValueError` when the document is not a DCC, and a
    malformed one raised the parser's own exception straight through a caller's handler. A
    certificate arrives from a calibration laboratory by email or portal, so malformed is the
    ordinary case rather than the exotic one — and `qif_schema_issues`, the library's other
    reader of somebody else's XML, has always treated a document it cannot parse as a
    complaint about the document.

    The external-entity case is here because it is the one an attacker sends: ElementTree
    refuses to resolve it, and that refusal now arrives as this module's own error with the
    file named.

    The expansion bomb is the other one. Seven nested entities expand to a hundred million
    characters from a document under a kilobyte, and a reader that expands them is a hang
    rather than an error. CPython's expat caps the amplification factor and refuses it — a
    property of the interpreter rather than of this code, which is exactly why it is
    asserted here: an interpreter without that cap turns a mailed certificate into a denial
    of service, and this fails rather than letting it through quietly.
    """
    with pytest.raises(ValueError, match="not well-formed XML"):
        parse_dcc(text, document="cert.xml")


def test_the_bomb_is_refused_for_its_size_rather_than_because_entities_are_inert():
    """The positive control, without which the test above proves much less than it looks.

    "The parser refused a document containing entities" has two explanations: the expansion
    limit caught it, or the parser does not process internal entities at all and the
    reference was simply undefined. Only the first is the protection this rests on — a
    parser of the second kind would still refuse the bomb and would refuse every legitimate
    certificate that uses an entity too.

    So: a small internal entity has to expand and be read. It does, which is what makes the
    refusal above a statement about amplification.
    """
    from xml.etree import ElementTree as ET

    document = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE r [<!ENTITY lab "Physikalisch-Technische Bundesanstalt">]>\n'
        "<r><name>&lab;</name></r>"
    )
    root = ET.fromstring(document)
    assert root.findtext("name") == "Physikalisch-Technische Bundesanstalt"
