use std::io::{self, Read};

use oxideav_mp3::analysis::{analyze_granule, AnalysisState};
use oxideav_mp3::mdct::{forward_overlap, mdct, window_long_family_analysis, MdctState};
use oxideav_mp3::side_info::BlockType;
use serde::Serialize;

const GRANULE_SAMPLES: usize = 576;
const SUBBAND_COUNT: usize = 32;
const COEFFICIENTS_PER_SUBBAND: usize = 18;
const COEFFICIENT_COUNT: usize = 576;
const COEFFICIENTS_PER_BIN: usize = 24;
const WARMUP_GRANULES: usize = 4;
const SMALL_THRESHOLDS: [f64; 7] = [1.0e-8, 1.0e-7, 1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2];

#[derive(Debug, Serialize)]
struct ThresholdSummary {
    relative_threshold: f64,
    mean_count_per_granule: f64,
    fraction: f64,
}

#[derive(Debug, Serialize)]
struct ProbeReport {
    schema_version: u32,
    case_id: String,
    state: &'static str,
    algorithm: &'static str,
    sample_rate_hz: u32,
    channel_count: u32,
    input_sample_count: usize,
    analyzed_granule_count: usize,
    warmup_granule_count: usize,
    exact_zero_mean_count_per_granule: f64,
    exact_zero_fraction: f64,
    small_coefficient_counts: Vec<ThresholdSummary>,
    mean_normalized_magnitude_by_bin_24: Vec<f64>,
    small_fraction_1e4_by_bin_24: Vec<f64>,
    small_fraction_1e3_by_bin_24: Vec<f64>,
}

fn read_f32_stdin() -> Result<Vec<f32>, String> {
    let mut bytes = Vec::new();
    io::stdin()
        .read_to_end(&mut bytes)
        .map_err(|error| format!("read stdin: {error}"))?;
    if bytes.len() % std::mem::size_of::<f32>() != 0 {
        return Err("stdin byte count is not divisible by four".to_owned());
    }
    Ok(bytes
        .chunks_exact(4)
        .map(|chunk| f32::from_le_bytes(chunk.try_into().expect("four bytes")))
        .collect())
}

