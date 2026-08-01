//! Verdict-free exact MP3 hybrid-transform ablation probe.
//!
//! The measurement contract is preregistered in
//! `docs/research/exact-hybrid-ablation-preregistration-20260801.md`.

use std::io::{self, Read};
use std::sync::OnceLock;
use std::time::Instant;

use oxideav_mp3::analysis::{m_coefficient, C_TABLE};
use serde::Serialize;

const GRANULE_SAMPLES: usize = 576;
const ANALYSIS_ROW_SAMPLES: usize = 32;
const ANALYSIS_STATE_SAMPLES: usize = 512;
const SUBBAND_COUNT: usize = 32;
const COEFFICIENTS_PER_SUBBAND: usize = 18;
const COEFFICIENT_COUNT: usize = 576;
const COEFFICIENTS_PER_BIN: usize = 24;
const WARMUP_GRANULES: usize = 4;
const REGION_COUNT: usize = 5;
const PHASE_OFFSETS: [usize; 8] = [0, 72, 144, 216, 288, 360, 432, 504];
const GLOBAL_RMS_FLOOR: f64 = 1.0e-12;
const REPLAY_SMALL_THRESHOLD: f64 = 1.0e-4;
const LOCAL_THRESHOLDS: [f64; 3] = [1.0e-4, 1.0e-3, 1.0e-2];
const LOCAL_SCALE_RMS_FLOOR: f64 = 1.0e-4;
const CONTENT_ACTIVE_THRESHOLD: f64 = 1.0e-3;
const CONTENT_ACTIVE_FRACTION: f64 = 0.10;
const MIN_REGION_GRANULES: usize = 32;
const MIN_SUPPORTED_PHASES: usize = 6;
const REFERENCE_COEFFICIENT_END: usize = 432;
const REPLAY_SELECTED_START: usize = 432;
const REPLAY_SELECTED_END: usize = 456;
const TARGET_SUBBAND_START: usize = 24;

type AnalysisMatrix = [[f64; 64]; SUBBAND_COUNT];
type MdctKernel = [[f64; 36]; COEFFICIENTS_PER_SUBBAND];

#[derive(Debug)]
struct AnalysisState {
    samples: [f64; ANALYSIS_STATE_SAMPLES],
}

impl Default for AnalysisState {
    fn default() -> Self {
        Self {
            samples: [0.0; ANALYSIS_STATE_SAMPLES],
        }
    }
}

#[derive(Debug, Clone, Default)]
struct RegionAccumulator {
    analyzed_granules: usize,
    measurable_granules: usize,
    content_supported_granules: usize,
    replay_small_count: usize,
    replay_count: usize,
    local_small_counts: [usize; LOCAL_THRESHOLDS.len()],
    local_count: usize,
}

#[derive(Debug)]
struct ReplayAccumulator {
    analyzed_granules: usize,
    exact_zero_count: usize,
    magnitude_sums: [f64; COEFFICIENT_COUNT],
    small_1e4_counts: [usize; COEFFICIENT_COUNT],
    small_1e3_counts: [usize; COEFFICIENT_COUNT],
}

impl Default for ReplayAccumulator {
    fn default() -> Self {
        Self {
            analyzed_granules: 0,
            exact_zero_count: 0,
            magnitude_sums: [0.0; COEFFICIENT_COUNT],
            small_1e4_counts: [0; COEFFICIENT_COUNT],
            small_1e3_counts: [0; COEFFICIENT_COUNT],
        }
    }
}

#[derive(Debug, Serialize)]
struct RegionSummary {
    region_index: usize,
    analyzed_granule_count: usize,
    measurable_granule_count: usize,
    content_supported_granule_count: usize,
    content_supported_fraction: Option<f64>,
    replay_selected_small_fraction_1e4: Option<f64>,
    subband_relative_small_fraction_1e4: Option<f64>,
    subband_relative_small_fraction_1e3: Option<f64>,
    subband_relative_small_fraction_1e2: Option<f64>,
    time_region_supported: bool,
    content_region_supported: bool,
}

#[derive(Debug, Serialize)]
struct PhaseSummary {
    phase_offset_samples: usize,
    input_granule_count: usize,
    analyzed_granule_count: usize,
    measurable_granule_count: usize,
    content_supported_granule_count: usize,
    content_supported_fraction: Option<f64>,
    global_replay_selected_small_fraction_1e4: Option<f64>,
    global_subband_relative_small_fraction_1e2: Option<f64>,
    time_median_subband_relative_small_fraction_1e2: Option<f64>,
    time_region_supported: bool,
    content_guard_supported: bool,
    regions: Vec<RegionSummary>,
}

