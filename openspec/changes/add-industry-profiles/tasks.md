# Tasks: Industry profiles

## 1. Profile

- [x] 1.1 Profile schema (URN-identified): factor set, basis rules, required checks by
      item class, material needs, artifacts, drawing standard; source or practice label
      per rule (`anvilate.industry`, published as industry-profile 1.0.0; basis rules and
      material needs are not modelled yet)
- [x] 1.2 Item classes an item declares (flight box, primary structure, chassis part,
      patient-contacting, guard)
- [x] 1.3 Layering with override sources; relaxation reporting
      (on the resolved profile; carrying it onto margin rows waits on binding a profile
      to a margin report)

## 2. Shipped profiles

- [x] 2.1 General, held identical to today's cards by a regression over every example
- [x] 2.2 Spaceflight hardware, transport aircraft, automotive, medical device,
      industrial machinery, consumer product, each with values read from primary public
      documents and a list of rules awaiting user values

## 3. Card

- [x] 3.1 Required checks shown when untriggered; not evaluated or not available
- [ ] 3.2 Attribution of every profile-added rule; "what the profile changed" listing over
      the MCP tools and the CLI
      (attribution and the CLI listing, `anvilate check --profile`, are built; MCP is not)
- [ ] 3.3 Report header naming profile and version, with the screening-not-certification
      statement
- [x] 3.4 A docs page for industry profiles: choosing one, layering a company profile,
      what each shipped profile switches on
