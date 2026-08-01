//! Experimental measurements for compression-like spectral traces.
//!
//! This module deliberately measures signal properties without classifying
//! audio as lossy-derived or healthy. The feature definition remains at
//! version `0` until the private real-audio benchmark freezes a calibrated
//! contract.

use crate::error::AnalysisError;
use rustdct::mdct::{window_fn, Mdct};
use rustdct::DctPlanner;

/// Prototype feature version.
///
/// Version `0` is reserved for uncalibrated measurements and must not be
/// persisted as a stable cache contract or interpreted as a user verdict.
pub const COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION: u16 = 0;

const ABSOLUTE_FRAME_POWER_FLOOR: f64 = 1.0e-12;
const RELATIVE_FRAME_POWER_FLOOR: f64 = 1.0e-6;
const RELATIVE_ACTIVE_BIN_POWER_FLOOR: f64 = 1.0e-5;
const MIN_ACTIVE_BIN_FRACTION: f64 = 0.02;
const MIN_SUPPORTED_FRAMES: usize = 32;
const MIN_HIGH_BAND_SUPPORTED_FRAMES: usize = 16;
const MIN_MEASURABLE_NYQUIST_HZ: f64 = 20_000.0;
const MIN_EDGE_DROP_DB: f64 = 6.0;
const HOLE_DEFICIT_RATIO: f64 = 1.0e-3;
const RUPTURE_BASELINE_DB: f64 = 6.0;
const RUPTURE_NORMALIZATION_DB: f64 = 30.0;
const LOG_BAND_COUNT: usize = 32;
const ALIGNMENT_COARSE_PHASES: usize = 32;
const ALIGNMENT_MAX_BLOCKS_PER_PHASE: usize = 12;
const ALIGNMENT_SMALL_COEFFICIENT_THRESHOLD: f32 = 1.0e-4;

/// Explainable, verdict-free measurements from the shared magnitude STFT.
///
/// Optional values are absent when the input lacks enough usable support.
/// Ratio and score fields are constrained to `[0, 1]`; all other floating
/// values are finite and non-negative.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct CompressionTraceFeatures {
    /// Measurement-definition version. `0` means experimental and unfrozen.
    pub feature_version: u16,
    /// Number of STFT frames supplied to the measurement.
    pub analyzed_frame_count: u32,
    /// Number of energetic, non-sparse frames used by the measurement.
    pub active_frame_count: u32,
    /// Duration represented by active frame hops.
    pub active_duration_seconds: f32,
    /// Active frames with enough upper-mid-band support to search for an edge.
    pub high_band_supported_frame_count: u32,
    /// Median fraction of bins above the per-frame relative power floor.
    pub median_active_bin_fraction: Option<f32>,
    /// Robust frequency of a repeated downward high-frequency step.
    pub spectral_edge_hz: Option<f32>,
    /// Median local power drop at the repeated edge.
    pub spectral_edge_drop_db: Option<f32>,
    /// Fraction of high-band-supported frames agreeing on the edge.
    pub spectral_edge_persistence: Option<f32>,
    /// Interquartile spread of agreeing frame-level edge frequencies.
    pub spectral_edge_spread_hz: Option<f32>,
    /// Density of deep local deficits with energetic frequency neighbours.
    pub spectral_hole_ratio: Option<f32>,
    /// Density of those deficits that are isolated in frequency.
    pub isolated_hole_ratio: Option<f32>,
    /// Robust adjacent-band discontinuity score.
    pub band_rupture_score: Option<f32>,
    /// Phase contrast in small MDCT coefficients across candidate frame grids.
    pub transform_alignment_score: Option<f32>,
    /// Candidate MDCT half-window size that produced the strongest contrast.
    pub transform_alignment_block_samples: Option<u32>,
    /// Encoder-grid phase associated with the strongest alignment contrast.
    pub transform_alignment_phase_samples: Option<u32>,
    /// Small-coefficient fraction at the strongest candidate phase.
    pub transform_alignment_small_coefficient_fraction: Option<f32>,
}

