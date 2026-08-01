//! Machine-readable runner for the private audio-integrity prototype benchmark.

use std::fs::File;
use std::io::Read;
use std::path::Path;
use std::time::Instant;
use std::{
    collections::{BTreeMap, BTreeSet},
    f64::consts::TAU,
};

use lossytrace::{
    analyze_audio, AnalysisConfig, CompressionTraceFeatures,
    COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION,
};
use rustdct::mdct::{window_fn, Mdct};
use rustdct::DctPlanner;
use rustfft::num_complex::Complex;
use rustfft::FftPlanner;
use serde::Serialize;
use sha2::{Digest, Sha256};
use symphonia::core::audio::AudioBufferRef;
use symphonia::core::codecs::DecoderOptions;
use symphonia::core::formats::FormatOptions;
use symphonia::core::io::MediaSourceStream;
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;
use symphonia::default::get_probe;

#[derive(Debug, Serialize)]
struct SourceFacts {
    sample_rate_hz: u32,
    channel_count: Option<usize>,
    declared_bits_per_sample: Option<u32>,
    codec_debug: String,
    container_extension: Option<String>,
}

struct DecodedAudio {
    samples: Vec<f32>,
    side_samples: Option<Vec<f32>>,
    source_facts: SourceFacts,
}

#[derive(Debug, Serialize)]
struct StereoTraceFeatures {
    analyzed_frame_count: usize,
    supported_band_count: usize,
    mid_band_coherence: Option<f64>,
    high_band_coherence: Option<f64>,
    high_band_coherence_lift: Option<f64>,
    high_band_side_ratio: Option<f64>,
    mid_band_side_ratio: Option<f64>,
    high_band_side_suppression: Option<f64>,
    strongest_coherence_step: Option<f64>,
    strongest_coherence_step_hz: Option<f64>,
    strongest_side_ratio_step: Option<f64>,
    strongest_side_ratio_step_hz: Option<f64>,
}

#[derive(Debug, PartialEq, Serialize)]
struct TargetedPhaseVerification {
    discovery_phase_samples: usize,
    candidate_radius_samples: usize,
    control_phase_stride_samples: usize,
    audio_block_count: usize,
    frames_per_phase: usize,
    peak_z_minimum: f64,
    peak_z_median: f64,
    peak_concentration: f64,
    consistent_peak_score: f64,
}

#[derive(Debug, PartialEq, Serialize)]
struct MultiCandidatePhaseVerification {
    discovery_aggregate_phase_samples: usize,
    discovery_candidate_count: usize,
    verified_phase_samples: usize,
    candidate_radius_samples: usize,
    control_phase_stride_samples: usize,
    audio_block_count: usize,
    frames_per_phase: usize,
    peak_z_minimum: f64,
    peak_z_median: f64,
    consistent_peak_score: f64,
}

#[derive(Debug, PartialEq, Serialize)]
struct TransformGridWindowProbe {
    block_samples: usize,
    phase_stride_samples: usize,
    best_phase_samples: usize,
    nac_minimum: f64,
    nac_median: f64,
    nac_contrast: f64,
    local_nac_contrast: f64,
    peak_adjacent_nac_contrast: f64,
    small_coefficient_fraction: f64,
    small_coefficient_contrast: f64,
    peak_adjacent_small_coefficient_contrast: f64,
    histogram_gap_fraction: f64,
    histogram_gap_depletion: f64,
    peak_adjacent_histogram_gap_depletion: f64,
    phase_peak_z_minimum: f64,
    phase_peak_z_median: f64,
    phase_peak_concentration: f64,
    phase_consistent_peak_score: f64,
    phase_aggregate_peak_z: f64,
    phase_aligned_peak_z_minimum: f64,
    phase_aligned_peak_z_median: f64,
    phase_aggregate_peak_samples: usize,
    long_block_audio_block_count: Option<usize>,
    long_block_frames_per_phase: Option<usize>,
    long_block_phase_peak_z_minimum: Option<f64>,
    long_block_phase_peak_z_median: Option<f64>,
    long_block_phase_peak_concentration: Option<f64>,
    long_block_phase_consistent_peak_score: Option<f64>,
    long_block_phase_aggregate_peak_z: Option<f64>,
    long_block_phase_aligned_peak_z_minimum: Option<f64>,
    long_block_phase_aligned_peak_z_median: Option<f64>,
    long_block_phase_aggregate_peak_samples: Option<usize>,
    targeted_phase_verification: Option<TargetedPhaseVerification>,
    multi_candidate_phase_verification: Option<MultiCandidatePhaseVerification>,
}

#[derive(Debug, Serialize)]
struct TransformGridProbe {
    mp3_long_sine: Option<TransformGridWindowProbe>,
    long_sine: Option<TransformGridWindowProbe>,
    long_kbd: Option<TransformGridWindowProbe>,
    long_vorbis: Option<TransformGridWindowProbe>,
    opus_long_celt: Option<TransformGridWindowProbe>,
    opus_short_celt: Option<TransformGridWindowProbe>,
}

#[derive(Debug, Clone, Copy)]
enum TransformGridProfile {
    AlignedPeriodicityV22,
    BalancedOpusPeriodicityV24,
    ConservativeTwoGridV28,
    EfficientPeriodicityV18,
    Full,
    HybridOpusPeriodicityV23,
    LongBlockV16,
    LongBlockV17,
    SampledPeriodicityV19,
    StableV15,
    SubsampledPeriodicityV20,
    TargetedVerificationV25,
    MultiCandidateVerificationV26,
    OpusDualGridV27,
    VerifiedMp3TwoGridV29,
    VerifiedAacMp3FourGridV30,
    VerifiedAacSineMp3ThreeGridV30,
    Mp3FrameVerificationV31,
}

impl TransformGridProfile {
    fn name(self) -> &'static str {
        match self {
            Self::AlignedPeriodicityV22 => "aligned-periodicity-v22",
            Self::BalancedOpusPeriodicityV24 => "balanced-opus-periodicity-v24",
            Self::ConservativeTwoGridV28 => "conservative-two-grid-v28",
            Self::EfficientPeriodicityV18 => "efficient-periodicity-v18",
            Self::Full => "full",
            Self::HybridOpusPeriodicityV23 => "hybrid-opus-periodicity-v23",
            Self::LongBlockV16 => "long-block-v16",
            Self::LongBlockV17 => "long-block-v17",
            Self::SampledPeriodicityV19 => "sampled-periodicity-v19",
            Self::StableV15 => "stable-v15",
            Self::SubsampledPeriodicityV20 => "subsampled-periodicity-v20",
            Self::TargetedVerificationV25 => "targeted-verification-v25",
            Self::MultiCandidateVerificationV26 => "multi-candidate-verification-v26",
            Self::OpusDualGridV27 => "opus-dual-grid-v27",
            Self::VerifiedMp3TwoGridV29 => "verified-mp3-two-grid-v29",
            Self::VerifiedAacMp3FourGridV30 => "verified-aac-mp3-four-grid-v30",
            Self::VerifiedAacSineMp3ThreeGridV30 => "verified-aac-sine-mp3-three-grid-v30",
            Self::Mp3FrameVerificationV31 => "mp3-frame-verification-v31",
        }
    }
}

#[derive(Debug, Clone, Copy)]
enum LongBlockProfile {
    LegacyFourEvenlySpaced,
    TenNonOverlapping,
}

#[derive(Debug, Serialize)]
struct BenchmarkResult {
    schema_version: u32,
    case_id: String,
    audio_sha256: String,
    decoded_sample_count: usize,
    decoded_duration_seconds: f64,
    source_facts: SourceFacts,
    repetitions: usize,
    baseline_times_ms: Vec<f64>,
    prototype_times_ms: Vec<f64>,
    baseline_median_ms: f64,
    prototype_median_ms: f64,
    runtime_overhead_percent: f64,
    feature_version: u16,
    compression_trace: CompressionTraceFeatures,
    stereo_trace: Option<StereoTraceFeatures>,
    research_transform_grid_enabled: bool,
    research_transform_grid_profile: Option<&'static str>,
    research_transform_grid_elapsed_ms: Option<f64>,
    research_total_runtime_overhead_percent: f64,
    transform_grid_probe: Option<TransformGridProbe>,
}

#[derive(Debug, Serialize)]
struct MemoryRunResult {
    schema_version: u32,
    case_id: String,
    audio_sha256: String,
    decoded_sample_count: usize,
    decoded_duration_seconds: f64,
    prototype_enabled: bool,
    feature_version: u16,
    compression_trace_measured: bool,
}

#[derive(Debug, Serialize)]
struct TransformOnlyRunResult {
    schema_version: u32,
    case_id: String,
    audio_sha256: String,
    decoded_sample_count: usize,
    decoded_duration_seconds: f64,
    source_facts: SourceFacts,
    research_transform_grid_profile: &'static str,
    research_transform_grid_elapsed_ms: f64,
    transform_grid_probe: TransformGridProbe,
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|error| format!("open {}: {error}", path.display()))?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = file.read(&mut buffer).map_err(|error| error.to_string())?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn downmix(buf: &AudioBufferRef<'_>, output: &mut Vec<f32>, side: &mut Vec<f32>) {
    fn mix<T: Copy>(
        planes: &[&[T]],
        convert: impl Fn(T) -> f32,
        output: &mut Vec<f32>,
        side: &mut Vec<f32>,
    ) {
        if planes.is_empty() {
            return;
        }
        for index in 0..planes[0].len() {
            let sum: f32 = planes.iter().map(|plane| convert(plane[index])).sum();
            output.push(sum / planes.len() as f32);
            if planes.len() == 2 {
                side.push((convert(planes[0][index]) - convert(planes[1][index])) * 0.5);
            }
        }
    }
    match buf {
        AudioBufferRef::F32(b) => mix(b.planes().planes(), |value| value, output, side),
        AudioBufferRef::F64(b) => mix(b.planes().planes(), |value| value as f32, output, side),
        AudioBufferRef::S8(b) => mix(
            b.planes().planes(),
            |value| value as f32 / 128.0,
            output,
            side,
        ),
        AudioBufferRef::S16(b) => mix(
            b.planes().planes(),
            |value| value as f32 / 32_768.0,
            output,
            side,
        ),
        AudioBufferRef::S24(b) => mix(
            b.planes().planes(),
            |value| value.inner() as f32 / 8_388_608.0,
            output,
            side,
        ),
        AudioBufferRef::S32(b) => mix(
            b.planes().planes(),
            |value| value as f32 / 2_147_483_648.0,
            output,
            side,
        ),
        AudioBufferRef::U8(b) => mix(
            b.planes().planes(),
            |value| (value as f32 - 128.0) / 128.0,
            output,
            side,
        ),
        AudioBufferRef::U16(b) => mix(
            b.planes().planes(),
            |value| (value as f32 - 32_768.0) / 32_768.0,
            output,
            side,
        ),
        AudioBufferRef::U24(b) => mix(
            b.planes().planes(),
            |value| (value.inner() as f32 - 8_388_608.0) / 8_388_608.0,
            output,
            side,
        ),
        AudioBufferRef::U32(b) => mix(
            b.planes().planes(),
            |value| (value as f32 - 2_147_483_648.0) / 2_147_483_648.0,
            output,
            side,
        ),
    }
}

fn median_option(values: &mut [f64]) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    values.sort_by(f64::total_cmp);
    let midpoint = values.len() / 2;
    if values.len().is_multiple_of(2) {
        Some((values[midpoint - 1] + values[midpoint]) * 0.5)
    } else {
        Some(values[midpoint])
    }
}

