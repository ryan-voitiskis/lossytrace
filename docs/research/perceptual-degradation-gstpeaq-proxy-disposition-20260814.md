# GstPEAQ proxy score-blind disposition - 2026-08-14

**Status:** the frozen two-primary-family candidate is stopped at its declared
GstPEAQ legal/conformance gate. This is a public-record research disposition,
not legal advice, metric execution, a perceptual result, or a final negative
answer to the LossyTrace objective.

## Outcome

Public primary sources do not clear GstPEAQ for the frozen LossyTrace use:

- GstPEAQ's exact frozen README says it implements BS.1387-1 Basic and
  Advanced models but does not produce values within the allowed ITU
  tolerance.
- Its `COPYING` file supplies the GNU Library General Public License version 2
  for the software copyright. It does not document separate consent for the
  protected technology described by BS.1387.
- The in-force 2023 [`ITU-R BS.1387-2`](https://www.itu.int/rec/R-REC-BS.1387-2-202305-I/en)
  still says the technology is protected by international patents and that
  prior owner consent in the form of a licence is mandatory.
- The official [`ITU-R patent information page`](https://www.itu.int/en/ITU-R/study-groups/Pages/itu-r-patent-information.aspx)
  warns that its database is neither certified accurate nor complete and
  directs implementers to the declaring organizations or BR Secretariat to
  determine whether licences are required.
- A current database query for BS.1387 returns eight 1998 declarations under
  policy 2.2, attributed to Berkom, CCETT, CRC, Fraunhofer, IRT, KPN NV,
  OPTICOM, and TU Berlin. Policy 2.2 means willingness to negotiate on
  reasonable, non-discriminatory terms—not automatic permission.

The public record therefore does not establish current patent validity or
scope, expiry, a licence to LossyTrace, internal research permission, or binary
redistribution permission. The age of a declaration and the database word
`Granted` cannot responsibly fill those gaps.

## Australian experimental-use context

Section 119C of the current Australian
[`Patents Act 1990`](https://www.legislation.gov.au/C2004A04014/2024-10-14/2024-10-14/text/original/epub/OEBPS/document_1/document_1.html)
contains an exemption for acts done for experimental purposes relating to the
subject matter of an invention. The LossyTrace plan would use the proxy as a
measurement tool in experiments about audio degradation; the public record
does not establish that this is an experiment on the patented subject matter,
and it does not address any other jurisdiction. The exemption is therefore not
treated as self-executing clearance. Fact-specific qualified legal review would
still be required.

## Frozen candidate disposition

The current contract expressly stops a candidate when the proxy
legal/conformance boundary is unresolved. That stop condition is now triggered:

- legal gate: failed to clear from public evidence;
- conformance gate: failed because upstream declares values outside ITU
  tolerance;
- build and execution: remain unauthorized;
- score access: remains closed;
- current two-family candidate: may not advance;
- no-reference work: remains ineligible; and
- final research recommendation: remains unfrozen.

Nonconformance does not prove every proxy output is useless. It means the tool
cannot be represented as a conforming PEAQ implementation and cannot silently
enter the preregistered primary evidence stack. Similarly, this candidate-level
stop is not a rigorous full-objective negative result: no adequate human
calibration experiment has yet rejected perceptual estimation.

## Successor choices

Exactly three honest paths remain:

1. **Qualified legal clearance:** obtain fact-specific advice and any required
   rights-holder consent for exact internal research and redistribution
   boundaries.
2. **Preregister a simpler successor:** retire the proxy and freeze a new
   ViSQOL-only full-reference candidate, including revised added-value and
   artifact-profile limitations, before any retained or human metric outcomes
   are opened.
3. **Reject the current candidate:** end this two-family candidate without
   replacing it. This does not itself answer whether a different
   full-reference estimator could work.

No option is selected here. Rights-holder contact, legal spend, family
replacement, build, execution, and score access all require a separate
responsible-human decision. Silent replacement is forbidden.

## Immutable public observations

- GstPEAQ README: 2,169 bytes, SHA-256
  `bf2a8afc21a8cb27b1270aff34525abdf67d01b85e3a85987f34408377ab8ce1`.
- GstPEAQ COPYING: 25,265 bytes, SHA-256
  `94b03f1a60a7fd5007149530626a895a6ef5a8b9342abfd56860c5f3956f5d23`.
- BS.1387-2 English PDF: 2,065,318 bytes, SHA-256
  `ffe3ce073c483fb29c573a3158aa73c6536856468a9539e8b292ef9a0389f135`.
- BS.1387 patent-query response: 18,370 bytes, SHA-256
  `018a0e2e7953e86a82004de271f42be1b3a5c5f24451e893dc793aa154545fe7`.

All four were streamed for hashing and not retained. No GstPEAQ source,
binary, audio, metric result, listening score, or sealed evidence entered the
research store.

Machine-readable artifacts:

- [`public legal observation`](../../research/toolchains/evidence/perceptual-degradation-gstpeaq-public-legal-observation-20260814-001.json)
- [`score-blind disposition`](../../benchmarks/perceptual-degradation-v1/gstpeaq-proxy-score-blind-disposition.json)
- [`validator`](../../scripts/validate-perceptual-degradation-gstpeaq-proxy-disposition.py)