#[derive(Debug, Serialize)]
struct ReplaySummary {
    analyzed_granule_count: usize,
    exact_zero_mean_count_per_granule: f64,
    exact_zero_fraction: f64,
    mean_normalized_magnitude_by_bin_24: Vec<f64>,
    small_fraction_1e4_by_bin_24: Vec<f64>,
    small_fraction_1e3_by_bin_24: Vec<f64>,
}

#[derive(Debug, Serialize)]
struct AggregateSummary {
    a0_replay_selected_small_fraction_1e4: Option<f64>,
    a1_phase_zero_subband_relative_small_fraction_1e2: Option<f64>,
    a2_phase_zero_time_median_small_fraction_1e2: Option<f64>,
    a3_supported_phase_count: usize,
    a3_phase_stable_small_fraction_1e2: Option<f64>,
    a3_phase_interquartile_range: Option<f64>,
    a3_phase_full_range: Option<f64>,
    a4_content_guard_supported: bool,
    a4_content_guarded_small_fraction_1e2: Option<f64>,
}

#[derive(Debug, Serialize)]
struct ProbeReport {
    schema_version: u32,
    feature_version: u16,
    case_id: String,
    state: &'static str,
    algorithm: &'static str,
    public_verdict_enabled: bool,
    sample_rate_hz: u32,
    channel_count: u32,
    input_sample_count: usize,
    phase_offsets_samples: [usize; PHASE_OFFSETS.len()],
    warmup_granule_count: usize,
    time_region_count: usize,
    replay: ReplaySummary,
    aggregate: AggregateSummary,
    phases: Vec<PhaseSummary>,
    elapsed_ms: f64,
}

fn analysis_matrix() -> &'static AnalysisMatrix {
    static MATRIX: OnceLock<AnalysisMatrix> = OnceLock::new();
    MATRIX.get_or_init(|| {
        std::array::from_fn(|subband| std::array::from_fn(|index| m_coefficient(subband, index)))
    })
}

fn mdct_kernel() -> &'static MdctKernel {
    static KERNEL: OnceLock<MdctKernel> = OnceLock::new();
    KERNEL.get_or_init(|| {
        std::array::from_fn(|coefficient| {
            std::array::from_fn(|sample| {
                let window = (std::f64::consts::PI / 36.0 * (sample as f64 + 0.5)).sin();
                let angle = std::f64::consts::PI / 72.0
                    * (2 * sample + 1 + COEFFICIENTS_PER_SUBBAND) as f64
                    * (2 * coefficient + 1) as f64;
                window * angle.cos()
            })
        })
    })
}

fn analyze_row(
    pcm: &[f32; ANALYSIS_ROW_SAMPLES],
    state: &mut AnalysisState,
) -> [f32; SUBBAND_COUNT] {
    state.samples.copy_within(
        0..ANALYSIS_STATE_SAMPLES - ANALYSIS_ROW_SAMPLES,
        ANALYSIS_ROW_SAMPLES,
    );
    for (index, value) in pcm.iter().enumerate() {
        state.samples[ANALYSIS_ROW_SAMPLES - 1 - index] = f64::from(*value);
    }
    let mut folded = [0.0_f64; 64];
    for (index, value) in folded.iter_mut().enumerate() {
        *value = (0..8)
            .map(|tap| {
                let source = index + 64 * tap;
                C_TABLE[source] * state.samples[source]
            })
            .sum();
    }
    std::array::from_fn(|subband| {
        analysis_matrix()[subband]
            .iter()
            .zip(folded)
            .map(|(matrix, value)| matrix * value)
            .sum::<f64>() as f32
    })
}

fn transform_subband(previous: &[f64; 18], current: &[f64; 18]) -> [f64; 18] {
    std::array::from_fn(|coefficient| {
        mdct_kernel()[coefficient]
            .iter()
            .enumerate()
            .map(|(sample, kernel)| {
                let value = if sample < 18 {
                    previous[sample]
                } else {
                    current[sample - 18]
                };
                kernel * value
            })
            .sum()
    })
}