fn stereo_trace(
    mid_samples: &[f32],
    side_samples: &[f32],
    sample_rate: u32,
) -> Option<StereoTraceFeatures> {
    const FRAME_SIZE: usize = 2_048;
    const HOP_SIZE: usize = 1_024;
    const FIRST_BAND_HZ: f64 = 2_000.0;
    const BAND_WIDTH_HZ: f64 = 1_000.0;
    const BAND_COUNT: usize = 18;
    const MIN_BAND_FRAMES: usize = 16;

    let sample_count = mid_samples.len().min(side_samples.len());
    if sample_count < FRAME_SIZE || sample_rate < 40_000 {
        return None;
    }
    let frame_count = 1 + (sample_count - FRAME_SIZE) / HOP_SIZE;
    let window: Vec<f32> = (0..FRAME_SIZE)
        .map(|index| {
            let phase = 2.0 * std::f32::consts::PI * index as f32 / (FRAME_SIZE - 1) as f32;
            0.5 * (1.0 - phase.cos())
        })
        .collect();
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(FRAME_SIZE);
    let bin_hz = f64::from(sample_rate) / FRAME_SIZE as f64;
    let mut coherence_by_band = vec![Vec::new(); BAND_COUNT];
    let mut side_ratio_by_band = vec![Vec::new(); BAND_COUNT];
    let mut mid_fft = vec![Complex::new(0.0_f32, 0.0); FRAME_SIZE];
    let mut side_fft = vec![Complex::new(0.0_f32, 0.0); FRAME_SIZE];

    for frame_index in 0..frame_count {
        let start = frame_index * HOP_SIZE;
        for sample_index in 0..FRAME_SIZE {
            let weight = window[sample_index];
            mid_fft[sample_index] = Complex::new(mid_samples[start + sample_index] * weight, 0.0);
            side_fft[sample_index] = Complex::new(side_samples[start + sample_index] * weight, 0.0);
        }
        fft.process(&mut mid_fft);
        fft.process(&mut side_fft);

        let frame_power: f64 = mid_fft[..=FRAME_SIZE / 2]
            .iter()
            .zip(&side_fft[..=FRAME_SIZE / 2])
            .map(|(mid, side)| f64::from(mid.norm_sqr() + side.norm_sqr()))
            .sum();
        if frame_power <= 1.0e-12 {
            continue;
        }

        for band_index in 0..BAND_COUNT {
            let start_hz = FIRST_BAND_HZ + band_index as f64 * BAND_WIDTH_HZ;
            let end_hz = start_hz + BAND_WIDTH_HZ;
            let start_bin = (start_hz / bin_hz).ceil() as usize;
            let end_bin = ((end_hz / bin_hz).floor() as usize).min(FRAME_SIZE / 2 + 1);
            if end_bin <= start_bin {
                continue;
            }

            let mut left_power = 0.0_f64;
            let mut right_power = 0.0_f64;
            let mut mid_power = 0.0_f64;
            let mut side_power = 0.0_f64;
            let mut cross = Complex::new(0.0_f64, 0.0);
            for bin in start_bin..end_bin {
                let mid = mid_fft[bin];
                let side = side_fft[bin];
                let left = mid + side;
                let right = mid - side;
                left_power += f64::from(left.norm_sqr());
                right_power += f64::from(right.norm_sqr());
                mid_power += f64::from(mid.norm_sqr());
                side_power += f64::from(side.norm_sqr());
                let product = left * right.conj();
                cross += Complex::new(f64::from(product.re), f64::from(product.im));
            }
            let band_power = mid_power + side_power;
            if band_power / frame_power < 1.0e-5 || left_power <= 1.0e-12 || right_power <= 1.0e-12
            {
                continue;
            }
            let coherence = (cross.norm() / (left_power * right_power).sqrt()).clamp(0.0, 1.0);
            coherence_by_band[band_index].push(coherence);
            side_ratio_by_band[band_index].push(side_power / band_power);
        }
    }

    let band_coherence: Vec<Option<f64>> = coherence_by_band
        .iter_mut()
        .map(|values| {
            (values.len() >= MIN_BAND_FRAMES)
                .then(|| median_option(values))
                .flatten()
        })
        .collect();
    let band_side_ratio: Vec<Option<f64>> = side_ratio_by_band
        .iter_mut()
        .map(|values| {
            (values.len() >= MIN_BAND_FRAMES)
                .then(|| median_option(values))
                .flatten()
        })
        .collect();
    let supported_band_count = band_coherence
        .iter()
        .filter(|value| value.is_some())
        .count();
    if supported_band_count < 6 {
        return None;
    }

    let region_median = |values: &[Option<f64>], start: usize, end: usize| {
        let mut present: Vec<f64> = values[start..end].iter().flatten().copied().collect();
        median_option(&mut present)
    };
    let mid_band_coherence = region_median(&band_coherence, 0, 6);
    let high_band_coherence = region_median(&band_coherence, 8, BAND_COUNT);
    let mid_band_side_ratio = region_median(&band_side_ratio, 0, 6);
    let high_band_side_ratio = region_median(&band_side_ratio, 8, BAND_COUNT);
    let high_band_coherence_lift = mid_band_coherence
        .zip(high_band_coherence)
        .map(|(mid, high)| (high - mid).max(0.0));
    let high_band_side_suppression = mid_band_side_ratio
        .zip(high_band_side_ratio)
        .map(|(mid, high)| (mid - high).max(0.0));

    let strongest_step = |values: &[Option<f64>]| {
        values
            .windows(2)
            .enumerate()
            .filter_map(|(index, pair)| {
                pair[0]
                    .zip(pair[1])
                    .map(|(before, after)| ((after - before).abs(), index))
            })
            .max_by(|left, right| left.0.total_cmp(&right.0))
            .map(|(strength, index)| (strength, FIRST_BAND_HZ + (index + 1) as f64 * BAND_WIDTH_HZ))
    };
    let coherence_step = strongest_step(&band_coherence);
    let side_ratio_step = strongest_step(&band_side_ratio);

    Some(StereoTraceFeatures {
        analyzed_frame_count: frame_count,
        supported_band_count,
        mid_band_coherence,
        high_band_coherence,
        high_band_coherence_lift,
        high_band_side_ratio,
        mid_band_side_ratio,
        high_band_side_suppression,
        strongest_coherence_step: coherence_step.map(|value| value.0),
        strongest_coherence_step_hz: coherence_step.map(|value| value.1),
        strongest_side_ratio_step: side_ratio_step.map(|value| value.0),
        strongest_side_ratio_step_hz: side_ratio_step.map(|value| value.1),
    })
}

#[derive(Debug, Clone, Copy)]
struct TransformPhaseMeasurement {
    nac: f64,
    small_fraction: f64,
    gap_fraction: f64,
}

#[derive(Debug, Clone, Copy)]
struct PhasePeak {
    phase_samples: usize,
    z_score: f64,
}

#[derive(Debug, Clone, Copy)]
struct PhasePeriodicityMeasurement {
    audio_block_count: usize,
    frames_per_phase: usize,
    phase_stride_samples: usize,
    peak_z_minimum: f64,
    peak_z_median: f64,
    peak_concentration: f64,
    consistent_peak_score: f64,
    aggregate_peak_z: f64,
    aligned_peak_z_minimum: f64,
    aligned_peak_z_median: f64,
    aggregate_peak_samples: usize,
    peak_phase_count: usize,
    peak_phase_samples: [usize; 16],
}

fn phase_periodicity_probe(
    samples: &[f32],
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
    audio_block_count: usize,
    frames_per_phase: usize,
    frame_stride: usize,
    phase_stride: usize,
    block_spacing_frames: Option<usize>,
    minimum_peak_count: usize,
) -> Option<PhasePeriodicityMeasurement> {
    const LOG_FLOOR: f64 = 1.0e-12;

    if audio_block_count < 2
        || frames_per_phase == 0
        || frame_stride == 0
        || phase_stride == 0
        || !block_samples.is_multiple_of(phase_stride)
        || minimum_peak_count < 2
        || minimum_peak_count > audio_block_count
    {
        return None;
    }
    let input_samples = block_samples.checked_mul(2)?;
    let sampled_frame_span = frames_per_phase
        .checked_sub(1)?
        .checked_mul(frame_stride)?
        .checked_add(2)?;
    let block_span = block_samples.checked_mul(sampled_frame_span)?;
    if samples.len() < block_span {
        return None;
    }
    let available_aligned_starts = (samples.len() - block_span) / block_samples;
    let block_indices: Vec<usize> = if let Some(block_spacing_frames) = block_spacing_frames {
        let available_blocks = available_aligned_starts / block_spacing_frames + 1;
        let selected_block_count = audio_block_count.min(available_blocks);
        (0..selected_block_count)
            .map(|index| {
                index * available_blocks.saturating_sub(1)
                    / selected_block_count.saturating_sub(1).max(1)
                    * block_spacing_frames
            })
            .collect()
    } else {
        (0..audio_block_count)
            .map(|index| {
                index * available_aligned_starts / audio_block_count.saturating_sub(1).max(1)
            })
            .collect()
    };
    let mut output = vec![0.0_f32; block_samples];
    let mut scratch = vec![0.0_f32; mdct.get_scratch_len()];
    let mut peaks = Vec::with_capacity(audio_block_count);
    let mut standardized_curves = Vec::with_capacity(audio_block_count);
    let phase_count = block_samples / phase_stride;

    for block_index in block_indices {
        let anchor = block_index * block_samples;
        let mut phase_energy = Vec::with_capacity(phase_count + 1);
        for phase in (0..=block_samples).step_by(phase_stride) {
            let mut energy = 0.0_f64;
            let mut measured_coefficients = 0_usize;
            for frame in 0..frames_per_phase {
                let start = anchor + frame * frame_stride * block_samples + phase;
                let middle = start + block_samples;
                let end = middle + block_samples;
                if end > samples.len() {
                    continue;
                }
                let input_a = &samples[start..middle];
                let input_b = &samples[middle..end];
                let rms = (input_a
                    .iter()
                    .chain(input_b)
                    .map(|sample| f64::from(*sample).powi(2))
                    .sum::<f64>()
                    / input_samples as f64)
                    .sqrt();
                if rms < 1.0e-5 {
                    continue;
                }
                mdct.process_mdct_with_scratch(input_a, input_b, &mut output, &mut scratch);
                let scale = (rms * block_samples as f64).max(LOG_FLOOR);
                for coefficient in output.iter().copied() {
                    let normalized = f64::from(coefficient).abs() / scale;
                    energy += normalized.max(LOG_FLOOR).log10();
                }
                measured_coefficients += output.len();
            }
            if measured_coefficients == 0 {
                phase_energy.push(None);
            } else {
                phase_energy.push(Some(energy / measured_coefficients as f64));
            }
        }
        let differences: Vec<f64> = phase_energy
            .windows(2)
            .filter_map(|pair| pair[0].zip(pair[1]).map(|(before, after)| after - before))
            .collect();
        if differences.len() != phase_count {
            continue;
        }
        let mean = differences.iter().sum::<f64>() / differences.len() as f64;
        let variance = differences
            .iter()
            .map(|difference| (difference - mean).powi(2))
            .sum::<f64>()
            / differences.len() as f64;
        let standard_deviation = variance.sqrt();
        if standard_deviation <= 1.0e-12 {
            continue;
        }
        let standardized = differences
            .iter()
            .map(|difference| (difference - mean) / standard_deviation)
            .collect::<Vec<_>>();
        let (phase_index, peak_z) = standardized
            .iter()
            .copied()
            .enumerate()
            .max_by(|left, right| left.1.total_cmp(&right.1))?;
        peaks.push(PhasePeak {
            phase_samples: phase_index * phase_stride,
            z_score: peak_z,
        });
        standardized_curves.push(standardized);
    }
    if peaks.len() < minimum_peak_count {
        return None;
    }

    let mut peak_z_scores: Vec<f64> = peaks.iter().map(|peak| peak.z_score).collect();
    let phase_peak_z_minimum = peak_z_scores.iter().copied().fold(f64::INFINITY, f64::min);
    let phase_peak_z_median = median_option(&mut peak_z_scores)?;
    let (x, y, total_weight) =
        peaks
            .iter()
            .fold((0.0_f64, 0.0_f64, 0.0_f64), |(x, y, total_weight), peak| {
                let angle =
                    2.0 * std::f64::consts::PI * peak.phase_samples as f64 / block_samples as f64;
                (
                    x + peak.z_score * angle.cos(),
                    y + peak.z_score * angle.sin(),
                    total_weight + peak.z_score,
                )
            });
    let resultant = x.hypot(y);
    let phase_peak_concentration = resultant / total_weight.max(1.0e-12);
    let phase_consistent_peak_score = resultant / peaks.len() as f64;
    let (aggregate_peak_index, aggregate_peak_z) = (0..phase_count)
        .map(|phase| {
            (
                phase,
                standardized_curves
                    .iter()
                    .map(|curve| curve[phase])
                    .sum::<f64>()
                    / standardized_curves.len() as f64,
            )
        })
        .max_by(|left, right| left.1.total_cmp(&right.1))?;
    let mut aligned_peak_z = standardized_curves
        .iter()
        .map(|curve| curve[aggregate_peak_index])
        .collect::<Vec<_>>();
    let aligned_peak_z_minimum = aligned_peak_z.iter().copied().fold(f64::INFINITY, f64::min);
    let aligned_peak_z_median = median_option(&mut aligned_peak_z)?;
    let mut peak_phase_samples = [0_usize; 16];
    let peak_phase_count = peaks.len().min(peak_phase_samples.len());
    for (destination, peak) in peak_phase_samples.iter_mut().zip(peaks.iter()) {
        *destination = peak.phase_samples;
    }
    Some(PhasePeriodicityMeasurement {
        audio_block_count: peaks.len(),
        frames_per_phase,
        phase_stride_samples: phase_stride,
        peak_z_minimum: phase_peak_z_minimum,
        peak_z_median: phase_peak_z_median,
        peak_concentration: phase_peak_concentration.clamp(0.0, 1.0),
        consistent_peak_score: phase_consistent_peak_score,
        aggregate_peak_z,
        aligned_peak_z_minimum,
        aligned_peak_z_median,
        aggregate_peak_samples: aggregate_peak_index * phase_stride,
        peak_phase_count,
        peak_phase_samples,
    })
}

