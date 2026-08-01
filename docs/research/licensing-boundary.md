# Research licensing boundary

LossyTrace is licensed under `MIT OR Apache-2.0`, but not every artifact used
during detector research is suitable for redistribution under those terms.

The AAC quantization-error cycle used an independently written Rust probe
alongside a paper companion package whose notice permits personal or research
use and prohibits commercial use. The companion source was never a production
dependency. To avoid implying broader clearance, neither the companion source
nor the independent probe is included in the public repository or release
package. They remain in the separately checksummed external research archive
for provenance and potential legal review.

Licensed corpus audio is handled similarly: manifests, source terms,
fingerprints, generators, and aggregate results may be public, while audio
stays in the external corpus store under its source-specific terms.