fn hybrid_coefficients(
    granule: &[f32; GRANULE_SAMPLES],
    analysis_state: &mut AnalysisState,
    previous: &mut [[f64; 18]; SUBBAND_COUNT],
) -> [f64; COEFFICIENT_COUNT] {
    let mut subbands = [[0.0_f64; 18]; SUBBAND_COUNT];
    for (time, row) in granule.chunks_exact(ANALYSIS_ROW_SAMPLES).enumerate() {
        let row: &[f32; ANALYSIS_ROW_SAMPLES] = row.try_into().expect("exact analysis row");
        let analyzed = analyze_row(row, analysis_state);
        for subband in 0..SUBBAND_COUNT {
            subbands[subband][time] = f64::from(analyzed[subband]);
        }
    }
    let mut coefficients = [0.0_f64; COEFFICIENT_COUNT];
    for subband in 0..SUBBAND_COUNT {
        let transformed = transform_subband(&previous[subband], &subbands[subband]);
        coefficients[subband * 18..(subband + 1) * 18].copy_from_slice(&transformed);
        previous[subband] = subbands[subband];
    }
    coefficients
}

fn nearest_rank_q75(values: &[f64; 18]) -> f64 {
    let mut sorted = *values;
    sorted.sort_by(f64::total_cmp);
    sorted[13]
}

fn ratio(numerator: usize, denominator: usize) -> Option<f64> {
    (denominator > 0).then(|| numerator as f64 / denominator as f64)
}

fn median(values: &mut [f64]) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    values.sort_by(f64::total_cmp);
    let middle = values.len() / 2;
    Some(if values.len().is_multiple_of(2) {
        (values[middle - 1] + values[middle]) * 0.5
    } else {
        values[middle]
    })
}

