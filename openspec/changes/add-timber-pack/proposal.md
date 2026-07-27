# Change: Timber pack (NDS member screening)

## Why

No open-source Python implementation of NDS timber design exists — AWC's free WoodWorks
is closed (https://awc.org/resources/woodworks-software-for-wood-design/), and searches
found nothing else. Yet NDS member design is classic spreadsheet territory with a huge US
audience: an adjustment-factor chain (load duration C_D, wet service C_M, temperature C_t,
beam stability C_L, size C_F, column stability C_P, …) multiplied onto reference design
values, then closed-form member checks. Reference design values are copyrighted
(NDS Supplement) — handled by Anvilate's user-supplied allowables doctrine, which turns
the copyright obstacle into a one-time data-entry step firms already perform.

## What Changes

- `discipline-packs` gains a timber pack requirement: the NDS adjustment-factor chain as
  a typed, itemized computation, member screens (bending, shear, compression with column
  stability, bearing, combined bending + axial), each citing its NDS section, with
  reference design values user-supplied with provenance.

## Impact

- Affected specs: `discipline-packs` (1 added requirement).
- Affected code (when implemented): new pack + analysis functions; worked-example anchors
  from published NDS example problems; US-customary default units (existing units
  capability already covers this).
