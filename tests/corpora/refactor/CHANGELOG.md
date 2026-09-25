# Corpus version history

## 0.2.0 — source validity and typed evidence correction (#361, #362)

This is a breaking pre-1.0 fixture/contract correction, not a certified runtime
result. All 350 primary source pairs change. Original flat files are replaced
by proper Java package/Python module trees and importing consumers. Reordering,
pure extraction, relocation and aliasing now perform actual sink-relevant
operations; invalid Java class-body helper placement is removed.

Schema 2 introduces exact case identity, per-side locators/source digests,
expected source/purity conditions, and separate structural/removal/failure
semantics. Primary inventory remains 50 × seven = 350; its legacy label split
remains 250 stay / 100 flip. Another 38 retained-sink fix comparisons and 34
named controls bring the total to 422: 270 equality, 100 inequality, 50 removal,
two intentional failures. Eight repeated primary topologies remain eight; no
new independent primary-seed diversity is claimed.

New corpus digest:
`sha256:bd1621a71c945436a5f040e65f8ab9cda39af145e96c2cbc44f8886221a2fef9`.
All scores measured on 0.1.0 are non-comparable with this revision. Source
syntax tests and generator tests are not production Joern/fingerprint/lifecycle
acceptance. Future campaign evidence must record this exact lock and revision.

## 0.1.0 — historical only

The old lock remains byte-for-byte under `history/0.1.0/` with original source
at Git revision `940d440cb99e23131d28ee5bbb1655ea29d46a58`. The old corpus digest
was `sha256:0750651a2d915dbdb672993b2a41d644f893f5e7407d260e5e28054b3f4e50f6`.
Its superficial transforms, Java failures and missing after-correspondence
invalidate using its reported results as corrected G0 evidence. Recovery of old
artifacts does not constitute new execution.
