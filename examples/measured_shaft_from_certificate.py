"""Worked example: a measured shaft, and the measurement that cannot settle the question.

A drawing calls a 25 mm shaft to ISO 286 **h6**: upper limit 25.0000 mm, lower limit
24.9870 mm. A calibration laboratory measures the finished part at **25.0004 mm**, with an
expanded uncertainty of ±0.0012 mm at coverage factor k = 2.

The deterministic verdict is a failure: 25.0004 is 0.4 µm above the h6 upper limit. But the
certificate's own uncertainty is *three times* that overshoot, and the honest reading is
that this measurement does not decide the question — the shaft is out of tolerance on the
number and inside tolerance on about a quarter of the distribution the laboratory itself
declared. Anvilate reports both: the verdict, and the fact that the measurement cannot
support it at that resolution.

Getting there takes three steps, and the first two are the ones this module is about:

1. **The certificate is read.** The identifier, the issuing laboratory, and the signature
   situation come off it. This one is unsigned, and that is what the provenance says. Had it
   been signed, the provenance would say the signature is present and *not verified* —
   there is no third state, because verifying one needs a trust anchor an offline tool does
   not have.
2. **The measured value is a draft.** It goes through the same per-value, per-person
   confirmation an RFQ number does. ``release()`` refuses first and succeeds after — a
   calibration certificate is a better source than a customer's table, and it is still not
   a person deciding that this measurement is the one the design should use.
3. **The stated uncertainty becomes a distribution.** U at k = 2 is a standard uncertainty
   of U/2, which is what a half-width at a sigma level means, so the laboratory's number
   reaches the margin sampler directly rather than being read once and forgotten.

Run it directly (``python examples/measured_shaft_from_certificate.py``);
:func:`screen_measured_shaft` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.dcc import parse_dcc
from anvilate.ingest import DraftSpec
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.tolerance import zone_limits
from anvilate.uncertainty import sample_margin
from anvilate.units import Quantity

CERTIFICATE = """<?xml version="1.0" encoding="UTF-8"?>
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
      <dcc:uniqueIdentifier>CAL-2026-04711</dcc:uniqueIdentifier>
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
        <dcc:name><dcc:content lang="en">Nordmetrik Kalibrierlabor</dcc:content></dcc:name>
        <dcc:location><dcc:city>Braunschweig</dcc:city></dcc:location>
      </dcc:contact>
      <dcc:cryptElectronicSeal>false</dcc:cryptElectronicSeal>
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
          </dcc:data>
        </dcc:result>
      </dcc:results>
    </dcc:measurementResult>
  </dcc:measurementResults>
</dcc:digitalCalibrationCertificate>
"""

NOMINAL = Quantity(magnitude=25.0, unit="mm")
SHAFT_ZONE = "h6"


def screen_measured_shaft() -> dict[str, object]:
    """Read the certificate, confirm the value, and screen it against the h6 zone."""
    certificate = parse_dcc(CERTIFICATE, document="CAL-2026-04711.dcc.xml")
    measured = certificate.labelled("shaft diameter")

    # Step 2: the measurement is a draft, and a draft is not an input.
    draft = DraftSpec(
        values=(measured.as_extracted("shaft_diameter"),), documents=("CAL-2026-04711.dcc.xml",)
    )
    blocked: str | None = None
    try:
        draft.release()
    except ValueError as exc:
        blocked = str(exc)
    released = draft.with_confirmation("shaft_diameter", by="R. Engineer")

    zone = zone_limits(SHAFT_ZONE, NOMINAL)
    upper = (NOMINAL.to("mm").magnitude) + zone.upper.to("mm").magnitude
    lower = (NOMINAL.to("mm").magnitude) + zone.lower.to("mm").magnitude
    diameter = released.release()["shaft_diameter"].to("mm").magnitude

    # Step 3: the certificate's own uncertainty, sampled. The margin is how far below the
    # upper limit the shaft sits, in micrometres; a margin below zero is out of tolerance.
    # `distribution_in` is not decoration: the sampler works on bare floats, so the unit has
    # to be settled while the value is still a Quantity. Reading `measured.distribution`
    # directly works only for a certificate that happens to state millimetres — the same
    # shaft in micrometres would be sampled a thousand times off against a millimetre limit,
    # with nothing in the numbers to show it.
    scatter = sample_margin(
        lambda values: (upper - values["shaft_diameter"]) * 1000.0,
        {"shaft_diameter": measured.distribution_in("mm")},
        required=0.0,
        seed=20260511,
    )
    entry = ScorecardEntry(
        name=f"shaft diameter within {SHAFT_ZONE}",
        status=CheckStatus.PASS if lower <= diameter <= upper else CheckStatus.FAIL,
        detail=(
            f"measured {diameter:.4f} mm against {lower:.4f}–{upper:.4f} mm "
            f"({(diameter - upper) * 1000:+.1f} µm on the upper limit)"
        ),
        reference=zone.source,
        uncertainty=scatter,
    )
    return {
        "certificate": certificate,
        "measured": measured,
        "blocked": blocked,
        "confirmed": released.confirmed()[0],
        "card": Scorecard(entries=(entry,)),
        "limits": (lower, upper),
    }


def main() -> None:
    result = screen_measured_shaft()
    certificate = result["certificate"]
    measured = result["measured"]
    entry = result["card"].entries[0]

    print("STEP 1 — the certificate")
    print(f"  {certificate.summary()}")
    print(f"  {measured}")
    print()
    print("STEP 2 — the measurement is a draft")
    print(f"  release refused: {result['blocked'].splitlines()[0]}")
    print(f"  after confirmation: {result['confirmed']}")
    print()
    print("STEP 3 — the verdict, and what the measurement can support")
    print(f"  {entry}")
    print(f"  {entry.uncertainty}")
    print(
        f"  the certificate's expanded uncertainty is ±1.2 µm at k=2 and the overshoot is "
        f"0.4 µm,\n  so the measurement is "
        f"{(1 - entry.uncertainty.shortfall_probability) * 100:.0f}% consistent with a shaft "
        "that is actually\n  inside the zone. The number fails. The measurement does not "
        "settle it."
    )


if __name__ == "__main__":
    main()