fn transform_grid_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
    long_block_profile: LongBlockProfile,
) -> Option<TransformGridWindowProbe> {
    const BLOCKS_PER_PHASE: usize = 3;
    const SMALL_THRESHOLD: f64 = 1.0e-5;
    const GAP_UPPER_THRESHOLD: f64 = 1.0e-4;

    let input_samples = block_samples.checked_mul(2)?;
    if samples.len() < input_samples + block_samples {
        return None;
    }
    let available_blocks = (samples.len() - input_samples) / block_samples;
    let block_indices: Vec<usize> = (0..BLOCKS_PER_PHASE)
        .map(|index| {
            index * available_blocks.saturating_sub(1) / BLOCKS_PER_PHASE.saturating_sub(1).max(1)
        })
        .collect();
    let mut output = vec![0.0_f32; block_samples];
    let mut scratch = vec![0.0_f32; mdct.get_scratch_len()];
    let mut phases = Vec::with_capacity(block_samples);

    for phase in 0..block_samples {
        let mut nac_values = Vec::with_capacity(BLOCKS_PER_PHASE);
        let mut small_fractions = Vec::with_capacity(BLOCKS_PER_PHASE);
        let mut gap_fractions = Vec::with_capacity(BLOCKS_PER_PHASE);
        for block_index in block_indices.iter().copied() {
            let start = block_index * block_samples + phase;
            let middle = start + block_samples;
            let end = middle + block_samples;
            if end > samples.len() {
                continue;
            }
            let input_a = &samples[start..middle];
            let input_b = &samples[middle..end];
            let rms = (input_a
                .iter()
                .chain(input_b)
                .map(|sample| f64::from(*sample).powi(2))
                .sum::<f64>()
                / input_samples as f64)
                .sqrt();
            if rms < 1.0e-5 {
                continue;
            }
            mdct.process_mdct_with_scratch(input_a, input_b, &mut output, &mut scratch);
            let scale = (rms * block_samples as f64).max(1.0e-12);
            let mut nac = 0.0_f64;
            let mut small = 0_usize;
            let mut gap = 0_usize;
            for coefficient in output.iter().copied() {
                let normalized = f64::from(coefficient).abs() / scale;
                nac += (normalized * normalized * 1.0e10).max(1.0).log10();
                small += usize::from(normalized < SMALL_THRESHOLD);
                gap += usize::from((SMALL_THRESHOLD..GAP_UPPER_THRESHOLD).contains(&normalized));
            }
            nac_values.push(nac / block_samples as f64);
            small_fractions.push(small as f64 / block_samples as f64);
            gap_fractions.push(gap as f64 / block_samples as f64);
        }
        phases.push(TransformPhaseMeasurement {
            nac: median_option(&mut nac_values)?,
            small_fraction: median_option(&mut small_fractions)?,
            gap_fraction: median_option(&mut gap_fractions)?,
        });
    }

    let (best_phase_samples, best) = phases
        .iter()
        .enumerate()
        .min_by(|left, right| left.1.nac.total_cmp(&right.1.nac))?;
    let mut nac_values: Vec<f64> = phases.iter().map(|phase| phase.nac).collect();
    let nac_median = median_option(&mut nac_values)?;
    let mut small_values: Vec<f64> = phases.iter().map(|phase| phase.small_fraction).collect();
    let small_median = median_option(&mut small_values)?;
    let mut gap_values: Vec<f64> = phases.iter().map(|phase| phase.gap_fraction).collect();
    let gap_median = median_option(&mut gap_values)?;
    let mut local_nac_values: Vec<f64> = (1..=8)
        .flat_map(|distance| {
            [
                phases[(best_phase_samples + distance) % block_samples].nac,
                phases[(best_phase_samples + block_samples - distance) % block_samples].nac,
            ]
        })
        .collect();
    let local_nac = median_option(&mut local_nac_values)?;
    let adjacent_peak = |project: fn(&TransformPhaseMeasurement) -> f64, inverted: bool| {
        phases
            .iter()
            .enumerate()
            .map(|(phase, measurement)| {
                let before = project(&phases[(phase + block_samples - 1) % block_samples]);
                let after = project(&phases[(phase + 1) % block_samples]);
                let center = project(measurement);
                if inverted {
                    ((before + after) * 0.5 - center).max(0.0)
                } else {
                    (center - (before + after) * 0.5).max(0.0)
                }
            })
            .fold(0.0_f64, f64::max)
    };
    let short_periodicity =
        phase_periodicity_probe(samples, block_samples, mdct, 8, 2, 1, 1, None, 4)?;
    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let long_periodicity = match long_block_profile {
        LongBlockProfile::LegacyFourEvenlySpaced => phase_periodicity_probe(
            samples,
            block_samples,
            mdct,
            4,
            frames_per_second,
            1,
            1,
            None,
            2,
        ),
        LongBlockProfile::TenNonOverlapping => phase_periodicity_probe(
            samples,
            block_samples,
            mdct,
            10,
            frames_per_second,
            1,
            1,
            Some(frames_per_second),
            3,
        ),
    };

    Some(TransformGridWindowProbe {
        block_samples,
        phase_stride_samples: 1,
        best_phase_samples,
        nac_minimum: best.nac,
        nac_median,
        nac_contrast: ((nac_median - best.nac) / nac_median.max(1.0e-12)).clamp(0.0, 1.0),
        local_nac_contrast: ((local_nac - best.nac) / nac_median.max(1.0e-12)).clamp(0.0, 1.0),
        peak_adjacent_nac_contrast: (adjacent_peak(|phase| phase.nac, true)
            / nac_median.max(1.0e-12))
        .clamp(0.0, 1.0),
        small_coefficient_fraction: best.small_fraction,
        small_coefficient_contrast: (best.small_fraction - small_median).clamp(0.0, 1.0),
        peak_adjacent_small_coefficient_contrast: adjacent_peak(
            |phase| phase.small_fraction,
            false,
        )
        .clamp(0.0, 1.0),
        histogram_gap_fraction: best.gap_fraction,
        histogram_gap_depletion: (gap_median - best.gap_fraction).clamp(0.0, 1.0),
        peak_adjacent_histogram_gap_depletion: adjacent_peak(|phase| phase.gap_fraction, true)
            .clamp(0.0, 1.0),
        phase_peak_z_minimum: short_periodicity.peak_z_minimum,
        phase_peak_z_median: short_periodicity.peak_z_median,
        phase_peak_concentration: short_periodicity.peak_concentration,
        phase_consistent_peak_score: short_periodicity.consistent_peak_score,
        phase_aggregate_peak_z: short_periodicity.aggregate_peak_z,
        phase_aligned_peak_z_minimum: short_periodicity.aligned_peak_z_minimum,
        phase_aligned_peak_z_median: short_periodicity.aligned_peak_z_median,
        phase_aggregate_peak_samples: short_periodicity.aggregate_peak_samples,
        long_block_audio_block_count: long_periodicity.map(|value| value.audio_block_count),
        long_block_frames_per_phase: long_periodicity.map(|value| value.frames_per_phase),
        long_block_phase_peak_z_minimum: long_periodicity.map(|value| value.peak_z_minimum),
        long_block_phase_peak_z_median: long_periodicity.map(|value| value.peak_z_median),
        long_block_phase_peak_concentration: long_periodicity.map(|value| value.peak_concentration),
        long_block_phase_consistent_peak_score: long_periodicity
            .map(|value| value.consistent_peak_score),
        long_block_phase_aggregate_peak_z: long_periodicity.map(|value| value.aggregate_peak_z),
        long_block_phase_aligned_peak_z_minimum: long_periodicity
            .map(|value| value.aligned_peak_z_minimum),
        long_block_phase_aligned_peak_z_median: long_periodicity
            .map(|value| value.aligned_peak_z_median),
        long_block_phase_aggregate_peak_samples: long_periodicity
            .map(|value| value.aggregate_peak_samples),
        targeted_phase_verification: None,
        multi_candidate_phase_verification: None,
    })
}

fn periodicity_window_probe(
    block_samples: usize,
    periodicity: PhasePeriodicityMeasurement,
) -> TransformGridWindowProbe {
    // This research profile deliberately omits the legacy coefficient-grid
    // measurements. The profile name makes the zero placeholders
    // unambiguous; only the phase-periodicity fields are candidates for use.
    TransformGridWindowProbe {
        block_samples,
        phase_stride_samples: periodicity.phase_stride_samples,
        best_phase_samples: 0,
        nac_minimum: 0.0,
        nac_median: 0.0,
        nac_contrast: 0.0,
        local_nac_contrast: 0.0,
        peak_adjacent_nac_contrast: 0.0,
        small_coefficient_fraction: 0.0,
        small_coefficient_contrast: 0.0,
        peak_adjacent_small_coefficient_contrast: 0.0,
        histogram_gap_fraction: 0.0,
        histogram_gap_depletion: 0.0,
        peak_adjacent_histogram_gap_depletion: 0.0,
        phase_peak_z_minimum: periodicity.peak_z_minimum,
        phase_peak_z_median: periodicity.peak_z_median,
        phase_peak_concentration: periodicity.peak_concentration,
        phase_consistent_peak_score: periodicity.consistent_peak_score,
        phase_aggregate_peak_z: periodicity.aggregate_peak_z,
        phase_aligned_peak_z_minimum: periodicity.aligned_peak_z_minimum,
        phase_aligned_peak_z_median: periodicity.aligned_peak_z_median,
        phase_aggregate_peak_samples: periodicity.aggregate_peak_samples,
        long_block_audio_block_count: Some(periodicity.audio_block_count),
        long_block_frames_per_phase: Some(periodicity.frames_per_phase),
        long_block_phase_peak_z_minimum: Some(periodicity.peak_z_minimum),
        long_block_phase_peak_z_median: Some(periodicity.peak_z_median),
        long_block_phase_peak_concentration: Some(periodicity.peak_concentration),
        long_block_phase_consistent_peak_score: Some(periodicity.consistent_peak_score),
        long_block_phase_aggregate_peak_z: Some(periodicity.aggregate_peak_z),
        long_block_phase_aligned_peak_z_minimum: Some(periodicity.aligned_peak_z_minimum),
        long_block_phase_aligned_peak_z_median: Some(periodicity.aligned_peak_z_median),
        long_block_phase_aggregate_peak_samples: Some(periodicity.aggregate_peak_samples),
        targeted_phase_verification: None,
        multi_candidate_phase_verification: None,
    }
}

fn efficient_periodicity_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
) -> Option<TransformGridWindowProbe> {
    const AUDIO_BLOCK_COUNT: usize = 10;
    const FRAMES_PER_PHASE: usize = 1;
    const MINIMUM_PEAK_COUNT: usize = 5;

    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let periodicity = phase_periodicity_probe(
        samples,
        block_samples,
        mdct,
        AUDIO_BLOCK_COUNT,
        FRAMES_PER_PHASE,
        1,
        1,
        Some(frames_per_second),
        MINIMUM_PEAK_COUNT,
    )?;
    Some(periodicity_window_probe(block_samples, periodicity))
}