fn main() -> Result<(), String> {
    let case_id = std::env::args()
        .nth(1)
        .ok_or_else(|| "usage: mp3-history-probe CASE_ID < mono.f32le".to_owned())?;
    let samples = read_f32_stdin()?;
    let full_granules = samples.len() / GRANULE_SAMPLES;
    if full_granules <= WARMUP_GRANULES {
        return Err("insufficient PCM for MP3 hybrid analysis".to_owned());
    }

    let mut analysis_state = AnalysisState::new();
    let mut mdct_states: [MdctState; SUBBAND_COUNT] = std::array::from_fn(|_| MdctState::new());
    let mut exact_zero_count = 0usize;
    let mut small_counts = [0usize; SMALL_THRESHOLDS.len()];
    let mut magnitude_sums = [0.0f64; COEFFICIENT_COUNT];
    let mut small_1e4_counts = [0usize; COEFFICIENT_COUNT];
    let mut small_1e3_counts = [0usize; COEFFICIENT_COUNT];
    let mut analyzed_granules = 0usize;

    for (granule_index, granule) in samples.chunks_exact(GRANULE_SAMPLES).enumerate() {
        let pcm: &[f32; GRANULE_SAMPLES] =
            granule.try_into().expect("chunks_exact yields one granule");
        let subbands = analyze_granule(pcm, &mut analysis_state);
        let mut coefficients = [0.0f64; COEFFICIENT_COUNT];
        for subband in 0..SUBBAND_COUNT {
            let current: [f64; COEFFICIENTS_PER_SUBBAND] =
                std::array::from_fn(|index| f64::from(subbands[subband][index]));
            let overlap = forward_overlap(&current, &mut mdct_states[subband]);
            let windowed = window_long_family_analysis(&overlap, BlockType::Long);
            let transformed = mdct(&windowed, 36);
            coefficients
                [subband * COEFFICIENTS_PER_SUBBAND..(subband + 1) * COEFFICIENTS_PER_SUBBAND]
                .copy_from_slice(&transformed);
        }
        if granule_index < WARMUP_GRANULES {
            continue;
        }
        let coefficient_rms = (coefficients.iter().map(|value| value * value).sum::<f64>()
            / COEFFICIENT_COUNT as f64)
            .sqrt();
        if coefficient_rms <= 1.0e-12 {
            continue;
        }
        analyzed_granules += 1;
        for (index, coefficient) in coefficients.iter().copied().enumerate() {
            if coefficient == 0.0 {
                exact_zero_count += 1;
            }
            let normalized = coefficient.abs() / coefficient_rms;
            magnitude_sums[index] += normalized;
            for (threshold_index, threshold) in SMALL_THRESHOLDS.iter().copied().enumerate() {
                if normalized <= threshold {
                    small_counts[threshold_index] += 1;
                }
            }
            if normalized <= 1.0e-4 {
                small_1e4_counts[index] += 1;
            }
            if normalized <= 1.0e-3 {
                small_1e3_counts[index] += 1;
            }
        }
    }
    if analyzed_granules == 0 {
        return Err("no supported MP3 hybrid granules".to_owned());
    }
    let total_coefficients = analyzed_granules * COEFFICIENT_COUNT;
    let collapse_f64 = |values: &[f64; COEFFICIENT_COUNT]| {
        values
            .chunks_exact(COEFFICIENTS_PER_BIN)
            .map(|bin| bin.iter().sum::<f64>() / COEFFICIENTS_PER_BIN as f64)
            .collect::<Vec<_>>()
    };
    let collapse_usize = |values: &[usize; COEFFICIENT_COUNT]| {
        values
            .chunks_exact(COEFFICIENTS_PER_BIN)
            .map(|bin| {
                bin.iter().sum::<usize>() as f64 / (COEFFICIENTS_PER_BIN * analyzed_granules) as f64
            })
            .collect::<Vec<_>>()
    };
    let normalized_magnitudes = magnitude_sums.map(|value| value / analyzed_granules as f64);
    let report = ProbeReport {
        schema_version: 1,
        case_id,
        state: "research_only_exact_mp3_hybrid_transform_probe",
        algorithm: "iso11172_3_polyphase_analysis_plus_long_hybrid_mdct",
        sample_rate_hz: 44_100,
        channel_count: 1,
        input_sample_count: samples.len(),
        analyzed_granule_count: analyzed_granules,
        warmup_granule_count: WARMUP_GRANULES,
        exact_zero_mean_count_per_granule: exact_zero_count as f64 / analyzed_granules as f64,
        exact_zero_fraction: exact_zero_count as f64 / total_coefficients as f64,
        small_coefficient_counts: SMALL_THRESHOLDS
            .iter()
            .copied()
            .zip(small_counts)
            .map(|(threshold, count)| ThresholdSummary {
                relative_threshold: threshold,
                mean_count_per_granule: count as f64 / analyzed_granules as f64,
                fraction: count as f64 / total_coefficients as f64,
            })
            .collect(),
        mean_normalized_magnitude_by_bin_24: collapse_f64(&normalized_magnitudes),
        small_fraction_1e4_by_bin_24: collapse_usize(&small_1e4_counts),
        small_fraction_1e3_by_bin_24: collapse_usize(&small_1e3_counts),
    };
    serde_json::to_writer(io::stdout().lock(), &report)
        .map_err(|error| format!("serialize report: {error}"))?;
    println!();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_granule_stays_zero_through_exact_hybrid_chain() {
        let pcm = [0.0f32; GRANULE_SAMPLES];
        let mut analysis_state = AnalysisState::new();
        let subbands = analyze_granule(&pcm, &mut analysis_state);
        assert!(subbands.iter().flatten().all(|value| *value == 0.0));

        let mut state = MdctState::new();
        let current = [0.0f64; COEFFICIENTS_PER_SUBBAND];
        let overlap = forward_overlap(&current, &mut state);
        let windowed = window_long_family_analysis(&overlap, BlockType::Long);
        let coefficients = mdct(&windowed, 36);
        assert_eq!(coefficients.len(), COEFFICIENTS_PER_SUBBAND);
        assert!(coefficients.iter().all(|value| *value == 0.0));
    }

    #[test]
    fn impulse_produces_finite_hybrid_coefficients() {
        let mut pcm = [0.0f32; GRANULE_SAMPLES];
        pcm[GRANULE_SAMPLES / 2] = 1.0;
        let mut analysis_state = AnalysisState::new();
        let subbands = analyze_granule(&pcm, &mut analysis_state);
        let mut states: [MdctState; SUBBAND_COUNT] = std::array::from_fn(|_| MdctState::new());
        let mut nonzero = 0usize;
        for subband in 0..SUBBAND_COUNT {
            let current = std::array::from_fn(|index| f64::from(subbands[subband][index]));
            let overlap = forward_overlap(&current, &mut states[subband]);
            let windowed = window_long_family_analysis(&overlap, BlockType::Long);
            let coefficients = mdct(&windowed, 36);
            assert!(coefficients.iter().all(|value| value.is_finite()));
            nonzero += coefficients
                .iter()
                .filter(|value| value.abs() > 0.0)
                .count();
        }
        assert!(nonzero > 0);
    }
}