impl CompressionTraceFeatures {
    /// Validate the public numeric contract.
    pub fn validate(&self) -> Result<(), AnalysisError> {
        if self.active_frame_count > self.analyzed_frame_count {
            return Err(AnalysisError::NumericalError(format!(
                "active_frame_count {} exceeds analyzed_frame_count {}",
                self.active_frame_count, self.analyzed_frame_count
            )));
        }
        if self.high_band_supported_frame_count > self.active_frame_count {
            return Err(AnalysisError::NumericalError(format!(
                "high_band_supported_frame_count {} exceeds active_frame_count {}",
                self.high_band_supported_frame_count, self.active_frame_count
            )));
        }
        validate_non_negative("active_duration_seconds", self.active_duration_seconds)?;
        for (name, value) in [
            (
                "median_active_bin_fraction",
                self.median_active_bin_fraction,
            ),
            ("spectral_edge_persistence", self.spectral_edge_persistence),
            ("spectral_hole_ratio", self.spectral_hole_ratio),
            ("isolated_hole_ratio", self.isolated_hole_ratio),
            ("band_rupture_score", self.band_rupture_score),
            ("transform_alignment_score", self.transform_alignment_score),
            (
                "transform_alignment_small_coefficient_fraction",
                self.transform_alignment_small_coefficient_fraction,
            ),
        ] {
            validate_ratio(name, value)?;
        }
        for (name, value) in [
            ("spectral_edge_hz", self.spectral_edge_hz),
            ("spectral_edge_drop_db", self.spectral_edge_drop_db),
            ("spectral_edge_spread_hz", self.spectral_edge_spread_hz),
        ] {
            if let Some(value) = value {
                validate_non_negative(name, value)?;
            }
        }
        let edge_fields = [
            self.spectral_edge_hz.is_some(),
            self.spectral_edge_drop_db.is_some(),
            self.spectral_edge_persistence.is_some(),
            self.spectral_edge_spread_hz.is_some(),
        ];
        if edge_fields.iter().any(|present| *present) && !edge_fields.iter().all(|present| *present)
        {
            return Err(AnalysisError::NumericalError(
                "spectral edge fields must be either all present or all absent".to_string(),
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy)]
struct FrameEdge {
    frequency_hz: f64,
    drop_db: f64,
}

#[derive(Debug, Clone, Copy)]
struct EdgeSummary {
    frequency_hz: f64,
    drop_db: f64,
    persistence: f64,
    spread_hz: f64,
}

#[derive(Debug, Clone, Copy)]
struct BandRange {
    start: usize,
    end: usize,
    center_hz: f64,
}

#[derive(Debug, Clone, Copy)]
struct TransformAlignment {
    score: f64,
    block_samples: usize,
    phase_samples: usize,
    small_coefficient_fraction: f64,
}

#[derive(Debug, Clone, Copy)]
struct HoleCounts {
    supported_tiles: u64,
    holes: u64,
    isolated_holes: u64,
}

/// Measure experimental compression-trace features from an existing STFT.
///
/// The function borrows the spectrogram, performs no FFT, and retains only
/// per-frame/per-bin scratch state. Candidate constants are intentionally not
/// a policy and must be calibrated with the private benchmark before this
/// output is cached or shown as a verdict.
pub fn measure_compression_trace(
    magnitude_spec_frames: &[Vec<f32>],
    sample_rate: u32,
    hop_size: usize,
) -> Result<CompressionTraceFeatures, AnalysisError> {
    measure_compression_trace_with_samples(magnitude_spec_frames, &[], sample_rate, hop_size)
}

/// Measure compression traces using the shared STFT and optional time samples.
///
/// The raw samples are used only for the experimental transform-grid family.
/// Passing an empty slice preserves the STFT-only behavior for focused tests.
pub fn measure_compression_trace_with_samples(
    magnitude_spec_frames: &[Vec<f32>],
    samples: &[f32],
    sample_rate: u32,
    hop_size: usize,
) -> Result<CompressionTraceFeatures, AnalysisError> {
    if sample_rate == 0 {
        return Err(AnalysisError::InvalidInput(
            "compression trace sample_rate must be greater than zero".to_string(),
        ));
    }
    if hop_size == 0 {
        return Err(AnalysisError::InvalidInput(
            "compression trace hop_size must be greater than zero".to_string(),
        ));
    }

    let analyzed_frame_count = exact_u32("analyzed_frame_count", magnitude_spec_frames.len())?;
    let Some(first_frame) = magnitude_spec_frames.first() else {
        return Ok(empty_features(analyzed_frame_count));
    };
    let n_bins = first_frame.len();
    if n_bins < 8 {
        validate_frames(magnitude_spec_frames, n_bins)?;
        return Ok(empty_features(analyzed_frame_count));
    }
    validate_frames(magnitude_spec_frames, n_bins)?;

    let fft_size = n_bins
        .checked_sub(1)
        .and_then(|half| half.checked_mul(2))
        .ok_or_else(|| {
            AnalysisError::InvalidInput(
                "compression trace FFT size cannot be represented".to_string(),
            )
        })?;
    if fft_size == 0 {
        return Ok(empty_features(analyzed_frame_count));
    }
    let bin_hz = f64::from(sample_rate) / fft_size as f64;
    let nyquist_hz = f64::from(sample_rate) / 2.0;

    let max_frame_power = magnitude_spec_frames
        .iter()
        .map(|frame| frame_power(frame))
        .fold(0.0_f64, f64::max);
    let frame_power_floor =
        ABSOLUTE_FRAME_POWER_FLOOR.max(max_frame_power * RELATIVE_FRAME_POWER_FLOOR);

    let mut active_indices = Vec::new();
    let mut active_bin_fractions = Vec::new();
    for (index, frame) in magnitude_spec_frames.iter().enumerate() {
        let total_power = frame_power(frame);
        if total_power < frame_power_floor {
            continue;
        }
        let peak_power = frame
            .iter()
            .map(|magnitude| f64::from(*magnitude).powi(2))
            .fold(0.0_f64, f64::max);
        if peak_power <= 0.0 {
            continue;
        }
        let active_floor =
            (peak_power * RELATIVE_ACTIVE_BIN_POWER_FLOOR).max(ABSOLUTE_FRAME_POWER_FLOOR);
        let active_bins = frame
            .iter()
            .filter(|magnitude| f64::from(**magnitude).powi(2) >= active_floor)
            .count();
        let active_fraction = active_bins as f64 / n_bins as f64;
        if active_fraction < MIN_ACTIVE_BIN_FRACTION {
            continue;
        }
        active_indices.push(index);
        active_bin_fractions.push(active_fraction);
    }

    let active_frame_count = exact_u32("active_frame_count", active_indices.len())?;
    let active_duration_seconds =
        (active_indices.len() as f64 * hop_size as f64 / f64::from(sample_rate)) as f32;
    let median_active_bin_fraction = median(&mut active_bin_fractions).map(|value| value as f32);

    if active_indices.len() < MIN_SUPPORTED_FRAMES {
        let features = CompressionTraceFeatures {
            feature_version: COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION,
            analyzed_frame_count,
            active_frame_count,
            active_duration_seconds,
            high_band_supported_frame_count: 0,
            median_active_bin_fraction,
            spectral_edge_hz: None,
            spectral_edge_drop_db: None,
            spectral_edge_persistence: None,
            spectral_edge_spread_hz: None,
            spectral_hole_ratio: None,
            isolated_hole_ratio: None,
            band_rupture_score: None,
            transform_alignment_score: None,
            transform_alignment_block_samples: None,
            transform_alignment_phase_samples: None,
            transform_alignment_small_coefficient_fraction: None,
        };
        features.validate()?;
        return Ok(features);
    }

    let high_band_measurable = nyquist_hz >= MIN_MEASURABLE_NYQUIST_HZ;
    let edge_search = if high_band_measurable {
        edge_search_bins(n_bins, bin_hz, nyquist_hz)
    } else {
        None
    };
    let mut high_band_supported_indices = Vec::new();
    let mut frame_edges = Vec::new();
    if let Some((search_start, search_end, window_bins)) = edge_search {
        for index in active_indices.iter().copied() {
            let frame = &magnitude_spec_frames[index];
            if !has_high_band_support(frame, bin_hz, nyquist_hz) {
                continue;
            }
            high_band_supported_indices.push(index);
            if let Some(edge) = frame_edge(frame, bin_hz, search_start, search_end, window_bins) {
                frame_edges.push(edge);
            }
        }
    }
    let high_band_supported_frame_count = exact_u32(
        "high_band_supported_frame_count",
        high_band_supported_indices.len(),
    )?;
    let edge_summary = if high_band_supported_indices.len() >= MIN_HIGH_BAND_SUPPORTED_FRAMES {
        summarize_edges(&mut frame_edges, high_band_supported_indices.len(), bin_hz)
    } else {
        None
    };

    let (spectral_hole_ratio, isolated_hole_ratio) =
        measure_holes(magnitude_spec_frames, &active_indices, bin_hz, nyquist_hz);
    let band_rupture_score = measure_band_ruptures(
        magnitude_spec_frames,
        &active_indices,
        log_band_ranges(n_bins, bin_hz, nyquist_hz),
        edge_summary.map(|edge| edge.frequency_hz),
    );
    let transform_alignment = measure_transform_alignment(samples);

    let features = CompressionTraceFeatures {
        feature_version: COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION,
        analyzed_frame_count,
        active_frame_count,
        active_duration_seconds,
        high_band_supported_frame_count,
        median_active_bin_fraction,
        spectral_edge_hz: edge_summary.map(|edge| edge.frequency_hz as f32),
        spectral_edge_drop_db: edge_summary.map(|edge| edge.drop_db as f32),
        spectral_edge_persistence: edge_summary.map(|edge| edge.persistence as f32),
        spectral_edge_spread_hz: edge_summary.map(|edge| edge.spread_hz as f32),
        spectral_hole_ratio,
        isolated_hole_ratio,
        band_rupture_score,
        transform_alignment_score: transform_alignment.map(|value| value.score as f32),
        transform_alignment_block_samples: transform_alignment
            .and_then(|value| u32::try_from(value.block_samples).ok()),
        transform_alignment_phase_samples: transform_alignment
            .and_then(|value| u32::try_from(value.phase_samples).ok()),
        transform_alignment_small_coefficient_fraction: transform_alignment
            .map(|value| value.small_coefficient_fraction as f32),
    };
    features.validate()?;
    Ok(features)
}

fn empty_features(analyzed_frame_count: u32) -> CompressionTraceFeatures {
    CompressionTraceFeatures {
        feature_version: COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION,
        analyzed_frame_count,
        active_frame_count: 0,
        active_duration_seconds: 0.0,
        high_band_supported_frame_count: 0,
        median_active_bin_fraction: None,
        spectral_edge_hz: None,
        spectral_edge_drop_db: None,
        spectral_edge_persistence: None,
        spectral_edge_spread_hz: None,
        spectral_hole_ratio: None,
        isolated_hole_ratio: None,
        band_rupture_score: None,
        transform_alignment_score: None,
        transform_alignment_block_samples: None,
        transform_alignment_phase_samples: None,
        transform_alignment_small_coefficient_fraction: None,
    }
}

fn validate_frames(
    magnitude_spec_frames: &[Vec<f32>],
    expected_bins: usize,
) -> Result<(), AnalysisError> {
    for (frame_index, frame) in magnitude_spec_frames.iter().enumerate() {
        if frame.len() != expected_bins {
            return Err(AnalysisError::InvalidInput(format!(
                "compression trace frame {frame_index} has {} bins; expected {expected_bins}",
                frame.len()
            )));
        }
        for (bin_index, magnitude) in frame.iter().enumerate() {
            if !magnitude.is_finite() || *magnitude < 0.0 {
                return Err(AnalysisError::InvalidInput(format!(
                    "compression trace frame {frame_index} bin {bin_index} must be finite and non-negative, got {magnitude}"
                )));
            }
        }
    }
    Ok(())
}

fn frame_power(frame: &[f32]) -> f64 {
    frame
        .iter()
        .map(|magnitude| f64::from(*magnitude).powi(2))
        .sum()
}

fn has_high_band_support(frame: &[f32], bin_hz: f64, nyquist_hz: f64) -> bool {
    let anchor_start = hz_to_bin(nyquist_hz * 0.35, bin_hz, frame.len());
    let anchor_end = hz_to_bin(nyquist_hz * 0.55, bin_hz, frame.len());
    if anchor_end <= anchor_start + 4 {
        return false;
    }
    let total = frame_power(frame);
    if total <= 0.0 {
        return false;
    }
    let anchor: f64 = frame[anchor_start..anchor_end]
        .iter()
        .map(|magnitude| f64::from(*magnitude).powi(2))
        .sum();
    anchor / total >= 1.0e-4
}

fn edge_search_bins(n_bins: usize, bin_hz: f64, nyquist_hz: f64) -> Option<(usize, usize, usize)> {
    let search_start_hz = 10_000.0_f64.max(nyquist_hz * 0.50);
    let search_end_hz = (nyquist_hz * 0.94).min(21_000.0);
    let window_hz = 300.0_f64.max(nyquist_hz * 0.015);
    let window_bins = ((window_hz / bin_hz).round() as usize).max(3);
    let search_start = hz_to_bin(search_start_hz, bin_hz, n_bins).max(window_bins);
    let search_end =
        hz_to_bin(search_end_hz, bin_hz, n_bins).min(n_bins.saturating_sub(window_bins));
    (search_end > search_start).then_some((search_start, search_end, window_bins))
}

fn frame_edge(
    frame: &[f32],
    bin_hz: f64,
    search_start: usize,
    search_end: usize,
    window_bins: usize,
) -> Option<FrameEdge> {
    let mut prefix = Vec::with_capacity(frame.len() + 1);
    prefix.push(0.0_f64);
    for magnitude in frame {
        let next = prefix.last().copied().unwrap_or(0.0) + f64::from(*magnitude).powi(2);
        prefix.push(next);
    }
    let peak_power = frame
        .iter()
        .map(|magnitude| f64::from(*magnitude).powi(2))
        .fold(0.0_f64, f64::max);
    let floor = (peak_power * 1.0e-12).max(1.0e-24);
    let mut best: Option<FrameEdge> = None;
    for bin in search_start..search_end {
        let below = range_mean(&prefix, bin - window_bins, bin);
        let above = range_mean(&prefix, bin, bin + window_bins);
        if below < peak_power * RELATIVE_ACTIVE_BIN_POWER_FLOOR {
            continue;
        }
        let drop_db = 10.0 * ((below + floor) / (above + floor)).log10();
        if drop_db < MIN_EDGE_DROP_DB {
            continue;
        }
        if best.is_none_or(|edge| drop_db > edge.drop_db) {
            best = Some(FrameEdge {
                frequency_hz: bin as f64 * bin_hz,
                drop_db,
            });
        }
    }
    best
}

fn summarize_edges(
    frame_edges: &mut [FrameEdge],
    supported_frame_count: usize,
    bin_hz: f64,
) -> Option<EdgeSummary> {
    if frame_edges.is_empty() || supported_frame_count == 0 {
        return None;
    }
    frame_edges.sort_by(|left, right| left.frequency_hz.total_cmp(&right.frequency_hz));
    let center = percentile_sorted_by(frame_edges, 0.5, |edge| edge.frequency_hz)?;
    let tolerance_hz = (bin_hz * 3.0).max(300.0);
    let mut agreeing: Vec<FrameEdge> = frame_edges
        .iter()
        .copied()
        .filter(|edge| (edge.frequency_hz - center).abs() <= tolerance_hz)
        .collect();
    if agreeing.is_empty() {
        return None;
    }
    agreeing.sort_by(|left, right| left.frequency_hz.total_cmp(&right.frequency_hz));
    let frequency_hz = percentile_sorted_by(&agreeing, 0.5, |edge| edge.frequency_hz)?;
    let q1 = percentile_sorted_by(&agreeing, 0.25, |edge| edge.frequency_hz)?;
    let q3 = percentile_sorted_by(&agreeing, 0.75, |edge| edge.frequency_hz)?;
    let mut drops: Vec<f64> = agreeing.iter().map(|edge| edge.drop_db).collect();
    let drop_db = median(&mut drops)?;
    Some(EdgeSummary {
        frequency_hz,
        drop_db,
        persistence: (agreeing.len() as f64 / supported_frame_count as f64).clamp(0.0, 1.0),
        spread_hz: (q3 - q1).max(0.0),
    })
}

fn measure_holes(
    magnitude_spec_frames: &[Vec<f32>],
    active_indices: &[usize],
    bin_hz: f64,
    nyquist_hz: f64,
) -> (Option<f32>, Option<f32>) {
    if active_indices.len() < MIN_SUPPORTED_FRAMES {
        return (None, None);
    }
    let counts = hole_counts(magnitude_spec_frames, active_indices, bin_hz, nyquist_hz);
    if counts.supported_tiles == 0 {
        return (None, None);
    }
    (
        Some((counts.holes as f64 / counts.supported_tiles as f64).clamp(0.0, 1.0) as f32),
        Some((counts.isolated_holes as f64 / counts.supported_tiles as f64).clamp(0.0, 1.0) as f32),
    )
}

fn hole_counts(
    magnitude_spec_frames: &[Vec<f32>],
    frame_indices: &[usize],
    bin_hz: f64,
    nyquist_hz: f64,
) -> HoleCounts {
    let n_bins = magnitude_spec_frames[0].len();
    let radius = 2;
    let start = hz_to_bin(500.0, bin_hz, n_bins).max(radius);
    let end = hz_to_bin((nyquist_hz * 0.90).min(20_000.0), bin_hz, n_bins).min(n_bins - radius);
    if end <= start {
        return HoleCounts {
            supported_tiles: 0,
            holes: 0,
            isolated_holes: 0,
        };
    }

    let mut counts = HoleCounts {
        supported_tiles: 0,
        holes: 0,
        isolated_holes: 0,
    };
    let mut hole_flags = vec![false; n_bins];
    for index in frame_indices.iter().copied() {
        let frame = &magnitude_spec_frames[index];
        hole_flags.fill(false);
        let peak_power = frame
            .iter()
            .map(|magnitude| f64::from(*magnitude).powi(2))
            .fold(0.0_f64, f64::max);
        let support_floor = peak_power * RELATIVE_ACTIVE_BIN_POWER_FLOOR;
        for bin in start..end {
            let left = frame[bin - radius..bin]
                .iter()
                .map(|magnitude| f64::from(*magnitude).powi(2))
                .sum::<f64>()
                / radius as f64;
            let right = frame[bin + 1..=bin + radius]
                .iter()
                .map(|magnitude| f64::from(*magnitude).powi(2))
                .sum::<f64>()
                / radius as f64;
            let expected = left.min(right);
            if expected < support_floor {
                continue;
            }
            counts.supported_tiles += 1;
            let power = f64::from(frame[bin]).powi(2);
            if power <= expected * HOLE_DEFICIT_RATIO {
                counts.holes += 1;
                hole_flags[bin] = true;
            }
        }
        for bin in start..end {
            if hole_flags[bin] && !hole_flags[bin - 1] && !hole_flags[bin + 1] {
                counts.isolated_holes += 1;
            }
        }
    }
    counts
}

fn log_band_ranges(n_bins: usize, bin_hz: f64, nyquist_hz: f64) -> Vec<BandRange> {
    let lower_hz = 250.0;
    let upper_hz = (nyquist_hz * 0.90).min(20_000.0);
    if upper_hz <= lower_hz {
        return Vec::new();
    }
    let ratio = (upper_hz / lower_hz).powf(1.0 / LOG_BAND_COUNT as f64);
    let mut ranges = Vec::with_capacity(LOG_BAND_COUNT);
    for band in 0..LOG_BAND_COUNT {
        let low = lower_hz * ratio.powi(band as i32);
        let high = lower_hz * ratio.powi((band + 1) as i32);
        let start = hz_to_bin(low, bin_hz, n_bins);
        let end = hz_to_bin(high, bin_hz, n_bins).max(start + 1).min(n_bins);
        if start < end {
            ranges.push(BandRange {
                start,
                end,
                center_hz: (low * high).sqrt(),
            });
        }
    }
    ranges
}

fn measure_band_ruptures(
    magnitude_spec_frames: &[Vec<f32>],
    active_indices: &[usize],
    bands: Vec<BandRange>,
    edge_hz: Option<f64>,
) -> Option<f32> {
    if active_indices.len() < MIN_SUPPORTED_FRAMES || bands.len() < 5 {
        return None;
    }
    let mut residuals_by_band = vec![Vec::with_capacity(active_indices.len()); bands.len()];
    let mut band_db = vec![0.0_f64; bands.len()];
    for index in active_indices.iter().copied() {
        let frame = &magnitude_spec_frames[index];
        let peak_power = frame
            .iter()
            .map(|magnitude| f64::from(*magnitude).powi(2))
            .fold(0.0_f64, f64::max);
        let floor = (peak_power * 1.0e-12).max(1.0e-24);
        for (band_index, band) in bands.iter().enumerate() {
            let mean_power = frame[band.start..band.end]
                .iter()
                .map(|magnitude| f64::from(*magnitude).powi(2))
                .sum::<f64>()
                / (band.end - band.start) as f64;
            band_db[band_index] = 10.0 * (mean_power + floor).log10();
        }
        for band_index in 1..bands.len() - 1 {
            if edge_hz.is_some_and(|edge| (bands[band_index].center_hz - edge).abs() <= 800.0) {
                continue;
            }
            let expected = (band_db[band_index - 1] + band_db[band_index + 1]) / 2.0;
            let residual = (band_db[band_index] - expected).abs();
            residuals_by_band[band_index].push(residual);
        }
    }
    let mut persistent_residuals: Vec<f64> = residuals_by_band
        .iter_mut()
        .filter_map(|residuals| median(residuals))
        .map(|residual| {
            ((residual - RUPTURE_BASELINE_DB) / RUPTURE_NORMALIZATION_DB).clamp(0.0, 1.0)
        })
        .collect();
    persistent_residuals.sort_by(f64::total_cmp);
    let strongest: Vec<f64> = persistent_residuals.iter().rev().take(3).copied().collect();
    (!strongest.is_empty()).then(|| (strongest.iter().sum::<f64>() / strongest.len() as f64) as f32)
}

fn measure_transform_alignment(samples: &[f32]) -> Option<TransformAlignment> {
    const LONG_BLOCK_SAMPLES: usize = 1024;

    if samples.len() < LONG_BLOCK_SAMPLES * 8 || samples.iter().all(|sample| *sample == 0.0) {
        return None;
    }
    // DctPlanner caches MDCT plans by length, not by window function. Use
    // separate planners so equal-length sine and Vorbis transforms do not
    // accidentally share the first window planned.
    let mut sine_planner = DctPlanner::new();
    let sine_mdct = sine_planner.plan_mdct(LONG_BLOCK_SAMPLES, window_fn::mp3);
    let mut vorbis_planner = DctPlanner::new();
    let vorbis_mdct = vorbis_planner.plan_mdct(LONG_BLOCK_SAMPLES, window_fn::vorbis);
    [
        transform_alignment_for_mdct(samples, LONG_BLOCK_SAMPLES, sine_mdct.as_ref()),
        transform_alignment_for_mdct(samples, LONG_BLOCK_SAMPLES, vorbis_mdct.as_ref()),
    ]
    .into_iter()
    .flatten()
    .max_by(|left, right| left.score.total_cmp(&right.score))
}

fn transform_alignment_for_mdct(
    samples: &[f32],
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
) -> Option<TransformAlignment> {
    let coarse_step = (block_samples / ALIGNMENT_COARSE_PHASES).max(1);
    let mut coarse = Vec::with_capacity(ALIGNMENT_COARSE_PHASES);
    for phase in (0..block_samples).step_by(coarse_step) {
        if let Some(fraction) = alignment_phase_fraction(samples, block_samples, phase, mdct) {
            coarse.push((phase, fraction));
        }
    }
    let coarse_best = coarse
        .iter()
        .max_by(|left, right| left.1.total_cmp(&right.1))
        .copied()?;

    let mut refined = Vec::with_capacity(coarse_step * 2 + 1);
    for delta in -(coarse_step as isize)..=coarse_step as isize {
        let phase = (coarse_best.0 as isize + delta).rem_euclid(block_samples as isize) as usize;
        if let Some(fraction) = alignment_phase_fraction(samples, block_samples, phase, mdct) {
            refined.push((phase, fraction));
        }
    }
    let best = refined
        .iter()
        .max_by(|left, right| left.1.total_cmp(&right.1))
        .copied()?;
    let mut background: Vec<f64> = coarse
        .into_iter()
        .filter(|(phase, _)| {
            let direct = phase.abs_diff(best.0);
            direct.min(block_samples - direct) > coarse_step
        })
        .map(|(_, fraction)| fraction)
        .collect();
    let background_median = median(&mut background)?;
    let score =
        ((best.1 - background_median) / (1.0 - background_median).max(1.0e-9)).clamp(0.0, 1.0);
    Some(TransformAlignment {
        score,
        block_samples,
        phase_samples: best.0,
        small_coefficient_fraction: best.1,
    })
}

fn alignment_phase_fraction(
    samples: &[f32],
    block_samples: usize,
    phase: usize,
    mdct: &dyn Mdct<f32>,
) -> Option<f64> {
    let input_samples = block_samples.checked_mul(2)?;
    if samples.len() < phase.checked_add(input_samples)? {
        return None;
    }
    let available_blocks = (samples.len() - phase - input_samples) / block_samples + 1;
    let block_stride = (available_blocks / ALIGNMENT_MAX_BLOCKS_PER_PHASE).max(1);
    let mut output = vec![0.0_f32; block_samples];
    let mut scratch = vec![0.0_f32; mdct.get_scratch_len()];
    let mut fractions = Vec::with_capacity(ALIGNMENT_MAX_BLOCKS_PER_PHASE);
    for block_index in (0..available_blocks)
        .step_by(block_stride)
        .take(ALIGNMENT_MAX_BLOCKS_PER_PHASE)
    {
        let start = phase + block_index * block_samples;
        let middle = start + block_samples;
        let end = middle + block_samples;
        let input_a = &samples[start..middle];
        let input_b = &samples[middle..end];
        let rms = ((input_a
            .iter()
            .chain(input_b)
            .map(|sample| f64::from(*sample).powi(2))
            .sum::<f64>()
            / input_samples as f64)
            .sqrt()) as f32;
        if rms < 1.0e-4 {
            continue;
        }
        mdct.process_mdct_with_scratch(input_a, input_b, &mut output, &mut scratch);
        let threshold = rms * block_samples as f32 * ALIGNMENT_SMALL_COEFFICIENT_THRESHOLD;
        let small = output
            .iter()
            .filter(|coefficient| coefficient.abs() <= threshold)
            .count();
        fractions.push(small as f64 / output.len() as f64);
    }
    median(&mut fractions)
}

fn hz_to_bin(frequency_hz: f64, bin_hz: f64, n_bins: usize) -> usize {
    ((frequency_hz / bin_hz).round() as usize).min(n_bins.saturating_sub(1))
}

fn range_mean(prefix: &[f64], start: usize, end: usize) -> f64 {
    if end <= start {
        return 0.0;
    }
    (prefix[end] - prefix[start]) / (end - start) as f64
}

fn exact_u32(field: &str, value: usize) -> Result<u32, AnalysisError> {
    u32::try_from(value)
        .map_err(|_| AnalysisError::NumericalError(format!("{field} does not fit in u32: {value}")))
}

fn median(values: &mut [f64]) -> Option<f64> {
    percentile(values, 0.5)
}

fn percentile(values: &mut [f64], quantile: f64) -> Option<f64> {
    values.sort_by(f64::total_cmp);
    percentile_sorted(values, quantile)
}

fn percentile_sorted(values: &[f64], quantile: f64) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    let position = quantile.clamp(0.0, 1.0) * (values.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    let fraction = position - lower as f64;
    Some(values[lower] + (values[upper] - values[lower]) * fraction)
}

fn percentile_sorted_by<T>(
    values: &[T],
    quantile: f64,
    project: impl Fn(&T) -> f64,
) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    let position = quantile.clamp(0.0, 1.0) * (values.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    let fraction = position - lower as f64;
    let lower_value = project(&values[lower]);
    let upper_value = project(&values[upper]);
    Some(lower_value + (upper_value - lower_value) * fraction)
}

fn validate_ratio(field: &str, value: Option<f32>) -> Result<(), AnalysisError> {
    if let Some(value) = value {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(AnalysisError::NumericalError(format!(
                "{field} must be finite and in [0, 1], got {value}"
            )));
        }
    }
    Ok(())
}

fn validate_non_negative(field: &str, value: f32) -> Result<(), AnalysisError> {
    if !value.is_finite() || value < 0.0 {
        return Err(AnalysisError::NumericalError(format!(
            "{field} must be finite and non-negative, got {value}"
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE_RATE: u32 = 44_100;
    const HOP_SIZE: usize = 512;
    const BINS: usize = 1025;
    const FRAMES: usize = 128;

    fn frequency(bin: usize) -> f64 {
        bin as f64 * SAMPLE_RATE as f64 / ((BINS - 1) * 2) as f64
    }

    fn dense_frames(mut amplitude: impl FnMut(usize, f64) -> f32) -> Vec<Vec<f32>> {
        let mut frames = Vec::with_capacity(FRAMES);
        for frame in 0..FRAMES {
            let mut bins = Vec::with_capacity(BINS);
            for bin in 0..BINS {
                bins.push(amplitude(frame, frequency(bin)));
            }
            frames.push(bins);
        }
        frames
    }

    fn sharp_cutoff_frames(cutoff_hz: f64) -> Vec<Vec<f32>> {
        dense_frames(|frame, hz| {
            let amplitude = 0.85 + ((frame * 17 + (hz / 100.0) as usize) % 23) as f32 / 100.0;
            if hz < cutoff_hz {
                amplitude
            } else {
                amplitude * 1.0e-4
            }
        })
    }

    #[test]
    fn silence_and_short_input_do_not_fabricate_measurements() {
        let silent = vec![vec![0.0; BINS]; FRAMES];
        let result = measure_compression_trace(&silent, SAMPLE_RATE, HOP_SIZE).unwrap();
        assert_eq!(result.active_frame_count, 0);
        assert!(result.spectral_edge_hz.is_none());
        assert!(result.spectral_hole_ratio.is_none());

        let short = vec![vec![1.0; BINS]; MIN_SUPPORTED_FRAMES - 1];
        let result = measure_compression_trace(&short, SAMPLE_RATE, HOP_SIZE).unwrap();
        assert!(result.spectral_edge_hz.is_none());
        assert!(result.spectral_hole_ratio.is_none());
        assert!(result.band_rupture_score.is_none());
    }

    #[test]
    fn low_nyquist_disables_high_frequency_edge_measurement() {
        let frames = dense_frames(|_, _| 1.0);
        let result = measure_compression_trace(&frames, 32_000, HOP_SIZE).unwrap();
        assert_eq!(result.high_band_supported_frame_count, 0);
        assert!(result.spectral_edge_hz.is_none());
    }

    #[test]
    fn sharp_cutoff_produces_a_persistent_edge() {
        let frames = sharp_cutoff_frames(15_700.0);
        let result = measure_compression_trace(&frames, SAMPLE_RATE, HOP_SIZE).unwrap();
        let edge = result.spectral_edge_hz.expect("edge");
        assert!((edge - 15_700.0).abs() < 500.0, "edge={edge}");
        assert!(
            result.spectral_edge_drop_db.expect("drop") > 20.0,
            "{result:?}"
        );
        assert!(
            result.spectral_edge_persistence.expect("persistence") > 0.9,
            "{result:?}"
        );
        assert!(
            result.spectral_hole_ratio.unwrap_or(0.0) < 0.001,
            "cutoff-only input synthesized hole evidence: {result:?}"
        );
        assert!(
            result.band_rupture_score.unwrap_or(0.0) < 0.2,
            "selected cutoff leaked into rupture evidence: {result:?}"
        );
    }

    #[test]
    fn gradual_rolloff_is_less_edge_like_than_a_sharp_cutoff() {
        let sharp =
            measure_compression_trace(&sharp_cutoff_frames(15_700.0), SAMPLE_RATE, HOP_SIZE)
                .unwrap();
        let gradual_frames = dense_frames(|_, hz| (-3.0 * hz / 22_050.0).exp() as f32);
        let gradual = measure_compression_trace(&gradual_frames, SAMPLE_RATE, HOP_SIZE).unwrap();
        assert!(
            gradual.spectral_edge_drop_db.unwrap_or(0.0)
                < sharp.spectral_edge_drop_db.expect("sharp drop")
        );
    }

    #[test]
    fn isolated_holes_move_only_the_hole_measurements() {
        let baseline =
            dense_frames(|frame, hz| 0.8 + ((frame + (hz / 50.0) as usize) % 17) as f32 / 100.0);
        let mut with_holes = baseline.clone();
        for frame in &mut with_holes {
            for bin in (30..900).step_by(31) {
                frame[bin] *= 1.0e-4;
            }
        }
        let baseline = measure_compression_trace(&baseline, SAMPLE_RATE, HOP_SIZE).unwrap();
        let with_holes = measure_compression_trace(&with_holes, SAMPLE_RATE, HOP_SIZE).unwrap();
        assert!(with_holes.spectral_hole_ratio.unwrap() > baseline.spectral_hole_ratio.unwrap());
        assert!(with_holes.isolated_hole_ratio.unwrap() > baseline.isolated_hole_ratio.unwrap());
    }

    #[test]
    fn deeper_band_discontinuity_increases_rupture_score() {
        let shallow = dense_frames(|_, hz| {
            if (5_000.0..7_000.0).contains(&hz) {
                0.5
            } else {
                1.0
            }
        });
        let mut deep = shallow.clone();
        for frame in &mut deep {
            for (bin, magnitude) in frame.iter_mut().enumerate() {
                if (5_000.0..7_000.0).contains(&frequency(bin)) {
                    *magnitude = 0.01;
                }
            }
        }
        let shallow = measure_compression_trace(&shallow, SAMPLE_RATE, HOP_SIZE).unwrap();
        let deep = measure_compression_trace(&deep, SAMPLE_RATE, HOP_SIZE).unwrap();
        assert!(
            deep.band_rupture_score.unwrap() > shallow.band_rupture_score.unwrap(),
            "shallow={shallow:?} deep={deep:?}"
        );
    }

    #[test]
    fn gain_and_leading_silence_preserve_supported_measurements() {
        let frames = sharp_cutoff_frames(15_700.0);
        let scaled: Vec<Vec<f32>> = frames
            .iter()
            .map(|frame| frame.iter().map(|value| value * 0.25).collect())
            .collect();
        let dithered: Vec<Vec<f32>> = frames
            .iter()
            .enumerate()
            .map(|(frame_index, frame)| {
                frame
                    .iter()
                    .enumerate()
                    .map(|(bin, value)| {
                        let sign = if (frame_index + bin).is_multiple_of(2) {
                            1.0
                        } else {
                            -1.0
                        };
                        (value + sign * 1.0e-7).max(0.0)
                    })
                    .collect()
            })
            .collect();
        let trimmed = frames[1..].to_vec();
        let mut padded = vec![vec![0.0; BINS]; 20];
        padded.extend(frames.clone());
        padded.extend(vec![vec![0.0; BINS]; 20]);
        let reference = measure_compression_trace(&frames, SAMPLE_RATE, HOP_SIZE).unwrap();
        let scaled = measure_compression_trace(&scaled, SAMPLE_RATE, HOP_SIZE).unwrap();
        let dithered = measure_compression_trace(&dithered, SAMPLE_RATE, HOP_SIZE).unwrap();
        let trimmed = measure_compression_trace(&trimmed, SAMPLE_RATE, HOP_SIZE).unwrap();
        let padded = measure_compression_trace(&padded, SAMPLE_RATE, HOP_SIZE).unwrap();
        for candidate in [&scaled, &padded] {
            assert_eq!(candidate.active_frame_count, reference.active_frame_count);
        }
        for candidate in [&scaled, &dithered, &trimmed, &padded] {
            assert!(
                (candidate.spectral_edge_hz.unwrap() - reference.spectral_edge_hz.unwrap()).abs()
                    < 0.1
            );
            assert!(
                (candidate.spectral_hole_ratio.unwrap() - reference.spectral_hole_ratio.unwrap())
                    .abs()
                    < 1.0e-6
            );
        }
    }

    #[test]
    fn sparse_harmonic_frames_are_unsupported_instead_of_conjunctive() {
        let frames: Vec<Vec<f32>> = (0..FRAMES)
            .map(|_| {
                let mut frame = vec![0.0; BINS];
                for bin in (20..BINS).step_by(83) {
                    frame[bin] = 1.0;
                }
                frame
            })
            .collect();
        let result = measure_compression_trace(&frames, SAMPLE_RATE, HOP_SIZE).unwrap();
        assert_eq!(result.active_frame_count, 0);
        assert!(result.spectral_edge_hz.is_none());
        assert!(result.spectral_hole_ratio.is_none());
        assert!(result.band_rupture_score.is_none());
    }

    #[test]
    fn malformed_and_random_inputs_have_safe_numeric_behavior() {
        let malformed = vec![vec![1.0; BINS], vec![1.0; BINS - 1]];
        assert!(measure_compression_trace(&malformed, SAMPLE_RATE, HOP_SIZE).is_err());
        let non_finite = vec![vec![f32::NAN; BINS]; FRAMES];
        assert!(measure_compression_trace(&non_finite, SAMPLE_RATE, HOP_SIZE).is_err());

        let mut state = 0x1234_5678_u32;
        let random = dense_frames(|_, _| {
            state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            (state as f64 / u32::MAX as f64) as f32
        });
        let result = measure_compression_trace(&random, SAMPLE_RATE, HOP_SIZE).unwrap();
        result.validate().unwrap();
        serde_json::to_string(&result).unwrap();
    }

    #[test]
    fn analysis_pipeline_reuses_shared_stft_without_promoting_a_verdict() {
        let sample_count = SAMPLE_RATE as usize * 3;
        let mut state = 0xCAFE_BABE_u32;
        let samples: Vec<f32> = (0..sample_count)
            .map(|index| {
                state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                let noise = (state as f64 / u32::MAX as f64 - 0.5) as f32 * 0.02;
                let time = index as f32 / SAMPLE_RATE as f32;
                (std::f32::consts::TAU * 440.0 * time).sin() * 0.3 + noise
            })
            .collect();
        let result = crate::analyze_audio(
            &samples,
            SAMPLE_RATE,
            crate::AnalysisConfig {
                enable_compression_trace_prototype: true,
                ..crate::AnalysisConfig::default()
            },
        )
        .unwrap();
        assert!(result.compression_trace_prototype.is_some());
        let serialized = serde_json::to_value(&result).unwrap();
        assert!(
            serialized.get("compression_trace_prototype").is_none(),
            "prototype must not change the serialized analysis/cache contract"
        );
    }
}