fn sampled_periodicity_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
    phase_stride: usize,
) -> Option<TransformGridWindowProbe> {
    const AUDIO_BLOCK_COUNT: usize = 4;
    const FRAMES_PER_PHASE: usize = 4;
    const MINIMUM_PEAK_COUNT: usize = 3;

    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let frame_stride = frames_per_second.div_ceil(FRAMES_PER_PHASE).max(1);
    let periodicity = phase_periodicity_probe(
        samples,
        block_samples,
        mdct,
        AUDIO_BLOCK_COUNT,
        FRAMES_PER_PHASE,
        frame_stride,
        phase_stride,
        Some(frames_per_second * 2),
        MINIMUM_PEAK_COUNT,
    )?;

    Some(TransformGridWindowProbe {
        block_samples,
        phase_stride_samples: periodicity.phase_stride_samples,
        best_phase_samples: 0,
        nac_minimum: 0.0,
        nac_median: 0.0,
        nac_contrast: 0.0,
        local_nac_contrast: 0.0,
        peak_adjacent_nac_contrast: 0.0,
        small_coefficient_fraction: 0.0,
        small_coefficient_contrast: 0.0,
        peak_adjacent_small_coefficient_contrast: 0.0,
        histogram_gap_fraction: 0.0,
        histogram_gap_depletion: 0.0,
        peak_adjacent_histogram_gap_depletion: 0.0,
        phase_peak_z_minimum: periodicity.peak_z_minimum,
        phase_peak_z_median: periodicity.peak_z_median,
        phase_peak_concentration: periodicity.peak_concentration,
        phase_consistent_peak_score: periodicity.consistent_peak_score,
        phase_aggregate_peak_z: periodicity.aggregate_peak_z,
        phase_aligned_peak_z_minimum: periodicity.aligned_peak_z_minimum,
        phase_aligned_peak_z_median: periodicity.aligned_peak_z_median,
        phase_aggregate_peak_samples: periodicity.aggregate_peak_samples,
        long_block_audio_block_count: Some(periodicity.audio_block_count),
        long_block_frames_per_phase: Some(periodicity.frames_per_phase),
        long_block_phase_peak_z_minimum: Some(periodicity.peak_z_minimum),
        long_block_phase_peak_z_median: Some(periodicity.peak_z_median),
        long_block_phase_peak_concentration: Some(periodicity.peak_concentration),
        long_block_phase_consistent_peak_score: Some(periodicity.consistent_peak_score),
        long_block_phase_aggregate_peak_z: Some(periodicity.aggregate_peak_z),
        long_block_phase_aligned_peak_z_minimum: Some(periodicity.aligned_peak_z_minimum),
        long_block_phase_aligned_peak_z_median: Some(periodicity.aligned_peak_z_median),
        long_block_phase_aggregate_peak_samples: Some(periodicity.aggregate_peak_samples),
        targeted_phase_verification: None,
        multi_candidate_phase_verification: None,
    })
}

fn coarse_long_periodicity_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
) -> Option<TransformGridWindowProbe> {
    const AUDIO_BLOCK_COUNT: usize = 4;
    const PHASE_STRIDE: usize = 8;
    const MINIMUM_PEAK_COUNT: usize = 3;

    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let periodicity = phase_periodicity_probe(
        samples,
        block_samples,
        mdct,
        AUDIO_BLOCK_COUNT,
        frames_per_second,
        1,
        PHASE_STRIDE,
        None,
        MINIMUM_PEAK_COUNT,
    )?;

    Some(TransformGridWindowProbe {
        block_samples,
        phase_stride_samples: periodicity.phase_stride_samples,
        best_phase_samples: 0,
        nac_minimum: 0.0,
        nac_median: 0.0,
        nac_contrast: 0.0,
        local_nac_contrast: 0.0,
        peak_adjacent_nac_contrast: 0.0,
        small_coefficient_fraction: 0.0,
        small_coefficient_contrast: 0.0,
        peak_adjacent_small_coefficient_contrast: 0.0,
        histogram_gap_fraction: 0.0,
        histogram_gap_depletion: 0.0,
        peak_adjacent_histogram_gap_depletion: 0.0,
        phase_peak_z_minimum: periodicity.peak_z_minimum,
        phase_peak_z_median: periodicity.peak_z_median,
        phase_peak_concentration: periodicity.peak_concentration,
        phase_consistent_peak_score: periodicity.consistent_peak_score,
        phase_aggregate_peak_z: periodicity.aggregate_peak_z,
        phase_aligned_peak_z_minimum: periodicity.aligned_peak_z_minimum,
        phase_aligned_peak_z_median: periodicity.aligned_peak_z_median,
        phase_aggregate_peak_samples: periodicity.aggregate_peak_samples,
        long_block_audio_block_count: Some(periodicity.audio_block_count),
        long_block_frames_per_phase: Some(periodicity.frames_per_phase),
        long_block_phase_peak_z_minimum: Some(periodicity.peak_z_minimum),
        long_block_phase_peak_z_median: Some(periodicity.peak_z_median),
        long_block_phase_peak_concentration: Some(periodicity.peak_concentration),
        long_block_phase_consistent_peak_score: Some(periodicity.consistent_peak_score),
        long_block_phase_aggregate_peak_z: Some(periodicity.aggregate_peak_z),
        long_block_phase_aligned_peak_z_minimum: Some(periodicity.aligned_peak_z_minimum),
        long_block_phase_aligned_peak_z_median: Some(periodicity.aligned_peak_z_median),
        long_block_phase_aggregate_peak_samples: Some(periodicity.aggregate_peak_samples),
        targeted_phase_verification: None,
        multi_candidate_phase_verification: None,
    })
}

fn balanced_opus_periodicity_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
) -> Option<TransformGridWindowProbe> {
    const AUDIO_BLOCK_COUNT: usize = 3;
    const FRAMES_PER_PHASE: usize = 48;
    const PHASE_STRIDE: usize = 4;

    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let periodicity = phase_periodicity_probe(
        samples,
        block_samples,
        mdct,
        AUDIO_BLOCK_COUNT,
        FRAMES_PER_PHASE.min(frames_per_second),
        1,
        PHASE_STRIDE,
        None,
        AUDIO_BLOCK_COUNT,
    )?;

    Some(TransformGridWindowProbe {
        block_samples,
        phase_stride_samples: periodicity.phase_stride_samples,
        best_phase_samples: 0,
        nac_minimum: 0.0,
        nac_median: 0.0,
        nac_contrast: 0.0,
        local_nac_contrast: 0.0,
        peak_adjacent_nac_contrast: 0.0,
        small_coefficient_fraction: 0.0,
        small_coefficient_contrast: 0.0,
        peak_adjacent_small_coefficient_contrast: 0.0,
        histogram_gap_fraction: 0.0,
        histogram_gap_depletion: 0.0,
        peak_adjacent_histogram_gap_depletion: 0.0,
        phase_peak_z_minimum: periodicity.peak_z_minimum,
        phase_peak_z_median: periodicity.peak_z_median,
        phase_peak_concentration: periodicity.peak_concentration,
        phase_consistent_peak_score: periodicity.consistent_peak_score,
        phase_aggregate_peak_z: periodicity.aggregate_peak_z,
        phase_aligned_peak_z_minimum: periodicity.aligned_peak_z_minimum,
        phase_aligned_peak_z_median: periodicity.aligned_peak_z_median,
        phase_aggregate_peak_samples: periodicity.aggregate_peak_samples,
        long_block_audio_block_count: Some(periodicity.audio_block_count),
        long_block_frames_per_phase: Some(periodicity.frames_per_phase),
        long_block_phase_peak_z_minimum: Some(periodicity.peak_z_minimum),
        long_block_phase_peak_z_median: Some(periodicity.peak_z_median),
        long_block_phase_peak_concentration: Some(periodicity.peak_concentration),
        long_block_phase_consistent_peak_score: Some(periodicity.consistent_peak_score),
        long_block_phase_aggregate_peak_z: Some(periodicity.aggregate_peak_z),
        long_block_phase_aligned_peak_z_minimum: Some(periodicity.aligned_peak_z_minimum),
        long_block_phase_aligned_peak_z_median: Some(periodicity.aligned_peak_z_median),
        long_block_phase_aggregate_peak_samples: Some(periodicity.aggregate_peak_samples),
        targeted_phase_verification: None,
        multi_candidate_phase_verification: None,
    })
}

fn targeted_phase_verification(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
    discovery_phase_samples: usize,
) -> Option<TargetedPhaseVerification> {
    const AUDIO_BLOCK_COUNT: usize = 4;
    const FRAMES_PER_PHASE: usize = 16;
    const CANDIDATE_RADIUS_SAMPLES: usize = 2;
    const CONTROL_PHASE_STRIDE_SAMPLES: usize = 60;
    const LOG_FLOOR: f64 = 1.0e-12;

    if discovery_phase_samples >= block_samples
        || !block_samples.is_multiple_of(CONTROL_PHASE_STRIDE_SAMPLES)
    {
        return None;
    }
    let input_samples = block_samples.checked_mul(2)?;
    let block_span = block_samples.checked_mul(FRAMES_PER_PHASE.checked_add(2)?)?;
    if samples.len() < block_span {
        return None;
    }
    let available_aligned_starts = (samples.len() - block_span) / block_samples;
    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let first_anchor = (frames_per_second / 2).min(available_aligned_starts);
    let anchor_span = available_aligned_starts - first_anchor;
    let block_indices = (0..AUDIO_BLOCK_COUNT)
        .map(|index| {
            first_anchor + index * anchor_span / AUDIO_BLOCK_COUNT.saturating_sub(1).max(1)
        })
        .collect::<BTreeSet<_>>();
    if block_indices.len() < 3 {
        return None;
    }

    let circular_distance = |left: usize, right: usize| {
        let direct = left.abs_diff(right);
        direct.min(block_samples - direct)
    };
    let control_phases = (0..block_samples)
        .step_by(CONTROL_PHASE_STRIDE_SAMPLES)
        .filter(|phase| {
            circular_distance(*phase, discovery_phase_samples) > CANDIDATE_RADIUS_SAMPLES + 1
        })
        .collect::<Vec<_>>();
    if control_phases.len() < 16 {
        return None;
    }
    let candidate_phases = (-(CANDIDATE_RADIUS_SAMPLES as isize)
        ..=CANDIDATE_RADIUS_SAMPLES as isize)
        .map(|offset| {
            (discovery_phase_samples as isize + offset).rem_euclid(block_samples as isize) as usize
        })
        .collect::<Vec<_>>();
    let difference_phases = control_phases
        .iter()
        .copied()
        .chain(candidate_phases.iter().copied())
        .collect::<BTreeSet<_>>();
    let energy_phases = difference_phases
        .iter()
        .flat_map(|phase| [*phase, *phase + 1])
        .collect::<BTreeSet<_>>();

    let mut output = vec![0.0_f32; block_samples];
    let mut scratch = vec![0.0_f32; mdct.get_scratch_len()];
    let mut peaks = Vec::with_capacity(block_indices.len());
    for block_index in block_indices {
        let anchor = block_index * block_samples;
        let mut energies = BTreeMap::new();
        for phase in energy_phases.iter().copied() {
            let mut energy = 0.0_f64;
            let mut measured_coefficients = 0_usize;
            for frame in 0..FRAMES_PER_PHASE {
                let start = anchor + frame * block_samples + phase;
                let middle = start + block_samples;
                let end = middle + block_samples;
                if end > samples.len() {
                    continue;
                }
                let input_a = &samples[start..middle];
                let input_b = &samples[middle..end];
                let rms = (input_a
                    .iter()
                    .chain(input_b)
                    .map(|sample| f64::from(*sample).powi(2))
                    .sum::<f64>()
                    / input_samples as f64)
                    .sqrt();
                if rms < 1.0e-5 {
                    continue;
                }
                mdct.process_mdct_with_scratch(input_a, input_b, &mut output, &mut scratch);
                let scale = (rms * block_samples as f64).max(LOG_FLOOR);
                energy += output
                    .iter()
                    .map(|coefficient| {
                        (f64::from(*coefficient).abs() / scale)
                            .max(LOG_FLOOR)
                            .log10()
                    })
                    .sum::<f64>();
                measured_coefficients += output.len();
            }
            if measured_coefficients > 0 {
                energies.insert(phase, energy / measured_coefficients as f64);
            }
        }
        if energies.len() != energy_phases.len() {
            continue;
        }
        let difference = |phase: usize| {
            energies
                .get(&(phase + 1))
                .zip(energies.get(&phase))
                .map(|(after, before)| after - before)
        };
        let control_differences = control_phases
            .iter()
            .filter_map(|phase| difference(*phase))
            .collect::<Vec<_>>();
        if control_differences.len() != control_phases.len() {
            continue;
        }
        let mean = control_differences.iter().sum::<f64>() / control_differences.len() as f64;
        let variance = control_differences
            .iter()
            .map(|value| (value - mean).powi(2))
            .sum::<f64>()
            / control_differences.len() as f64;
        let standard_deviation = variance.sqrt();
        if standard_deviation <= 1.0e-12 {
            continue;
        }
        let (phase_samples, z_score) = candidate_phases
            .iter()
            .filter_map(|phase| {
                difference(*phase).map(|value| (*phase, (value - mean) / standard_deviation))
            })
            .max_by(|left, right| left.1.total_cmp(&right.1))?;
        peaks.push(PhasePeak {
            phase_samples,
            z_score,
        });
    }
    if peaks.len() < 3 {
        return None;
    }

    let mut peak_z_scores = peaks.iter().map(|peak| peak.z_score).collect::<Vec<_>>();
    let peak_z_minimum = peak_z_scores.iter().copied().fold(f64::INFINITY, f64::min);
    let peak_z_median = median_option(&mut peak_z_scores)?;
    let (x, y, total_weight) =
        peaks
            .iter()
            .fold((0.0_f64, 0.0_f64, 0.0_f64), |(x, y, weight), peak| {
                let peak_weight = peak.z_score.max(0.0);
                let angle = TAU * peak.phase_samples as f64 / block_samples as f64;
                (
                    x + peak_weight * angle.cos(),
                    y + peak_weight * angle.sin(),
                    weight + peak_weight,
                )
            });
    let resultant = x.hypot(y);
    Some(TargetedPhaseVerification {
        discovery_phase_samples,
        candidate_radius_samples: CANDIDATE_RADIUS_SAMPLES,
        control_phase_stride_samples: CONTROL_PHASE_STRIDE_SAMPLES,
        audio_block_count: peaks.len(),
        frames_per_phase: FRAMES_PER_PHASE,
        peak_z_minimum,
        peak_z_median,
        peak_concentration: resultant / total_weight.max(LOG_FLOOR),
        consistent_peak_score: resultant / peaks.len() as f64,
    })
}

