# Source-derived expectations — corpus 0.2.0

This methodology corrects the old name-only label derivation. A transform's
name is insufficient evidence that its source implements the intended
operation. The generator constructs known source transformations;
`validate_fixtures.py` checks their relevant shape independently; syntax checks
and runtime engine observations remain separate obligations.

Expectations are fixed by reviewed source semantics before measurement. They
must not be changed because a measured fingerprint disagrees. A genuine source
annotation error requires a documented correction, corpus version/digest change,
and invalidation of previous comparable scores.

## Primary source transformations

| Transform | Source operation and preconditions | Typed expectation |
|---|---|---|
| `alpha-rename-local` | Bijective rename of bound seed parameters/locals, retaining operators/literals and uses | strong/strong equality |
| `pdg-only-formatting` | Add only comments and blank lines | strong/strong equality |
| `independent-reordering` | Swap two existing independent literal assignments; both feed the original computation; statement multiset unchanged | strong/strong equality |
| `pure-extract` | Move the original expression into a unique called helper, bind actuals/formals and use its returned value in the original sink | strong/strong equality; real purity certificate required |
| `fqn-move-package-rename` | Move a real file/package, update declarations plus separate consumer imports, retain complete source tree | strong/strong equality |
| `aliasing-changing-extract` | Mutate an aliased holder in a called helper, reload its changed value, then perform the original sink-relevant computation | strong/strong inequality; no pure certificate |
| `genuine-fix` | Remove the unsafe source→sink behavior using separate parameter binding, fixed destination, or non-object data decoding | finding removal, not inferred missing-hash success |

Each primary seed includes an untrusted argument and a declared sink API. Java
uses typed String concatenation or primitive bound arithmetic. Java byte-array
extraction moves scalar length arithmetic while preserving the caller's actual
array operation. Python source guards `type(input) is str` or `bytes` before
computation. String concatenation, built-in byte slicing, and scalar arithmetic
are meaningful computations, not identity wrappers. Helpers are private static
Java methods or closed-module Python functions. This finite fixture domain does
not justify certifying arbitrary dynamic operations, annotations, reflection,
unknown calls, callbacks, overloaded operators, or writable aliases.

Pure refactors preserve the operand sequence and supported normal/exceptional
behavior under the stated source preconditions. The closed modules do not
rebind built-ins/helper names or inspect frames. An engine must establish these
facts from its supported evidence or honestly mark its certificate unavailable;
the corpus must not declare the required runtime result passed in advance.

## Security fixes and removal semantics

Java SQL uses `PreparedStatement` with a separate `setString` binding; Python
SQL uses the declared SQLite question-mark binding API. Path and SSRF fixes
choose a fixed trusted destination independent of the untrusted argument.
Deserialization replaces Java `ObjectInputStream` with UTF-8 data decoding and
Python `pickle.loads` with JSON data parsing. These are vulnerability-removing
changes, not a claim of feature-identical application repairs.

All 50 primary fix cases are predeclared `finding_removal/absent`. For the 38
injection/path/SSRF fixes with retained sink API calls, separate named cases
compare the original and post-fix sink slices and require inequality. Those
comparisons concern candidate slices, not a claim that a vulnerability remains.
The 12 deserialization fixes remove the dangerous API and do not manufacture
after-locators/hashes. Absence requires a completed after-scan, relevant rule/
file coverage and lifecycle evidence; unknown/error/timeout/unsupported is not
absence. The R04 gate must not trust a producer's `matches_expectation` flag.

## Additional controls

For each of eight class/language bases, controls include the inverse inline
operation, genuine extraction combined with rename and relocation, and a
changed sink-relevant literal. Each language also has an argument-position
negative (only actual arguments change), a helper-return negative, and two
sink-specific cases for one multi-assignment helper reused at distinct call
sites. Both returned values must reconnect correctly; matching just one sink
cannot satisfy both cases. Intentional Java/Python parser failures keep the
old finding visible and never count as resolution or a structural mismatch.

## Source validation is not runtime acceptance

Checks reject unchanged source, unused helpers, unconnected helper returns,
non-permutations masquerading as reordering, comment-only moves, stale imports,
mutation disconnected from the sink, stale locators, invalid ordinary syntax,
unsafe paths, symlinks, source/metadata drift and undeclared inventory. Tests
also check exact type guards, two-call contexts and typed outcome separation.
They are finite source-shape checks, not a general semantic-equivalence proof.

No scanned source is imported or executed. Java syntax checking disables
annotation processing. A separate actual Joern parse/export/map campaign and
production fingerprint/detection/lifecycle evaluation must establish runtime
support and full acceptance. Retain failed/incomplete cases in denominators.

## Adding or correcting cases

1. State the submission/review requirement and concrete source semantics first.
2. Add meaningful before/after trees, exact per-side sink locators, typed outcome,
   preconditions and rationale. Add independent source/negative tests.
3. Preserve full required Java/Python coverage; do not trade it for an easier
   trivial helper or relabel a measured failure as removal.
4. Bump the pre-1.0 corpus version for source/contract changes; preserve the old
   lock and identify its immutable Git source revision. After v1.0, follow
   normal semantic-version compatibility rules.
5. Regenerate, check schema/current source hashes/exact inventory and syntax,
   then run the production campaign. Record the new digest, categories, primary
   and supplemental counts, diversity limits and invalidated previous scores.
