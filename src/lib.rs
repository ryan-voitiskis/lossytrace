//! Experimental, verdict-free measurements of possible prior lossy compression.

mod audio;
pub mod compression_trace;
mod error;
pub mod stft;

use serde::Serialize;
use std::path::Path;

pub use audio::SourceFacts;
pub use compression_trace::{
    measure_compression_trace, measure_compression_trace_with_samples, CompressionTraceFeatures,
    COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION,
};
pub use error::AnalysisError;

pub const EVIDENCE_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone)]
pub struct AnalysisConfig {
    pub frame_size: usize,
    pub hop_size: usize,
    pub enable_compression_trace_prototype: bool,
}

impl Default for AnalysisConfig {
    fn default() -> Self {
        Self {
            frame_size: 2_048,
            hop_size: 512,
            enable_compression_trace_prototype: false,
        }
    }
}

/// Compatibility result used by the migrated research harness.
#[derive(Debug, Clone, Serialize)]
pub struct AnalysisResult {
    #[serde(skip)]
    pub compression_trace_prototype: Option<CompressionTraceFeatures>,
}

/// Analyze decoded mono samples without making a provenance verdict.
pub fn analyze_audio(
    samples: &[f32],
    sample_rate: u32,
    config: AnalysisConfig,
) -> Result<AnalysisResult, AnalysisError> {
    let frames = stft::compute_stft(samples, config.frame_size, config.hop_size)?;
    let compression_trace_prototype = config
        .enable_compression_trace_prototype
        .then(|| {
            measure_compression_trace_with_samples(&frames, samples, sample_rate, config.hop_size)
        })
        .transpose()?;
    Ok(AnalysisResult {
        compression_trace_prototype,
    })
}

#[derive(Debug, Clone, Serialize)]
pub struct EvidenceReport {
    pub schema_version: u16,
    pub state: &'static str,
    pub public_verdict_enabled: bool,
    pub input_sha256: String,
    pub analyzed_sample_count: usize,
    pub analyzed_duration_seconds: f64,
    pub truncated_by_limit: bool,
    pub source_facts: SourceFacts,
    pub compression_trace: CompressionTraceFeatures,
}

/// Decode and measure an audio file, returning evidence rather than a verdict.
pub fn analyze_file(
    path: &Path,
    max_seconds: Option<f64>,
) -> Result<EvidenceReport, AnalysisError> {
    let input_sha256 = audio::sha256_file(path)?;
    let decoded = audio::decode(path, max_seconds)?;
    let result = analyze_audio(
        &decoded.samples,
        decoded.source_facts.sample_rate_hz,
        AnalysisConfig {
            enable_compression_trace_prototype: true,
            ..AnalysisConfig::default()
        },
    )?;
    let compression_trace = result
        .compression_trace_prototype
        .ok_or_else(|| AnalysisError::NumericalError("measurement was not produced".to_owned()))?;
    compression_trace.validate()?;
    Ok(EvidenceReport {
        schema_version: EVIDENCE_SCHEMA_VERSION,
        state: "experimental_measurements_only",
        public_verdict_enabled: false,
        input_sha256,
        analyzed_sample_count: decoded.samples.len(),
        analyzed_duration_seconds: decoded.samples.len() as f64
            / f64::from(decoded.source_facts.sample_rate_hz),
        truncated_by_limit: decoded.truncated_by_limit,
        source_facts: decoded.source_facts,
        compression_trace,
    })
}