fn targeted_verification_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
) -> Option<TransformGridWindowProbe> {
    let mut probe =
        efficient_periodicity_window_probe(samples, sample_rate_hz, block_samples, mdct)?;
    let discovery_phase_samples = probe.long_block_phase_aggregate_peak_samples?;
    probe.targeted_phase_verification = targeted_phase_verification(
        samples,
        sample_rate_hz,
        block_samples,
        mdct,
        discovery_phase_samples,
    );
    Some(probe)
}

fn multi_candidate_phase_verification(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
    discovery_aggregate_phase_samples: usize,
    discovery_candidates: &[usize],
    control_phase_stride_samples: usize,
) -> Option<MultiCandidatePhaseVerification> {
    const AUDIO_BLOCK_COUNT: usize = 4;
    const FRAMES_PER_PHASE: usize = 16;
    const CANDIDATE_RADIUS_SAMPLES: usize = 2;
    const LOG_FLOOR: f64 = 1.0e-12;

    if discovery_aggregate_phase_samples >= block_samples
        || control_phase_stride_samples == 0
        || !block_samples.is_multiple_of(control_phase_stride_samples)
    {
        return None;
    }
    let mut base_candidates = discovery_candidates
        .iter()
        .copied()
        .filter(|phase| *phase < block_samples)
        .collect::<BTreeSet<_>>();
    base_candidates.insert(discovery_aggregate_phase_samples);
    if base_candidates.is_empty() {
        return None;
    }
    let candidate_phases = base_candidates
        .iter()
        .flat_map(|phase| {
            (-(CANDIDATE_RADIUS_SAMPLES as isize)..=CANDIDATE_RADIUS_SAMPLES as isize).map(
                |offset| (*phase as isize + offset).rem_euclid(block_samples as isize) as usize,
            )
        })
        .collect::<BTreeSet<_>>();
    let control_phases = (0..block_samples)
        .step_by(control_phase_stride_samples)
        .collect::<Vec<_>>();
    let difference_phases = control_phases
        .iter()
        .copied()
        .chain(candidate_phases.iter().copied())
        .collect::<BTreeSet<_>>();
    let energy_phases = difference_phases
        .iter()
        .flat_map(|phase| [*phase, *phase + 1])
        .collect::<BTreeSet<_>>();

    let input_samples = block_samples.checked_mul(2)?;
    let block_span = block_samples.checked_mul(FRAMES_PER_PHASE.checked_add(2)?)?;
    if samples.len() < block_span {
        return None;
    }
    let available_aligned_starts = (samples.len() - block_span) / block_samples;
    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let first_anchor = (frames_per_second / 2).min(available_aligned_starts);
    let anchor_span = available_aligned_starts - first_anchor;
    let block_indices = (0..AUDIO_BLOCK_COUNT)
        .map(|index| {
            first_anchor + index * anchor_span / AUDIO_BLOCK_COUNT.saturating_sub(1).max(1)
        })
        .collect::<BTreeSet<_>>();
    if block_indices.len() < 3 {
        return None;
    }

    let mut output = vec![0.0_f32; block_samples];
    let mut scratch = vec![0.0_f32; mdct.get_scratch_len()];
    let mut block_scores = Vec::with_capacity(block_indices.len());
    for block_index in block_indices {
        let anchor = block_index * block_samples;
        let mut energies = BTreeMap::new();
        for phase in energy_phases.iter().copied() {
            let mut energy = 0.0_f64;
            let mut measured_coefficients = 0_usize;
            for frame in 0..FRAMES_PER_PHASE {
                let start = anchor + frame * block_samples + phase;
                let middle = start + block_samples;
                let end = middle + block_samples;
                if end > samples.len() {
                    continue;
                }
                let input_a = &samples[start..middle];
                let input_b = &samples[middle..end];
                let rms = (input_a
                    .iter()
                    .chain(input_b)
                    .map(|sample| f64::from(*sample).powi(2))
                    .sum::<f64>()
                    / input_samples as f64)
                    .sqrt();
                if rms < 1.0e-5 {
                    continue;
                }
                mdct.process_mdct_with_scratch(input_a, input_b, &mut output, &mut scratch);
                let scale = (rms * block_samples as f64).max(LOG_FLOOR);
                energy += output
                    .iter()
                    .map(|coefficient| {
                        (f64::from(*coefficient).abs() / scale)
                            .max(LOG_FLOOR)
                            .log10()
                    })
                    .sum::<f64>();
                measured_coefficients += output.len();
            }
            if measured_coefficients > 0 {
                energies.insert(phase, energy / measured_coefficients as f64);
            }
        }
        if energies.len() != energy_phases.len() {
            continue;
        }
        let difference = |phase: usize| {
            energies
                .get(&(phase + 1))
                .zip(energies.get(&phase))
                .map(|(after, before)| after - before)
        };
        let control_differences = control_phases
            .iter()
            .filter_map(|phase| difference(*phase))
            .collect::<Vec<_>>();
        if control_differences.len() != control_phases.len() {
            continue;
        }
        let mean = control_differences.iter().sum::<f64>() / control_differences.len() as f64;
        let variance = control_differences
            .iter()
            .map(|value| (value - mean).powi(2))
            .sum::<f64>()
            / control_differences.len() as f64;
        let standard_deviation = variance.sqrt();
        if standard_deviation <= 1.0e-12 {
            continue;
        }
        block_scores.push(
            candidate_phases
                .iter()
                .filter_map(|phase| {
                    difference(*phase).map(|value| (*phase, (value - mean) / standard_deviation))
                })
                .collect::<BTreeMap<_, _>>(),
        );
    }
    if block_scores.len() < 3 {
        return None;
    }

    let mut best: Option<(f64, f64, f64, usize, Vec<f64>)> = None;
    for phase in candidate_phases {
        let values = block_scores
            .iter()
            .filter_map(|scores| scores.get(&phase).copied())
            .collect::<Vec<_>>();
        if values.len() != block_scores.len() {
            continue;
        }
        let mut values_for_median = values.clone();
        let median = median_option(&mut values_for_median)?;
        let minimum = values.iter().copied().fold(f64::INFINITY, f64::min);
        let mean = values.iter().sum::<f64>() / values.len() as f64;
        let rank = (median, minimum, mean);
        if best.as_ref().is_none_or(|current| {
            rank.0.total_cmp(&current.0).is_gt()
                || (rank.0.total_cmp(&current.0).is_eq()
                    && (rank.1.total_cmp(&current.1).is_gt()
                        || (rank.1.total_cmp(&current.1).is_eq()
                            && rank.2.total_cmp(&current.2).is_gt())))
        }) {
            best = Some((median, minimum, mean, phase, values));
        }
    }
    let (peak_z_median, peak_z_minimum, consistent_peak_score, verified_phase, _) = best?;
    Some(MultiCandidatePhaseVerification {
        discovery_aggregate_phase_samples,
        discovery_candidate_count: base_candidates.len(),
        verified_phase_samples: verified_phase,
        candidate_radius_samples: CANDIDATE_RADIUS_SAMPLES,
        control_phase_stride_samples,
        audio_block_count: block_scores.len(),
        frames_per_phase: FRAMES_PER_PHASE,
        peak_z_minimum,
        peak_z_median,
        consistent_peak_score,
    })
}

fn multi_candidate_verification_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
    control_phase_stride_samples: usize,
) -> Option<TransformGridWindowProbe> {
    const AUDIO_BLOCK_COUNT: usize = 10;
    const MINIMUM_PEAK_COUNT: usize = 5;

    let frames_per_second = usize::try_from(sample_rate_hz)
        .ok()?
        .div_ceil(block_samples)
        .clamp(8, 64);
    let periodicity = phase_periodicity_probe(
        samples,
        block_samples,
        mdct,
        AUDIO_BLOCK_COUNT,
        1,
        1,
        1,
        Some(frames_per_second),
        MINIMUM_PEAK_COUNT,
    )?;
    let candidates = &periodicity.peak_phase_samples[..periodicity.peak_phase_count];
    let verification = multi_candidate_phase_verification(
        samples,
        sample_rate_hz,
        block_samples,
        mdct,
        periodicity.aggregate_peak_samples,
        candidates,
        control_phase_stride_samples,
    );
    let mut probe = periodicity_window_probe(block_samples, periodicity);
    probe.multi_candidate_phase_verification = verification;
    Some(probe)
}

fn modified_bessel_i0(value: f64) -> f64 {
    let squared_quarter = value * value * 0.25;
    let mut sum = 1.0_f64;
    let mut term = 1.0_f64;
    for order in 1..=64 {
        term *= squared_quarter / (order * order) as f64;
        sum += term;
        if term <= sum * 1.0e-15 {
            break;
        }
    }
    sum
}

fn kbd_window(length: usize, alpha: f64) -> Vec<f32> {
    assert!(length.is_multiple_of(2));
    let half = length / 2;
    let alpha_scale = 4.0 * (alpha * std::f64::consts::PI / half as f64).powi(2);
    let mut kernel = Vec::with_capacity(half / 2 + 1);
    let mut total = 0.0_f64;
    for index in 0..=half / 2 {
        let value = modified_bessel_i0(((index * (half - index)) as f64 * alpha_scale).sqrt());
        kernel.push(value);
        total += value * (1 + usize::from(index > 0 && index < half / 2)) as f64;
    }
    let scale = 1.0 / (total + 1.0);
    let mut cumulative = 0.0_f64;
    let mut first_half = Vec::with_capacity(half);
    for index in 0..half {
        cumulative += kernel[index.min(half - index)];
        first_half.push((cumulative * scale).sqrt() as f32);
    }
    let mut output = Vec::with_capacity(length);
    output.extend_from_slice(&first_half);
    output.extend(first_half.iter().rev().copied());
    debug_assert!((0..half).all(|index| {
        (output[index] * output[index] + output[index + half] * output[index + half] - 1.0).abs()
            < 1.0e-5
    }));
    output
}

