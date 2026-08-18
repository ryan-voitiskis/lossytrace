# Perceptual-degradation sparse/tonal descriptor freeze - 2026-08-18

**Status:** score-blind descriptor and abstention rules frozen and replayed on
synthetic fixtures only; candidate selection and audio access remain closed.

The time-occupancy rule divides a member into ten equal-duration blocks. A
block is active at or above 0.001 of the maximum block power. At most two
active blocks is sparse; at least eight is non-sparse; the middle region
abstains.

The spectral rule uses 1,024-frame periodic-Hann windows at a 512-frame hop.
Supported active frames report median spectral flatness and the median share
of power in the eight strongest non-DC, non-Nyquist bins. Tonal requires
flatness at most 0.1 and concentration at least 0.6. Non-tonal requires
flatness at least 0.5 and concentration at most 0.2. Intermediate or
low-support material abstains.

All three pre-existing synthetic structures pass: sparse-tonal overlap,
sparse non-tonal, and tonal non-sparse. These are implementation gates, not
source evidence or perceptual truth. A valid contrast still requires distinct
exact members and source groups. TinySOL may provide a tonal non-sparse
candidate, but its pitched-note metadata does not establish the required
sparse non-tonal route.

No actual or retained audio was read, no exact member selected, no trait
assigned, and no manifest or partition allocated. The next gate is a bounded
metadata-only exact-member selection audit before any request to open nominated
audio.
