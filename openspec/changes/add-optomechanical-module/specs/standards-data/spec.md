# Standards Data Specification (delta)

## ADDED Requirements

### Requirement: Optical material property records

The materials database SHALL support optical material records carrying, in addition to the
mechanical and thermal properties every material record carries: refractive index at each
declared wavelength, the Abbe number with its defining wavelengths, the index change with
temperature over a declared range, the coefficient of thermal expansion over a declared
range, Knoop or equivalent hardness, and the stress-optic coefficient. Every property
SHALL carry its provenance and the wavelength and temperature range over which it is
declared valid, and a property consumed outside its declared range SHALL make the
consuming check report "not evaluated" naming the property and the range — never an
extrapolated value.

#### Scenario: Index is meaningless without its wavelength

- **WHEN** an optical material record declares a refractive index with no wavelength
- **THEN** the record is rejected naming the missing wavelength

#### Scenario: Range is enforced at the point of use

- **WHEN** a screen at a declared cold soak consumes a thermal coefficient whose declared
  range stops above that temperature
- **THEN** the screen reports "not evaluated" naming the property and its range

#### Scenario: Optical record satisfies the general contract too

- **WHEN** an optical material record is used by a mechanical screen
- **THEN** its elastic modulus, Poisson's ratio, and density resolve with provenance
  exactly as any other material record's do

### Requirement: Optical property data follows the existing licensing doctrine

Bundled optical property data SHALL come only from redistribution-clean sources, with the
per-record source identity and version stored. Vendor glass catalogs SHALL NOT be
redistributed in Anvilate releases; they SHALL be user-supplied or fetched to the user's
machine on first use with consent and checksum verification, cached locally, and recorded
in provenance, exactly as license-restricted section data already is.

#### Scenario: Public-domain source is bundled with its identity

- **WHEN** an optical material record originates from a public-domain or CC0 optical
  constants dataset
- **THEN** the record stores the dataset identity and version, and the record resolves
  offline

#### Scenario: Vendor catalog is not shipped

- **WHEN** a spec references a glass by a vendor designation whose catalog has not been
  supplied or fetched
- **THEN** the system asks for the governing properties or a local data file rather than
  recalling values, and records user provenance when they are supplied

#### Scenario: No property is recalled from model memory

- **WHEN** an optical property is required and no record or user declaration supplies it
- **THEN** the check reports "not evaluated" naming the property — the system MUST NOT
  substitute a remembered value