fn celt_low_overlap_window(length: usize, overlap: usize) -> Vec<f32> {
    assert!(length.is_multiple_of(2));
    let block_samples = length / 2;
    assert!(overlap > 0 && overlap <= block_samples);
    assert!((block_samples - overlap).is_multiple_of(2));

    // Opus' reference mode at 48 kHz uses a 120-sample overlap for both its
    // 960-bin long MDCT and 120-bin short MDCT. The ramp formula is the one
    // generated in celt/modes.c; the zero/flat regions turn that ramp into
    // the full 2N Princen-Bradley window expected by rustdct.
    let ramp: Vec<f32> = (0..overlap)
        .map(|index| {
            let phase = 0.5 * std::f64::consts::PI * (index as f64 + 0.5) / overlap as f64;
            (0.5 * std::f64::consts::PI * phase.sin().powi(2)).sin() as f32
        })
        .collect();
    let padding = (block_samples - overlap) / 2;
    let mut output = Vec::with_capacity(length);
    output.extend(std::iter::repeat_n(0.0, padding));
    output.extend_from_slice(&ramp);
    output.extend(std::iter::repeat_n(1.0, block_samples - overlap));
    output.extend(ramp.iter().rev().copied());
    output.extend(std::iter::repeat_n(0.0, padding));
    debug_assert_eq!(output.len(), length);
    debug_assert!((0..block_samples).all(|index| {
        (output[index] * output[index]
            + output[index + block_samples] * output[index + block_samples]
            - 1.0)
            .abs()
            < 1.0e-5
    }));
    output
}

fn research_periodicity_window_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    block_samples: usize,
    mdct: &dyn Mdct<f32>,
    profile: TransformGridProfile,
) -> Option<TransformGridWindowProbe> {
    match profile {
        TransformGridProfile::AlignedPeriodicityV22
        | TransformGridProfile::BalancedOpusPeriodicityV24
        | TransformGridProfile::ConservativeTwoGridV28
        | TransformGridProfile::EfficientPeriodicityV18
        | TransformGridProfile::HybridOpusPeriodicityV23
        | TransformGridProfile::MultiCandidateVerificationV26
        | TransformGridProfile::OpusDualGridV27
        | TransformGridProfile::TargetedVerificationV25
        | TransformGridProfile::VerifiedMp3TwoGridV29
        | TransformGridProfile::VerifiedAacMp3FourGridV30
        | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
        | TransformGridProfile::Mp3FrameVerificationV31 => {
            efficient_periodicity_window_probe(samples, sample_rate_hz, block_samples, mdct)
        }
        TransformGridProfile::SampledPeriodicityV19 => {
            sampled_periodicity_window_probe(samples, sample_rate_hz, block_samples, mdct, 1)
        }
        TransformGridProfile::SubsampledPeriodicityV20 => {
            sampled_periodicity_window_probe(samples, sample_rate_hz, block_samples, mdct, 4)
        }
        _ => unreachable!("research periodicity profile required"),
    }
}

fn parallel_periodicity_transform_grid_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    profile: TransformGridProfile,
) -> TransformGridProbe {
    std::thread::scope(|scope| {
        let mp3 = scope.spawn(|| {
            let mut planner = DctPlanner::new();
            if matches!(profile, TransformGridProfile::Mp3FrameVerificationV31) {
                let mdct = planner.plan_mdct(1_152, window_fn::mp3);
                return multi_candidate_verification_window_probe(
                    samples,
                    sample_rate_hz,
                    1_152,
                    mdct.as_ref(),
                    48,
                );
            }
            let mdct = planner.plan_mdct(576, window_fn::mp3);
            if matches!(
                profile,
                TransformGridProfile::VerifiedMp3TwoGridV29
                    | TransformGridProfile::VerifiedAacMp3FourGridV30
                    | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
            ) {
                multi_candidate_verification_window_probe(
                    samples,
                    sample_rate_hz,
                    576,
                    mdct.as_ref(),
                    24,
                )
            } else {
                research_periodicity_window_probe(
                    samples,
                    sample_rate_hz,
                    576,
                    mdct.as_ref(),
                    profile,
                )
            }
        });
        let long_sine = scope.spawn(|| {
            if !matches!(
                profile,
                TransformGridProfile::VerifiedAacMp3FourGridV30
                    | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
            ) {
                return None;
            }
            let mut planner = DctPlanner::new();
            let mdct = planner.plan_mdct(1_024, window_fn::mp3);
            multi_candidate_verification_window_probe(
                samples,
                sample_rate_hz,
                1_024,
                mdct.as_ref(),
                32,
            )
        });
        let long_kbd = scope.spawn(|| {
            if !matches!(profile, TransformGridProfile::VerifiedAacMp3FourGridV30) {
                return None;
            }
            let mut planner = DctPlanner::new();
            let mdct = planner.plan_mdct(1_024, |length| kbd_window(length, 4.0));
            multi_candidate_verification_window_probe(
                samples,
                sample_rate_hz,
                1_024,
                mdct.as_ref(),
                32,
            )
        });
        let vorbis = scope.spawn(|| {
            let mut planner = DctPlanner::new();
            let mdct = planner.plan_mdct(1_024, window_fn::vorbis);
            research_periodicity_window_probe(
                samples,
                sample_rate_hz,
                1_024,
                mdct.as_ref(),
                profile,
            )
        });
        let opus = scope.spawn(|| {
            if matches!(
                profile,
                TransformGridProfile::ConservativeTwoGridV28
                    | TransformGridProfile::VerifiedMp3TwoGridV29
                    | TransformGridProfile::VerifiedAacMp3FourGridV30
                    | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
                    | TransformGridProfile::Mp3FrameVerificationV31
            ) {
                return (None, None);
            }
            let mut planner = DctPlanner::new();
            let mdct = planner.plan_mdct(960, |length| celt_low_overlap_window(length, 120));
            let long = match profile {
                TransformGridProfile::HybridOpusPeriodicityV23 => {
                    coarse_long_periodicity_window_probe(
                        samples,
                        sample_rate_hz,
                        960,
                        mdct.as_ref(),
                    )
                }
                TransformGridProfile::BalancedOpusPeriodicityV24 => {
                    balanced_opus_periodicity_window_probe(
                        samples,
                        sample_rate_hz,
                        960,
                        mdct.as_ref(),
                    )
                }
                TransformGridProfile::TargetedVerificationV25 => {
                    targeted_verification_window_probe(samples, sample_rate_hz, 960, mdct.as_ref())
                }
                TransformGridProfile::MultiCandidateVerificationV26 => {
                    multi_candidate_verification_window_probe(
                        samples,
                        sample_rate_hz,
                        960,
                        mdct.as_ref(),
                        30,
                    )
                }
                _ => research_periodicity_window_probe(
                    samples,
                    sample_rate_hz,
                    960,
                    mdct.as_ref(),
                    profile,
                ),
            };
            let short = if matches!(profile, TransformGridProfile::OpusDualGridV27) {
                let mut short_planner = DctPlanner::new();
                let short_mdct =
                    short_planner.plan_mdct(120, |length| celt_low_overlap_window(length, 120));
                efficient_periodicity_window_probe(
                    samples,
                    sample_rate_hz,
                    120,
                    short_mdct.as_ref(),
                )
            } else {
                None
            };
            (long, short)
        });
        let (opus_long_celt, opus_short_celt) = opus.join().expect("Opus research probe panicked");
        TransformGridProbe {
            mp3_long_sine: mp3.join().expect("MP3 research probe panicked"),
            long_sine: long_sine.join().expect("AAC sine research probe panicked"),
            long_kbd: long_kbd.join().expect("AAC KBD research probe panicked"),
            long_vorbis: vorbis.join().expect("Vorbis research probe panicked"),
            opus_long_celt,
            opus_short_celt,
        }
    })
}

fn transform_grid_probe(
    samples: &[f32],
    sample_rate_hz: u32,
    profile: TransformGridProfile,
) -> TransformGridProbe {
    if matches!(
        profile,
        TransformGridProfile::AlignedPeriodicityV22
            | TransformGridProfile::BalancedOpusPeriodicityV24
            | TransformGridProfile::ConservativeTwoGridV28
            | TransformGridProfile::EfficientPeriodicityV18
            | TransformGridProfile::HybridOpusPeriodicityV23
            | TransformGridProfile::MultiCandidateVerificationV26
            | TransformGridProfile::OpusDualGridV27
            | TransformGridProfile::SampledPeriodicityV19
            | TransformGridProfile::SubsampledPeriodicityV20
            | TransformGridProfile::TargetedVerificationV25
            | TransformGridProfile::VerifiedMp3TwoGridV29
            | TransformGridProfile::VerifiedAacMp3FourGridV30
            | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
            | TransformGridProfile::Mp3FrameVerificationV31
    ) {
        return parallel_periodicity_transform_grid_probe(samples, sample_rate_hz, profile);
    }

    let long_block_profile = match profile {
        TransformGridProfile::LongBlockV17 => LongBlockProfile::TenNonOverlapping,
        TransformGridProfile::AlignedPeriodicityV22
        | TransformGridProfile::BalancedOpusPeriodicityV24
        | TransformGridProfile::ConservativeTwoGridV28
        | TransformGridProfile::EfficientPeriodicityV18
        | TransformGridProfile::Full
        | TransformGridProfile::HybridOpusPeriodicityV23
        | TransformGridProfile::LongBlockV16
        | TransformGridProfile::MultiCandidateVerificationV26
        | TransformGridProfile::OpusDualGridV27
        | TransformGridProfile::SampledPeriodicityV19
        | TransformGridProfile::StableV15
        | TransformGridProfile::SubsampledPeriodicityV20
        | TransformGridProfile::TargetedVerificationV25
        | TransformGridProfile::VerifiedMp3TwoGridV29
        | TransformGridProfile::VerifiedAacMp3FourGridV30
        | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
        | TransformGridProfile::Mp3FrameVerificationV31 => LongBlockProfile::LegacyFourEvenlySpaced,
    };
    let mut mp3_long_sine_planner = DctPlanner::new();
    let mp3_long_sine = mp3_long_sine_planner.plan_mdct(576, window_fn::mp3);
    let mut long_vorbis_planner = DctPlanner::new();
    let long_vorbis = long_vorbis_planner.plan_mdct(1_024, window_fn::vorbis);
    let mp3_long_sine = match profile {
        TransformGridProfile::AlignedPeriodicityV22
        | TransformGridProfile::BalancedOpusPeriodicityV24
        | TransformGridProfile::ConservativeTwoGridV28
        | TransformGridProfile::EfficientPeriodicityV18
        | TransformGridProfile::HybridOpusPeriodicityV23
        | TransformGridProfile::MultiCandidateVerificationV26
        | TransformGridProfile::OpusDualGridV27
        | TransformGridProfile::TargetedVerificationV25
        | TransformGridProfile::VerifiedMp3TwoGridV29
        | TransformGridProfile::VerifiedAacMp3FourGridV30
        | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
        | TransformGridProfile::Mp3FrameVerificationV31 => {
            efficient_periodicity_window_probe(samples, sample_rate_hz, 576, mp3_long_sine.as_ref())
        }
        _ => transform_grid_window_probe(
            samples,
            sample_rate_hz,
            576,
            mp3_long_sine.as_ref(),
            long_block_profile,
        ),
    };
    let long_vorbis = match profile {
        TransformGridProfile::AlignedPeriodicityV22
        | TransformGridProfile::BalancedOpusPeriodicityV24
        | TransformGridProfile::ConservativeTwoGridV28
        | TransformGridProfile::EfficientPeriodicityV18
        | TransformGridProfile::HybridOpusPeriodicityV23
        | TransformGridProfile::MultiCandidateVerificationV26
        | TransformGridProfile::OpusDualGridV27
        | TransformGridProfile::TargetedVerificationV25
        | TransformGridProfile::VerifiedMp3TwoGridV29
        | TransformGridProfile::VerifiedAacMp3FourGridV30
        | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
        | TransformGridProfile::Mp3FrameVerificationV31 => {
            efficient_periodicity_window_probe(samples, sample_rate_hz, 1_024, long_vorbis.as_ref())
        }
        _ => transform_grid_window_probe(
            samples,
            sample_rate_hz,
            1_024,
            long_vorbis.as_ref(),
            long_block_profile,
        ),
    };
    match profile {
        TransformGridProfile::AlignedPeriodicityV22
        | TransformGridProfile::BalancedOpusPeriodicityV24
        | TransformGridProfile::ConservativeTwoGridV28
        | TransformGridProfile::EfficientPeriodicityV18
        | TransformGridProfile::HybridOpusPeriodicityV23
        | TransformGridProfile::MultiCandidateVerificationV26
        | TransformGridProfile::OpusDualGridV27
        | TransformGridProfile::TargetedVerificationV25
        | TransformGridProfile::VerifiedMp3TwoGridV29
        | TransformGridProfile::VerifiedAacMp3FourGridV30
        | TransformGridProfile::VerifiedAacSineMp3ThreeGridV30
        | TransformGridProfile::Mp3FrameVerificationV31 => {
            let mut opus_long_celt_planner = DctPlanner::new();
            let opus_long_celt = opus_long_celt_planner
                .plan_mdct(960, |length| celt_low_overlap_window(length, 120));
            TransformGridProbe {
                mp3_long_sine,
                long_sine: None,
                long_kbd: None,
                long_vorbis,
                opus_long_celt: efficient_periodicity_window_probe(
                    samples,
                    sample_rate_hz,
                    960,
                    opus_long_celt.as_ref(),
                ),
                opus_short_celt: None,
            }
        }
        TransformGridProfile::SampledPeriodicityV19
        | TransformGridProfile::SubsampledPeriodicityV20 => {
            unreachable!("returned above")
        }
        TransformGridProfile::StableV15 => TransformGridProbe {
            mp3_long_sine,
            long_sine: None,
            long_kbd: None,
            long_vorbis,
            opus_long_celt: None,
            opus_short_celt: None,
        },
        TransformGridProfile::LongBlockV16 | TransformGridProfile::LongBlockV17 => {
            let mut opus_long_celt_planner = DctPlanner::new();
            let opus_long_celt = opus_long_celt_planner
                .plan_mdct(960, |length| celt_low_overlap_window(length, 120));
            TransformGridProbe {
                mp3_long_sine,
                long_sine: None,
                long_kbd: None,
                long_vorbis,
                opus_long_celt: transform_grid_window_probe(
                    samples,
                    sample_rate_hz,
                    960,
                    opus_long_celt.as_ref(),
                    long_block_profile,
                ),
                opus_short_celt: None,
            }
        }
        TransformGridProfile::Full => {
            let mut long_sine_planner = DctPlanner::new();
            let long_sine = long_sine_planner.plan_mdct(1_024, window_fn::mp3);
            let mut long_kbd_planner = DctPlanner::new();
            let long_kbd = long_kbd_planner.plan_mdct(1_024, |length| kbd_window(length, 4.0));
            let mut opus_long_celt_planner = DctPlanner::new();
            let opus_long_celt = opus_long_celt_planner
                .plan_mdct(960, |length| celt_low_overlap_window(length, 120));
            TransformGridProbe {
                mp3_long_sine,
                long_sine: transform_grid_window_probe(
                    samples,
                    sample_rate_hz,
                    1_024,
                    long_sine.as_ref(),
                    long_block_profile,
                ),
                long_kbd: transform_grid_window_probe(
                    samples,
                    sample_rate_hz,
                    1_024,
                    long_kbd.as_ref(),
                    long_block_profile,
                ),
                long_vorbis,
                opus_long_celt: transform_grid_window_probe(
                    samples,
                    sample_rate_hz,
                    960,
                    opus_long_celt.as_ref(),
                    long_block_profile,
                ),
                opus_short_celt: None,
            }
        }
    }
}