fn quartiles(values: &[f64]) -> Option<(f64, f64)> {
    if values.is_empty() {
        return None;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(f64::total_cmp);
    let lower_end = sorted.len() / 2;
    let upper_start = sorted.len().div_ceil(2);
    let q1 = median(&mut sorted[..lower_end].to_vec()).unwrap_or(sorted[0]);
    let q3 = median(&mut sorted[upper_start..].to_vec()).unwrap_or(*sorted.last().unwrap());
    Some((q1, q3))
}

fn observe_coefficients(
    coefficients: &[f64; COEFFICIENT_COUNT],
    region: &mut RegionAccumulator,
    replay: Option<&mut ReplayAccumulator>,
) {
    let rms = (coefficients.iter().map(|value| value * value).sum::<f64>()
        / COEFFICIENT_COUNT as f64)
        .sqrt();
    if rms <= GLOBAL_RMS_FLOOR {
        return;
    }
    region.analyzed_granules += 1;
    let content_active = coefficients[..REFERENCE_COEFFICIENT_END]
        .iter()
        .filter(|value| value.abs() / rms > CONTENT_ACTIVE_THRESHOLD)
        .count();
    if content_active as f64 / REFERENCE_COEFFICIENT_END as f64 >= CONTENT_ACTIVE_FRACTION {
        region.content_supported_granules += 1;
    }
    for value in &coefficients[REPLAY_SELECTED_START..REPLAY_SELECTED_END] {
        region.replay_count += 1;
        if value.abs() / rms <= REPLAY_SMALL_THRESHOLD {
            region.replay_small_count += 1;
        }
    }
    let mut measurable_subbands = 0;
    for subband in TARGET_SUBBAND_START..SUBBAND_COUNT {
        let start = subband * COEFFICIENTS_PER_SUBBAND;
        let magnitudes: [f64; 18] = std::array::from_fn(|index| coefficients[start + index].abs());
        let scale = nearest_rank_q75(&magnitudes);
        if scale <= rms * LOCAL_SCALE_RMS_FLOOR {
            continue;
        }
        measurable_subbands += 1;
        for magnitude in magnitudes {
            region.local_count += 1;
            for (index, threshold) in LOCAL_THRESHOLDS.iter().enumerate() {
                if magnitude <= scale * threshold {
                    region.local_small_counts[index] += 1;
                }
            }
        }
    }
    if measurable_subbands > 0 {
        region.measurable_granules += 1;
    }

    if let Some(replay) = replay {
        replay.analyzed_granules += 1;
        for (index, coefficient) in coefficients.iter().enumerate() {
            if *coefficient == 0.0 {
                replay.exact_zero_count += 1;
            }
            let normalized = coefficient.abs() / rms;
            replay.magnitude_sums[index] += normalized;
            if normalized <= 1.0e-4 {
                replay.small_1e4_counts[index] += 1;
            }
            if normalized <= 1.0e-3 {
                replay.small_1e3_counts[index] += 1;
            }
        }
    }
}

fn summarize_region(index: usize, region: &RegionAccumulator) -> RegionSummary {
    let local = |threshold: usize| ratio(region.local_small_counts[threshold], region.local_count);
    RegionSummary {
        region_index: index,
        analyzed_granule_count: region.analyzed_granules,
        measurable_granule_count: region.measurable_granules,
        content_supported_granule_count: region.content_supported_granules,
        content_supported_fraction: ratio(
            region.content_supported_granules,
            region.analyzed_granules,
        ),
        replay_selected_small_fraction_1e4: ratio(region.replay_small_count, region.replay_count),
        subband_relative_small_fraction_1e4: local(0),
        subband_relative_small_fraction_1e3: local(1),
        subband_relative_small_fraction_1e2: local(2),
        time_region_supported: region.measurable_granules >= MIN_REGION_GRANULES,
        content_region_supported: region.content_supported_granules >= MIN_REGION_GRANULES,
    }
}

fn measure_phase(
    samples: &[f32],
    phase_offset: usize,
    replay: Option<&mut ReplayAccumulator>,
) -> PhaseSummary {
    let phase_samples = &samples[phase_offset.min(samples.len())..];
    let input_granules = phase_samples.len() / GRANULE_SAMPLES;
    let post_warmup_granules = input_granules.saturating_sub(WARMUP_GRANULES);
    let mut analysis_state = AnalysisState::default();
    let mut previous = [[0.0_f64; 18]; SUBBAND_COUNT];
    let mut regions: [RegionAccumulator; REGION_COUNT] = Default::default();
    let mut replay = replay;
    for (granule_index, granule) in phase_samples.chunks_exact(GRANULE_SAMPLES).enumerate() {
        let granule: &[f32; GRANULE_SAMPLES] = granule.try_into().expect("exact granule");
        let coefficients = hybrid_coefficients(granule, &mut analysis_state, &mut previous);
        if granule_index < WARMUP_GRANULES || post_warmup_granules == 0 {
            continue;
        }
        let measured_index = granule_index - WARMUP_GRANULES;
        let region_index =
            (measured_index * REGION_COUNT / post_warmup_granules).min(REGION_COUNT - 1);
        observe_coefficients(
            &coefficients,
            &mut regions[region_index],
            replay.as_deref_mut(),
        );
    }
    let replay_small = ratio(
        regions.iter().map(|region| region.replay_small_count).sum(),
        regions.iter().map(|region| region.replay_count).sum(),
    );
    let local_small = ratio(
        regions
            .iter()
            .map(|region| region.local_small_counts[2])
            .sum(),
        regions.iter().map(|region| region.local_count).sum(),
    );
    let regions: Vec<_> = regions
        .iter()
        .enumerate()
        .map(|(index, region)| summarize_region(index, region))
        .collect();
    let analyzed_granules = regions
        .iter()
        .map(|region| region.analyzed_granule_count)
        .sum();
    let measurable_granules = regions
        .iter()
        .map(|region| region.measurable_granule_count)
        .sum();
    let content_supported_granules = regions
        .iter()
        .map(|region| region.content_supported_granule_count)
        .sum();
    let time_region_supported = regions.iter().all(|region| region.time_region_supported);
    let content_guard_supported = time_region_supported
        && regions.iter().all(|region| region.content_region_supported)
        && content_supported_granules * 2 >= analyzed_granules;
    let mut region_values: Vec<_> = regions
        .iter()
        .filter(|region| region.time_region_supported)
        .filter_map(|region| region.subband_relative_small_fraction_1e2)
        .collect();
    let time_median = (region_values.len() == REGION_COUNT)
        .then(|| median(&mut region_values))
        .flatten();
    PhaseSummary {
        phase_offset_samples: phase_offset,
        input_granule_count: input_granules,
        analyzed_granule_count: analyzed_granules,
        measurable_granule_count: measurable_granules,
        content_supported_granule_count: content_supported_granules,
        content_supported_fraction: ratio(content_supported_granules, analyzed_granules),
        global_replay_selected_small_fraction_1e4: replay_small,
        global_subband_relative_small_fraction_1e2: local_small,
        time_median_subband_relative_small_fraction_1e2: time_median,
        time_region_supported,
        content_guard_supported,
        regions,
    }
}

fn collapse_f64(values: &[f64; COEFFICIENT_COUNT], divisor: f64) -> Vec<f64> {
    values
        .chunks_exact(COEFFICIENTS_PER_BIN)
        .map(|bin| bin.iter().sum::<f64>() / COEFFICIENTS_PER_BIN as f64 / divisor)
        .collect()
}

fn collapse_usize(values: &[usize; COEFFICIENT_COUNT], divisor: usize) -> Vec<f64> {
    values
        .chunks_exact(COEFFICIENTS_PER_BIN)
        .map(|bin| bin.iter().sum::<usize>() as f64 / (COEFFICIENTS_PER_BIN * divisor) as f64)
        .collect()
}

fn replay_summary(replay: ReplayAccumulator) -> Result<ReplaySummary, String> {
    if replay.analyzed_granules == 0 {
        return Err("no supported exact-hybrid granules".to_owned());
    }
    let total_coefficients = replay.analyzed_granules * COEFFICIENT_COUNT;
    Ok(ReplaySummary {
        analyzed_granule_count: replay.analyzed_granules,
        exact_zero_mean_count_per_granule: replay.exact_zero_count as f64
            / replay.analyzed_granules as f64,
        exact_zero_fraction: replay.exact_zero_count as f64 / total_coefficients as f64,
        mean_normalized_magnitude_by_bin_24: collapse_f64(
            &replay.magnitude_sums,
            replay.analyzed_granules as f64,
        ),
        small_fraction_1e4_by_bin_24: collapse_usize(
            &replay.small_1e4_counts,
            replay.analyzed_granules,
        ),
        small_fraction_1e3_by_bin_24: collapse_usize(
            &replay.small_1e3_counts,
            replay.analyzed_granules,
        ),
    })
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
    let case_id = std::env::args().nth(1).ok_or_else(|| {
        "usage: lossytrace-exact-hybrid-ablation CASE_ID < mono-44100.f32le".to_owned()
    })?;
    let samples = read_f32_stdin()?;
    if samples.len() / GRANULE_SAMPLES <= WARMUP_GRANULES {
        return Err("insufficient PCM for exact-hybrid analysis".to_owned());
    }
    let started = Instant::now();
    let mut replay = ReplayAccumulator::default();
    let mut phases = Vec::with_capacity(PHASE_OFFSETS.len());
    for (index, offset) in PHASE_OFFSETS.iter().copied().enumerate() {
        phases.push(measure_phase(
            &samples,
            offset,
            (index == 0).then_some(&mut replay),
        ));
    }
    let phase_zero = phases.first().expect("fixed non-empty phases");
    let supported_values: Vec<_> = phases
        .iter()
        .filter(|phase| phase.time_region_supported)
        .filter_map(|phase| phase.time_median_subband_relative_small_fraction_1e2)
        .collect();
    let mut median_values = supported_values.clone();
    let phase_stable = (supported_values.len() >= MIN_SUPPORTED_PHASES)
        .then(|| median(&mut median_values))
        .flatten();
    let (iqr, full_range) = if let (Some((q1, q3)), Some(minimum), Some(maximum)) = (
        quartiles(&supported_values),
        supported_values.iter().copied().min_by(f64::total_cmp),
        supported_values.iter().copied().max_by(f64::total_cmp),
    ) {
        (Some(q3 - q1), Some(maximum - minimum))
    } else {
        (None, None)
    };
    let content_guard_supported = supported_values.len() >= MIN_SUPPORTED_PHASES
        && phases
            .iter()
            .filter(|phase| phase.time_region_supported)
            .all(|phase| phase.content_guard_supported);
    let replay = replay_summary(replay)?;
    if let Some(a0) = phase_zero.global_replay_selected_small_fraction_1e4 {
        if (a0 - replay.small_fraction_1e4_by_bin_24[18]).abs() > 1.0e-15 {
            return Err("A0 and archived-replay summaries differ".to_owned());
        }
    }
    let report = ProbeReport {
        schema_version: 2,
        feature_version: 0,
        case_id,
        state: "research_only_exact_mp3_hybrid_ablation",
        algorithm: "iso11172_3_polyphase_analysis_plus_long_hybrid_mdct",
        public_verdict_enabled: false,
        sample_rate_hz: 44_100,
        channel_count: 1,
        input_sample_count: samples.len(),
        phase_offsets_samples: PHASE_OFFSETS,
        warmup_granule_count: WARMUP_GRANULES,
        time_region_count: REGION_COUNT,
        replay,
        aggregate: AggregateSummary {
            a0_replay_selected_small_fraction_1e4: phase_zero
                .global_replay_selected_small_fraction_1e4,
            a1_phase_zero_subband_relative_small_fraction_1e2: phase_zero
                .global_subband_relative_small_fraction_1e2,
            a2_phase_zero_time_median_small_fraction_1e2: phase_zero
                .time_median_subband_relative_small_fraction_1e2,
            a3_supported_phase_count: supported_values.len(),
            a3_phase_stable_small_fraction_1e2: phase_stable,
            a3_phase_interquartile_range: iqr,
            a3_phase_full_range: full_range,
            a4_content_guard_supported: content_guard_supported,
            a4_content_guarded_small_fraction_1e2: content_guard_supported
                .then_some(phase_stable)
                .flatten(),
        },
        phases,
        elapsed_ms: started.elapsed().as_secs_f64() * 1_000.0,
    };
    serde_json::to_writer(io::stdout().lock(), &report)
        .map_err(|error| format!("serialize report: {error}"))?;
    println!();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use oxideav_mp3::analysis::{
        analyze_granule as reference_analyze_granule, AnalysisState as ReferenceAnalysisState,
    };
    use oxideav_mp3::mdct::{forward_overlap, mdct, window_long_family_analysis, MdctState};
    use oxideav_mp3::side_info::BlockType;

    fn deterministic_pcm() -> [f32; GRANULE_SAMPLES] {
        std::array::from_fn(|index| {
            let time = index as f64 / 44_100.0;
            (0.37 * (std::f64::consts::TAU * 997.0 * time).sin()
                + 0.11 * (std::f64::consts::TAU * 7_111.0 * time).sin()) as f32
        })
    }

    #[test]
    fn optimized_analysis_matches_pinned_reference() {
        let pcm = deterministic_pcm();
        let mut optimized = AnalysisState::default();
        let mut reference = ReferenceAnalysisState::new();
        let expected = reference_analyze_granule(&pcm, &mut reference);
        for (time, row) in pcm.chunks_exact(32).enumerate() {
            let row: &[f32; 32] = row.try_into().unwrap();
            let actual = analyze_row(row, &mut optimized);
            for subband in 0..32 {
                assert_eq!(actual[subband], expected[subband][time]);
            }
        }
    }

    #[test]
    fn optimized_mdct_matches_pinned_reference() {
        let previous: [f64; 18] = std::array::from_fn(|index| (index as f64 * 0.17).sin());
        let current: [f64; 18] = std::array::from_fn(|index| (index as f64 * 0.31).cos());
        let mut state = MdctState::from_saved(previous);
        let overlap = forward_overlap(&current, &mut state);
        let windowed = window_long_family_analysis(&overlap, BlockType::Long);
        let expected = mdct(&windowed, 36);
        let actual = transform_subband(&previous, &current);
        for (actual, expected) in actual.iter().zip(expected) {
            assert!((actual - expected).abs() <= 1.0e-12);
        }
    }

    #[test]
    fn scale_normalization_is_gain_invariant() {
        let coefficients: [f64; COEFFICIENT_COUNT] =
            std::array::from_fn(|index| ((index + 1) as f64 * 0.017).sin());
        let scaled = coefficients.map(|value| value * 0.03125);
        let mut first = RegionAccumulator::default();
        let mut second = RegionAccumulator::default();
        observe_coefficients(&coefficients, &mut first, None);
        observe_coefficients(&scaled, &mut second, None);
        assert_eq!(first.replay_small_count, second.replay_small_count);
        assert_eq!(first.local_small_counts, second.local_small_counts);
        assert_eq!(first.local_count, second.local_count);
        assert_eq!(
            first.content_supported_granules,
            second.content_supported_granules
        );
    }

    #[test]
    fn silence_is_not_supported() {
        let coefficients = [0.0_f64; COEFFICIENT_COUNT];
        let mut region = RegionAccumulator::default();
        observe_coefficients(&coefficients, &mut region, None);
        assert_eq!(region.analyzed_granules, 0);
        assert_eq!(region.measurable_granules, 0);
    }
}
