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