fn decode(path: &Path, max_seconds: Option<f64>) -> Result<DecodedAudio, String> {
    let file = File::open(path).map_err(|error| format!("open {}: {error}", path.display()))?;
    let source = MediaSourceStream::new(Box::new(file), Default::default());
    let mut hint = Hint::new();
    if let Some(extension) = path.extension().and_then(|value| value.to_str()) {
        hint.with_extension(extension);
    }
    let probed = get_probe()
        .format(
            &hint,
            source,
            &FormatOptions::default(),
            &MetadataOptions::default(),
        )
        .map_err(|error| format!("probe {}: {error}", path.display()))?;
    let mut reader = probed.format;
    let track = reader
        .default_track()
        .ok_or_else(|| format!("no default audio track in {}", path.display()))?;
    let track_id = track.id;
    let sample_rate = track
        .codec_params
        .sample_rate
        .ok_or_else(|| format!("missing sample rate in {}", path.display()))?;
    let source_facts = SourceFacts {
        sample_rate_hz: sample_rate,
        channel_count: track.codec_params.channels.map(|channels| channels.count()),
        declared_bits_per_sample: track.codec_params.bits_per_sample,
        codec_debug: format!("{:?}", track.codec_params.codec),
        container_extension: path
            .extension()
            .and_then(|value| value.to_str())
            .map(str::to_ascii_lowercase),
    };
    let mut decoder = symphonia::default::get_codecs()
        .make(&track.codec_params, &DecoderOptions::default())
        .map_err(|error| format!("decoder: {error}"))?;
    let sample_limit = max_seconds
        .map(|seconds| (seconds * f64::from(sample_rate)) as usize)
        .unwrap_or(usize::MAX);
    let initial_capacity = sample_limit.min(sample_rate as usize * 60);
    let mut samples = Vec::with_capacity(initial_capacity);
    let mut side_samples = Vec::with_capacity(initial_capacity);
    while samples.len() < sample_limit {
        let packet = match reader.next_packet() {
            Ok(packet) => packet,
            Err(symphonia::core::errors::Error::IoError(error))
                if error.kind() == std::io::ErrorKind::UnexpectedEof =>
            {
                break;
            }
            Err(error) => return Err(format!("read packet: {error}")),
        };
        if packet.track_id() != track_id {
            continue;
        }
        match decoder.decode(&packet) {
            Ok(decoded) => downmix(&decoded, &mut samples, &mut side_samples),
            Err(symphonia::core::errors::Error::DecodeError(_)) => continue,
            Err(error) => return Err(format!("decode packet: {error}")),
        }
    }
    samples.truncate(sample_limit);
    side_samples.truncate(sample_limit);
    if samples.is_empty() {
        return Err(format!(
            "decoded zero audio samples from {}",
            path.display()
        ));
    }
    Ok(DecodedAudio {
        side_samples: (source_facts.channel_count == Some(2)
            && side_samples.len() == samples.len())
        .then_some(side_samples),
        samples,
        source_facts,
    })
}

fn analyze_timed(
    samples: &[f32],
    sample_rate: u32,
    prototype_enabled: bool,
) -> Result<(f64, Option<CompressionTraceFeatures>), String> {
    let started = Instant::now();
    let analysis = analyze_audio(
        samples,
        sample_rate,
        AnalysisConfig {
            enable_compression_trace_prototype: prototype_enabled,
            ..AnalysisConfig::default()
        },
    )
    .map_err(|error| error.to_string())?;
    Ok((
        started.elapsed().as_secs_f64() * 1_000.0,
        analysis.compression_trace_prototype,
    ))
}

fn median(mut values: Vec<f64>) -> Result<f64, String> {
    if values.is_empty() {
        return Err("cannot compute median of an empty timing set".to_string());
    }
    values.sort_by(f64::total_cmp);
    let midpoint = values.len() / 2;
    if values.len().is_multiple_of(2) {
        Ok((values[midpoint - 1] + values[midpoint]) / 2.0)
    } else {
        Ok(values[midpoint])
    }
}

fn requested_transform_grid_profile() -> Result<Option<TransformGridProfile>, String> {
    if std::env::var("LOSSYTRACE_RESEARCH_SKIP_TRANSFORM_GRID").as_deref() == Ok("1") {
        return Ok(None);
    }
    match std::env::var("LOSSYTRACE_RESEARCH_TRANSFORM_GRID_PROFILE").as_deref() {
        Ok("aligned-periodicity-v22") => Ok(Some(TransformGridProfile::AlignedPeriodicityV22)),
        Ok("balanced-opus-periodicity-v24") => {
            Ok(Some(TransformGridProfile::BalancedOpusPeriodicityV24))
        }
        Ok("conservative-two-grid-v28") => Ok(Some(TransformGridProfile::ConservativeTwoGridV28)),
        Ok("efficient-periodicity-v18") => Ok(Some(TransformGridProfile::EfficientPeriodicityV18)),
        Ok("hybrid-opus-periodicity-v23") => {
            Ok(Some(TransformGridProfile::HybridOpusPeriodicityV23))
        }
        Ok("long-block-v16") => Ok(Some(TransformGridProfile::LongBlockV16)),
        Ok("long-block-v17") => Ok(Some(TransformGridProfile::LongBlockV17)),
        Ok("multi-candidate-verification-v26") => {
            Ok(Some(TransformGridProfile::MultiCandidateVerificationV26))
        }
        Ok("opus-dual-grid-v27") => Ok(Some(TransformGridProfile::OpusDualGridV27)),
        Ok("verified-mp3-two-grid-v29") => Ok(Some(TransformGridProfile::VerifiedMp3TwoGridV29)),
        Ok("verified-aac-mp3-four-grid-v30") => {
            Ok(Some(TransformGridProfile::VerifiedAacMp3FourGridV30))
        }
        Ok("verified-aac-sine-mp3-three-grid-v30") => {
            Ok(Some(TransformGridProfile::VerifiedAacSineMp3ThreeGridV30))
        }
        Ok("mp3-frame-verification-v31") => Ok(Some(TransformGridProfile::Mp3FrameVerificationV31)),
        Ok("sampled-periodicity-v19") => Ok(Some(TransformGridProfile::SampledPeriodicityV19)),
        Ok("stable-v15") => Ok(Some(TransformGridProfile::StableV15)),
        Ok("subsampled-periodicity-v20") => {
            Ok(Some(TransformGridProfile::SubsampledPeriodicityV20))
        }
        Ok("targeted-verification-v25") => Ok(Some(TransformGridProfile::TargetedVerificationV25)),
        Ok("full") | Err(std::env::VarError::NotPresent) => Ok(Some(TransformGridProfile::Full)),
        Ok(value) => Err(format!("unsupported transform-grid profile: {value}")),
        Err(error) => Err(format!(
            "read transform-grid profile environment variable: {error}"
        )),
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = std::env::args().collect();
    if !matches!(args.len(), 6 | 7) {
        return Err(
            "usage: audio_integrity_benchmark CASE_ID AUDIO_PATH MAX_SECONDS_OR_0 REPETITIONS feature-version=0 [memory-mode=baseline|memory-mode=prototype|research-mode=transform-only]"
                .to_string(),
        );
    }
    let case_id = args[1].clone();
    let audio_path = Path::new(&args[2]);
    let max_seconds = args[3]
        .parse::<f64>()
        .map_err(|error| format!("MAX_SECONDS_OR_0: {error}"))?;
    if !max_seconds.is_finite() || max_seconds < 0.0 {
        return Err("MAX_SECONDS_OR_0 must be finite and non-negative".to_string());
    }
    let max_seconds = (max_seconds > 0.0).then_some(max_seconds);
    let repetitions = args[4]
        .parse::<usize>()
        .map_err(|error| format!("REPETITIONS: {error}"))?;
    if repetitions == 0 || repetitions > 20 {
        return Err("REPETITIONS must be in 1..=20".to_string());
    }
    if args[5] != format!("feature-version={COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION}") {
        return Err(format!(
            "expected final guard argument feature-version={COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION}"
        ));
    }
    let transform_only = args.get(6).map(String::as_str) == Some("research-mode=transform-only");
    let memory_mode = match args.get(6).map(String::as_str) {
        None => None,
        Some("memory-mode=baseline") => Some(false),
        Some("memory-mode=prototype") => Some(true),
        Some("research-mode=transform-only") => None,
        Some(_) => {
            return Err(
                "optional mode must be memory-mode=baseline, memory-mode=prototype, or research-mode=transform-only"
                    .to_string(),
            );
        }
    };

    let decoded = decode(audio_path, max_seconds)?;
    if transform_only {
        let profile = requested_transform_grid_profile()?
            .ok_or_else(|| "transform-only mode requires an enabled transform grid".to_string())?;
        let started_at = Instant::now();
        let transform_grid_probe = transform_grid_probe(
            &decoded.samples,
            decoded.source_facts.sample_rate_hz,
            profile,
        );
        let output = TransformOnlyRunResult {
            schema_version: 1,
            case_id,
            audio_sha256: sha256_file(audio_path)?,
            decoded_sample_count: decoded.samples.len(),
            decoded_duration_seconds: decoded.samples.len() as f64
                / f64::from(decoded.source_facts.sample_rate_hz),
            source_facts: decoded.source_facts,
            research_transform_grid_profile: profile.name(),
            research_transform_grid_elapsed_ms: started_at.elapsed().as_secs_f64() * 1_000.0,
            transform_grid_probe,
        };
        println!(
            "{}",
            serde_json::to_string(&output).map_err(|error| error.to_string())?
        );
        return Ok(());
    }
    if let Some(prototype_enabled) = memory_mode {
        let (_, compression_trace) = analyze_timed(
            &decoded.samples,
            decoded.source_facts.sample_rate_hz,
            prototype_enabled,
        )?;
        if let Some(measured) = &compression_trace {
            measured.validate().map_err(|error| error.to_string())?;
        }
        if compression_trace.is_some() != prototype_enabled {
            return Err("memory-mode prototype measurement state differs".to_string());
        }
        let output = MemoryRunResult {
            schema_version: 1,
            case_id,
            audio_sha256: sha256_file(audio_path)?,
            decoded_sample_count: decoded.samples.len(),
            decoded_duration_seconds: decoded.samples.len() as f64
                / f64::from(decoded.source_facts.sample_rate_hz),
            prototype_enabled,
            feature_version: COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION,
            compression_trace_measured: compression_trace.is_some(),
        };
        println!(
            "{}",
            serde_json::to_string(&output).map_err(|error| error.to_string())?
        );
        return Ok(());
    }
    let mut baseline_times_ms = Vec::with_capacity(repetitions);
    let mut prototype_times_ms = Vec::with_capacity(repetitions);
    let mut compression_trace: Option<CompressionTraceFeatures> = None;
    for repetition in 0..repetitions {
        let ordered = if repetition % 2 == 0 {
            [false, true]
        } else {
            [true, false]
        };
        for prototype_enabled in ordered {
            let (elapsed_ms, measured) = analyze_timed(
                &decoded.samples,
                decoded.source_facts.sample_rate_hz,
                prototype_enabled,
            )?;
            if prototype_enabled {
                let measured = measured
                    .ok_or_else(|| "prototype analysis returned no measurements".to_string())?;
                if let Some(previous) = &compression_trace {
                    if previous != &measured {
                        return Err(
                            "prototype measurements changed between repetitions".to_string()
                        );
                    }
                } else {
                    compression_trace = Some(measured);
                }
                prototype_times_ms.push(elapsed_ms);
            } else {
                if measured.is_some() {
                    return Err("baseline unexpectedly returned prototype measurements".to_string());
                }
                baseline_times_ms.push(elapsed_ms);
            }
        }
    }
    let baseline_median_ms = median(baseline_times_ms.clone())?;
    let prototype_median_ms = median(prototype_times_ms.clone())?;
    let runtime_overhead_percent = if baseline_median_ms > 0.0 {
        (prototype_median_ms / baseline_median_ms - 1.0) * 100.0
    } else {
        0.0
    };
    let compression_trace = compression_trace.ok_or_else(|| "prototype did not run".to_string())?;
    compression_trace
        .validate()
        .map_err(|error| error.to_string())?;
    let stereo_trace = decoded.side_samples.as_ref().and_then(|side_samples| {
        stereo_trace(
            &decoded.samples,
            side_samples,
            decoded.source_facts.sample_rate_hz,
        )
    });
    let research_transform_grid_profile = requested_transform_grid_profile()?;
    let research_transform_grid_enabled = research_transform_grid_profile.is_some();
    let (transform_grid_probe, research_transform_grid_elapsed_ms) =
        if let Some(profile) = research_transform_grid_profile {
            let started_at = Instant::now();
            let probe = transform_grid_probe(
                &decoded.samples,
                decoded.source_facts.sample_rate_hz,
                profile,
            );
            (
                Some(probe),
                Some(started_at.elapsed().as_secs_f64() * 1_000.0),
            )
        } else {
            (None, None)
        };
    let research_total_runtime_overhead_percent = if baseline_median_ms > 0.0 {
        let transform_ms = research_transform_grid_elapsed_ms.unwrap_or(0.0);
        ((prototype_median_ms + transform_ms) / baseline_median_ms - 1.0) * 100.0
    } else {
        0.0
    };

    let output = BenchmarkResult {
        schema_version: 1,
        case_id,
        audio_sha256: sha256_file(audio_path)?,
        decoded_sample_count: decoded.samples.len(),
        decoded_duration_seconds: decoded.samples.len() as f64
            / f64::from(decoded.source_facts.sample_rate_hz),
        source_facts: decoded.source_facts,
        repetitions,
        baseline_times_ms,
        prototype_times_ms,
        baseline_median_ms,
        prototype_median_ms,
        runtime_overhead_percent,
        feature_version: COMPRESSION_TRACE_PROTOTYPE_FEATURE_VERSION,
        compression_trace,
        stereo_trace,
        research_transform_grid_enabled,
        research_transform_grid_profile: research_transform_grid_profile
            .map(TransformGridProfile::name),
        research_transform_grid_elapsed_ms,
        research_total_runtime_overhead_percent,
        transform_grid_probe,
    };
    println!(
        "{}",
        serde_json::to_string(&output).map_err(|error| error.to_string())?
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stable_v15_reuses_the_full_profiles_selected_probes() {
        let samples = (0..(1_024 * 4))
            .map(|index| {
                let time = index as f32 / 44_100.0;
                (time * 440.0 * std::f32::consts::TAU).sin()
                    + 0.25 * (time * 7_137.0 * std::f32::consts::TAU).sin()
            })
            .collect::<Vec<_>>();
        // Four transform blocks exercise the stable/full selection and the
        // original short probe without paying for the long-block research
        // measurement in this unit test. Corpus runs use the full audio and its
        // decoded sample rate.
        let full = transform_grid_probe(&samples, 8_000, TransformGridProfile::Full);
        let stable = transform_grid_probe(&samples, 8_000, TransformGridProfile::StableV15);

        assert_eq!(stable.mp3_long_sine, full.mp3_long_sine);
        assert_eq!(stable.long_vorbis, full.long_vorbis);
        assert!(stable.long_sine.is_none());
        assert!(stable.long_kbd.is_none());
        assert!(stable.opus_long_celt.is_none());
    }

    #[test]
    fn efficient_periodicity_v18_omits_legacy_coefficient_grid() {
        let samples = (0_usize..32_000)
            .map(|index| {
                let time = index as f32 / 8_000.0;
                let deterministic_noise =
                    ((index.wrapping_mul(7_919) % 65_521) as f32 / 32_760.5) - 1.0;
                (time * 440.0 * std::f32::consts::TAU).sin() + 0.05 * deterministic_noise
            })
            .collect::<Vec<_>>();
        let probe = transform_grid_probe(
            &samples,
            8_000,
            TransformGridProfile::EfficientPeriodicityV18,
        );
        let conservative = transform_grid_probe(
            &samples,
            8_000,
            TransformGridProfile::ConservativeTwoGridV28,
        );

        for measurement in [
            probe.mp3_long_sine.as_ref(),
            probe.long_vorbis.as_ref(),
            probe.opus_long_celt.as_ref(),
        ]
        .into_iter()
        .flatten()
        {
            assert_eq!(measurement.nac_minimum, 0.0);
            assert_eq!(measurement.long_block_frames_per_phase, Some(1));
            assert!(measurement.long_block_audio_block_count.unwrap_or_default() >= 5);
            assert!(measurement
                .long_block_phase_peak_z_median
                .is_some_and(f64::is_finite));
        }
        assert!(probe.long_sine.is_none());
        assert!(probe.long_kbd.is_none());
        assert_eq!(conservative.mp3_long_sine, probe.mp3_long_sine);
        assert_eq!(conservative.long_vorbis, probe.long_vorbis);
        assert!(conservative.opus_long_celt.is_none());
        assert!(conservative.opus_short_celt.is_none());
    }

    #[test]
    fn verified_mp3_v29_is_a_two_grid_profile() {
        let mut noise_state = 0x9e37_79b9_u32;
        let samples = (0_usize..64_000)
            .map(|index| {
                noise_state ^= noise_state << 13;
                noise_state ^= noise_state >> 17;
                noise_state ^= noise_state << 5;
                let time = index as f32 / 8_000.0;
                let deterministic_noise = noise_state as f32 / u32::MAX as f32 * 2.0 - 1.0;
                (time * 440.0 * std::f32::consts::TAU).sin() + 0.05 * deterministic_noise
            })
            .collect::<Vec<_>>();
        let probe =
            transform_grid_probe(&samples, 8_000, TransformGridProfile::VerifiedMp3TwoGridV29);

        let mp3 = probe.mp3_long_sine.as_ref().expect("MP3 grid");
        assert!(mp3.long_block_phase_aggregate_peak_z.is_some());
        if let Some(verification) = &mp3.multi_candidate_phase_verification {
            assert_eq!(verification.control_phase_stride_samples, 24);
            assert!(verification.audio_block_count >= 3);
        }
        assert!(probe
            .long_vorbis
            .as_ref()
            .is_some_and(|measurement| measurement.multi_candidate_phase_verification.is_none()));
        assert!(probe.opus_long_celt.is_none());
        assert!(probe.opus_short_celt.is_none());
    }

    #[test]
    fn verified_aac_mp3_v30_verifies_both_aac_long_windows() {
        let mut noise_state = 0x243f_6a88_u32;
        let samples = (0_usize..64_000)
            .map(|index| {
                noise_state ^= noise_state << 13;
                noise_state ^= noise_state >> 17;
                noise_state ^= noise_state << 5;
                let time = index as f32 / 8_000.0;
                let deterministic_noise = noise_state as f32 / u32::MAX as f32 * 2.0 - 1.0;
                (time * 523.25 * std::f32::consts::TAU).sin() + 0.05 * deterministic_noise
            })
            .collect::<Vec<_>>();
        let probe = transform_grid_probe(
            &samples,
            8_000,
            TransformGridProfile::VerifiedAacMp3FourGridV30,
        );

        for measurement in [
            probe.long_sine.as_ref().expect("AAC sine grid"),
            probe.long_kbd.as_ref().expect("AAC KBD grid"),
        ] {
            assert!(measurement
                .multi_candidate_phase_verification
                .as_ref()
                .is_some_and(|verification| {
                    verification.control_phase_stride_samples == 32
                        && verification.audio_block_count >= 3
                }));
        }
        assert!(probe.mp3_long_sine.is_some());
        assert!(probe.long_vorbis.is_some());
        assert!(probe.opus_long_celt.is_none());
        assert!(probe.opus_short_celt.is_none());

        let three_grid = transform_grid_probe(
            &samples,
            8_000,
            TransformGridProfile::VerifiedAacSineMp3ThreeGridV30,
        );
        assert!(three_grid
            .long_sine
            .as_ref()
            .and_then(|measurement| { measurement.multi_candidate_phase_verification.as_ref() })
            .is_some());
        assert!(three_grid.long_kbd.is_none());
        assert!(three_grid.opus_long_celt.is_none());

        let mp3_frame = transform_grid_probe(
            &samples,
            8_000,
            TransformGridProfile::Mp3FrameVerificationV31,
        );
        let frame_measurement = mp3_frame.mp3_long_sine.as_ref().expect("MP3 frame grid");
        assert_eq!(frame_measurement.block_samples, 1_152);
        assert!(frame_measurement
            .multi_candidate_phase_verification
            .as_ref()
            .is_some_and(|verification| { verification.control_phase_stride_samples == 48 }));
        assert!(mp3_frame.long_sine.is_none());
        assert!(mp3_frame.long_kbd.is_none());
        assert!(mp3_frame.opus_long_celt.is_none());
    }
}
