//! Verdict-free codec-projection research oracle.
//!
//! The fixed measurement contract is preregistered in
//! `docs/research/codec-projection-preregistration-20260802.md`.

use std::env;
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Instant;

use serde::{Deserialize, Serialize};

const COMMON_FFMPEG_ARGS: [&str; 5] = ["-nostdin", "-hide_banner", "-loglevel", "error", "-y"];

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Configuration {
    schema_version: u32,
    state: String,
    feature_version: u16,
    public_verdict_enabled: bool,
    algorithm: String,
    canonical_pcm: CanonicalPcm,
    projection: Projection,
    measurement: Measurement,
    representations: Vec<Representation>,
    selection: serde_json::Value,
    evaluation: serde_json::Value,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CanonicalPcm {
    start_seconds: f64,
    duration_seconds: f64,
    minimum_decoded_seconds: f64,
    sample_rate_hz: usize,
    channel_count: usize,
    clip_threshold: f64,
    maximum_clipped_fraction: f64,
    active_block_frames: usize,
    absolute_active_rms_dbfs: f64,
    relative_active_db: f64,
    minimum_active_fraction: f64,
    median_active_minimum_dbfs: f64,
    target_median_active_rms_dbfs: f64,
    peak_cap_dbfs: f64,
    quantization: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Projection {
    pcm_boundary: String,
    encode_args_after_input: Vec<String>,
    decode_args_after_input: Vec<String>,
    maximum_length_difference_frames: usize,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Measurement {
    edge_exclusion_frames: usize,
    block_frames: usize,
    minimum_power_exclusive: f64,
    minimum_supported_blocks: usize,
    minimum_supported_block_fraction: f64,
    quantile_method: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Representation {
    field: String,
    formula: String,
}

#[derive(Debug, Serialize)]
struct SupportSummary {
    supported: bool,
    reason: &'static str,
    decoded_frame_count: usize,
    clipped_sample_fraction: Option<f64>,
    active_block_count: Option<usize>,
    total_activity_block_count: Option<usize>,
    active_block_fraction: Option<f64>,
    median_active_rms_dbfs: Option<f64>,
    applied_scale: Option<f64>,
    canonical_frame_count: Option<usize>,
    first_projection_frame_count: Option<usize>,
    second_projection_frame_count: Option<usize>,
    aligned_frame_count: Option<usize>,
    eligible_measurement_block_count: Option<usize>,
    supported_measurement_block_count: Option<usize>,
    supported_measurement_block_fraction: Option<f64>,
}

#[derive(Debug, Serialize)]
struct BlockMeasurement {
    block_index: usize,
    signal_power: f64,
    first_residual_power: f64,
    second_residual_power: f64,
    r1_cycle_residual_retention: f64,
    r1_equivalent_db: f64,
    r2_residual_directional_recurrence: f64,
}

#[derive(Debug, Serialize)]
struct ScoreSummary {
    r1_cycle_residual_retention: f64,
    r1_interquartile_range: f64,
    r1_equivalent_db_median: f64,
    r2_residual_directional_recurrence: f64,
    r2_interquartile_range: f64,
}

#[derive(Debug, Serialize)]
struct OracleReport {
    schema_version: u32,
    state: &'static str,
    feature_version: u16,
    public_verdict_enabled: bool,
    case_id: String,
    algorithm: String,
    projection_performed: bool,
    support: SupportSummary,
    scores: Option<ScoreSummary>,
    blocks: Vec<BlockMeasurement>,
}

#[derive(Debug, Serialize)]
struct TimingReport {
    schema_version: u32,
    state: &'static str,
    case_id: String,
    elapsed_ms: f64,
    peak_resident_bytes: Option<u64>,
    ffmpeg_command_count: usize,
}

#[derive(Debug)]
struct Canonicalized {
    samples: Vec<i16>,
    support: SupportSummary,
}

fn read_configuration(path: &Path) -> Result<Configuration, String> {
    let bytes = fs::read(path).map_err(|error| format!("read configuration: {error}"))?;
    let config: Configuration =
        serde_json::from_slice(&bytes).map_err(|error| format!("parse configuration: {error}"))?;
    validate_configuration(&config)?;
    Ok(config)
}

fn validate_configuration(config: &Configuration) -> Result<(), String> {
    if config.schema_version != 1
        || config.state != "codec_projection_observed_development_v1"
        || config.feature_version != 0
        || config.public_verdict_enabled
        || config.algorithm != "libmp3lame_cbr128_cycle_residual_v1"
        || config.canonical_pcm.sample_rate_hz != 44_100
        || config.canonical_pcm.channel_count != 2
        || config.canonical_pcm.quantization != "s16le_round_ties_away_from_zero_scale_32768"
        || config.projection.pcm_boundary != "signed_16_bit_little_endian_stereo_44100_hz"
        || config.measurement.quantile_method != "linear_interpolation_index_p_times_n_minus_1"
        || config.representations.len() != 2
        || config.representations[0].field != "r1_cycle_residual_retention"
        || config.representations[0].formula != "e2/(e1+e2)"
        || config.representations[1].field != "r2_residual_directional_recurrence"
        || config.representations[1].formula
            != "abs(cosine(demean_per_channel(r1),demean_per_channel(r2)))"
        || !config.selection.is_object()
        || !config.evaluation.is_object()
    {
        return Err("configuration contract differs from oracle v1".to_owned());
    }
    let numeric_valid = config.canonical_pcm.start_seconds >= 0.0
        && config.canonical_pcm.duration_seconds > 0.0
        && config.canonical_pcm.minimum_decoded_seconds > 0.0
        && (0.0..=1.0).contains(&config.canonical_pcm.clip_threshold)
        && (0.0..=1.0).contains(&config.canonical_pcm.maximum_clipped_fraction)
        && config.canonical_pcm.active_block_frames > 0
        && (0.0..=1.0).contains(&config.canonical_pcm.minimum_active_fraction)
        && config.measurement.edge_exclusion_frames > 0
        && config.measurement.block_frames > 0
        && config.measurement.minimum_power_exclusive > 0.0
        && config.measurement.minimum_supported_blocks > 0
        && (0.0..=1.0).contains(&config.measurement.minimum_supported_block_fraction)
        && config.projection.maximum_length_difference_frames > 0;
    if !numeric_valid {
        return Err("configuration contains invalid numeric bounds".to_owned());
    }
    Ok(())
}

fn run_ffmpeg(ffmpeg: &Path, args: &[String]) -> Result<Vec<u8>, String> {
    let output = Command::new(ffmpeg)
        .args(COMMON_FFMPEG_ARGS)
        .args(args)
        .output()
        .map_err(|error| format!("launch FFmpeg: {error}"))?;
    if !output.status.success() {
        return Err(format!(
            "FFmpeg failed with {}: {}",
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    Ok(output.stdout)
}

fn decode_source(
    ffmpeg: &Path,
    source: &Path,
    canonical: &CanonicalPcm,
) -> Result<Vec<f32>, String> {
    let args = vec![
        "-ss".to_owned(),
        canonical.start_seconds.to_string(),
        "-t".to_owned(),
        canonical.duration_seconds.to_string(),
        "-i".to_owned(),
        source.to_string_lossy().into_owned(),
        "-map_metadata".to_owned(),
        "-1".to_owned(),
        "-map_chapters".to_owned(),
        "-1".to_owned(),
        "-fflags".to_owned(),
        "+bitexact".to_owned(),
        "-flags:a".to_owned(),
        "+bitexact".to_owned(),
        "-ar".to_owned(),
        canonical.sample_rate_hz.to_string(),
        "-ac".to_owned(),
        canonical.channel_count.to_string(),
        "-c:a".to_owned(),
        "pcm_f32le".to_owned(),
        "-f".to_owned(),
        "f32le".to_owned(),
        "pipe:1".to_owned(),
    ];
    let bytes = run_ffmpeg(ffmpeg, &args)?;
    if !bytes.len().is_multiple_of(4 * canonical.channel_count) {
        return Err("decoded float PCM has a partial frame".to_owned());
    }
    Ok(bytes
        .chunks_exact(4)
        .map(|chunk| f32::from_le_bytes(chunk.try_into().expect("exact f32")))
        .collect())
}

fn db_to_amplitude(db: f64) -> f64 {
    10.0_f64.powf(db / 20.0)
}

fn amplitude_to_db(value: f64) -> f64 {
    20.0 * value.log10()
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

fn quantile(values: &[f64], proportion: f64) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    let mut ordered = values.to_vec();
    ordered.sort_by(f64::total_cmp);
    let position = proportion * (ordered.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    let fraction = position - lower as f64;
    Some(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)
}

fn canonicalize(decoded: &[f32], config: &CanonicalPcm) -> Canonicalized {
    let frames = decoded.len() / config.channel_count;
    let base = SupportSummary {
        supported: false,
        reason: "not_evaluated",
        decoded_frame_count: frames,
        clipped_sample_fraction: None,
        active_block_count: None,
        total_activity_block_count: None,
        active_block_fraction: None,
        median_active_rms_dbfs: None,
        applied_scale: None,
        canonical_frame_count: None,
        first_projection_frame_count: None,
        second_projection_frame_count: None,
        aligned_frame_count: None,
        eligible_measurement_block_count: None,
        supported_measurement_block_count: None,
        supported_measurement_block_fraction: None,
    };
    let minimum_frames =
        (config.minimum_decoded_seconds * config.sample_rate_hz as f64).ceil() as usize;
    if frames < minimum_frames {
        return Canonicalized {
            samples: Vec::new(),
            support: SupportSummary {
                reason: "too_short",
                ..base
            },
        };
    }
    if decoded.iter().any(|value| !value.is_finite()) {
        return Canonicalized {
            samples: Vec::new(),
            support: SupportSummary {
                reason: "non_finite_pcm",
                ..base
            },
        };
    }
    let clipped = decoded
        .iter()
        .filter(|value| f64::from(value.abs()) >= config.clip_threshold)
        .count();
    let clipped_fraction = clipped as f64 / decoded.len() as f64;
    if clipped_fraction > config.maximum_clipped_fraction {
        return Canonicalized {
            samples: Vec::new(),
            support: SupportSummary {
                reason: "clipped",
                clipped_sample_fraction: Some(clipped_fraction),
                ..base
            },
        };
    }
    let mut channel_means = vec![0.0_f64; config.channel_count];
    for frame in decoded.chunks_exact(config.channel_count) {
        for (channel, value) in frame.iter().enumerate() {
            channel_means[channel] += f64::from(*value);
        }
    }
    for mean in &mut channel_means {
        *mean /= frames as f64;
    }
    let centered: Vec<f64> = decoded
        .iter()
        .enumerate()
        .map(|(index, value)| f64::from(*value) - channel_means[index % config.channel_count])
        .collect();
    let block_samples = config.active_block_frames * config.channel_count;
    let mut block_rms: Vec<f64> = centered
        .chunks_exact(block_samples)
        .map(|block| {
            (block.iter().map(|value| value * value).sum::<f64>() / block.len() as f64).sqrt()
        })
        .collect();
    if block_rms.is_empty() {
        return Canonicalized {
            samples: Vec::new(),
            support: SupportSummary {
                reason: "no_activity_blocks",
                clipped_sample_fraction: Some(clipped_fraction),
                ..base
            },
        };
    }
    let maximum_rms = block_rms.iter().copied().fold(0.0_f64, f64::max);
    let activity_threshold = db_to_amplitude(config.absolute_active_rms_dbfs)
        .max(maximum_rms * db_to_amplitude(config.relative_active_db));
    let mut active_rms: Vec<f64> = block_rms
        .drain(..)
        .filter(|value| *value >= activity_threshold)
        .collect();
    let active_count = active_rms.len();
    let total_count = centered.len() / block_samples;
    let active_fraction = active_count as f64 / total_count as f64;
    let active_median = median(&mut active_rms);
    let active_median_db = active_median
        .filter(|value| *value > 0.0)
        .map(amplitude_to_db);
    let activity_fields = SupportSummary {
        reason: "not_evaluated",
        clipped_sample_fraction: Some(clipped_fraction),
        active_block_count: Some(active_count),
        total_activity_block_count: Some(total_count),
        active_block_fraction: Some(active_fraction),
        median_active_rms_dbfs: active_median_db,
        ..base
    };
    if active_fraction < config.minimum_active_fraction {
        return Canonicalized {
            samples: Vec::new(),
            support: SupportSummary {
                reason: "insufficient_activity",
                ..activity_fields
            },
        };
    }
    let Some(active_median) = active_median else {
        return Canonicalized {
            samples: Vec::new(),
            support: SupportSummary {
                reason: "insufficient_activity",
                ..activity_fields
            },
        };
    };
    if amplitude_to_db(active_median) < config.median_active_minimum_dbfs {
        return Canonicalized {
            samples: Vec::new(),
            support: SupportSummary {
                reason: "quiet",
                ..activity_fields
            },
        };
    }
    let peak = centered
        .iter()
        .map(|value| value.abs())
        .fold(0.0_f64, f64::max);
    let target_scale = db_to_amplitude(config.target_median_active_rms_dbfs) / active_median;
    let peak_scale = if peak > 0.0 {
        db_to_amplitude(config.peak_cap_dbfs) / peak
    } else {
        target_scale
    };
    let scale = target_scale.min(peak_scale);
    let samples = centered
        .iter()
        .map(|value| {
            (value * scale * 32_768.0)
                .round()
                .clamp(i16::MIN as f64, i16::MAX as f64) as i16
        })
        .collect();
    Canonicalized {
        samples,
        support: SupportSummary {
            supported: true,
            reason: "canonical_pcm_supported",
            applied_scale: Some(scale),
            canonical_frame_count: Some(frames),
            ..activity_fields
        },
    }
}

fn write_s16le(path: &Path, samples: &[i16]) -> Result<(), String> {
    let mut output = File::create(path).map_err(|error| format!("create PCM: {error}"))?;
    for value in samples {
        output
            .write_all(&value.to_le_bytes())
            .map_err(|error| format!("write PCM: {error}"))?;
    }
    output
        .flush()
        .map_err(|error| format!("flush PCM: {error}"))
}

fn read_s16le(path: &Path, channel_count: usize) -> Result<Vec<i16>, String> {
    let bytes = fs::read(path).map_err(|error| format!("read PCM: {error}"))?;
    if !bytes.len().is_multiple_of(2 * channel_count) {
        return Err("projected PCM has a partial frame".to_owned());
    }
    Ok(bytes
        .chunks_exact(2)
        .map(|chunk| i16::from_le_bytes(chunk.try_into().expect("exact i16")))
        .collect())
}

fn encode(ffmpeg: &Path, pcm: &Path, mp3: &Path, config: &Configuration) -> Result<(), String> {
    let mut args = vec![
        "-f".to_owned(),
        "s16le".to_owned(),
        "-ar".to_owned(),
        config.canonical_pcm.sample_rate_hz.to_string(),
        "-ac".to_owned(),
        config.canonical_pcm.channel_count.to_string(),
        "-i".to_owned(),
        pcm.to_string_lossy().into_owned(),
    ];
    args.extend(config.projection.encode_args_after_input.iter().cloned());
    args.push(mp3.to_string_lossy().into_owned());
    let stdout = run_ffmpeg(ffmpeg, &args)?;
    if !stdout.is_empty() {
        return Err("FFmpeg encode unexpectedly wrote stdout".to_owned());
    }
    Ok(())
}

fn decode_projection(
    ffmpeg: &Path,
    mp3: &Path,
    pcm: &Path,
    config: &Configuration,
) -> Result<(), String> {
    let mut args = vec!["-i".to_owned(), mp3.to_string_lossy().into_owned()];
    args.extend(config.projection.decode_args_after_input.iter().cloned());
    args.push(pcm.to_string_lossy().into_owned());
    let stdout = run_ffmpeg(ffmpeg, &args)?;
    if !stdout.is_empty() {
        return Err("FFmpeg decode unexpectedly wrote stdout".to_owned());
    }
    Ok(())
}

fn projection_cycles(
    ffmpeg: &Path,
    canonical: &[i16],
    config: &Configuration,
) -> Result<(Vec<i16>, Vec<i16>), String> {
    let scratch = tempfile::Builder::new()
        .prefix("lossytrace-codec-projection-")
        .tempdir()
        .map_err(|error| format!("create scratch directory: {error}"))?;
    let x0 = scratch.path().join("x0.s16le");
    let x1_mp3 = scratch.path().join("x1.mp3");
    let x1 = scratch.path().join("x1.s16le");
    let x2_mp3 = scratch.path().join("x2.mp3");
    let x2 = scratch.path().join("x2.s16le");
    write_s16le(&x0, canonical)?;
    encode(ffmpeg, &x0, &x1_mp3, config)?;
    decode_projection(ffmpeg, &x1_mp3, &x1, config)?;
    encode(ffmpeg, &x1, &x2_mp3, config)?;
    decode_projection(ffmpeg, &x2_mp3, &x2, config)?;
    Ok((
        read_s16le(&x1, config.canonical_pcm.channel_count)?,
        read_s16le(&x2, config.canonical_pcm.channel_count)?,
    ))
}

fn score_block(index: usize, x0: &[i16], x1: &[i16], x2: &[i16]) -> Option<BlockMeasurement> {
    let sample_count = x0.len();
    let scale_squared = 32_768.0_f64.powi(2);
    let mut signal_sum = 0.0_f64;
    let mut first_sum = 0.0_f64;
    let mut second_sum = 0.0_f64;
    let mut first_channel_sums = [0.0_f64; 2];
    let mut second_channel_sums = [0.0_f64; 2];
    for sample in 0..sample_count {
        let signal = f64::from(x0[sample]);
        let first = f64::from(i32::from(x0[sample]) - i32::from(x1[sample]));
        let second = f64::from(i32::from(x1[sample]) - i32::from(x2[sample]));
        signal_sum += signal * signal;
        first_sum += first * first;
        second_sum += second * second;
        first_channel_sums[sample % 2] += first;
        second_channel_sums[sample % 2] += second;
    }
    let signal_power = signal_sum / sample_count as f64 / scale_squared;
    let first_power = first_sum / sample_count as f64 / scale_squared;
    let second_power = second_sum / sample_count as f64 / scale_squared;
    let samples_per_channel = sample_count as f64 / 2.0;
    let first_means = first_channel_sums.map(|value| value / samples_per_channel);
    let second_means = second_channel_sums.map(|value| value / samples_per_channel);
    let mut dot = 0.0_f64;
    let mut first_centered_sum = 0.0_f64;
    let mut second_centered_sum = 0.0_f64;
    for sample in 0..sample_count {
        let channel = sample % 2;
        let first = f64::from(i32::from(x0[sample]) - i32::from(x1[sample])) - first_means[channel];
        let second =
            f64::from(i32::from(x1[sample]) - i32::from(x2[sample])) - second_means[channel];
        dot += first * second;
        first_centered_sum += first * first;
        second_centered_sum += second * second;
    }
    let cosine_denominator = (first_centered_sum * second_centered_sum).sqrt();
    if cosine_denominator == 0.0 {
        return None;
    }
    Some(BlockMeasurement {
        block_index: index,
        signal_power,
        first_residual_power: first_power,
        second_residual_power: second_power,
        r1_cycle_residual_retention: second_power / (first_power + second_power),
        r1_equivalent_db: 10.0 * (second_power / first_power).log10(),
        r2_residual_directional_recurrence: (dot / cosine_denominator).abs().clamp(0.0, 1.0),
    })
}

fn measure(
    x0: &[i16],
    x1: &[i16],
    x2: &[i16],
    config: &Configuration,
    mut support: SupportSummary,
) -> (SupportSummary, Option<ScoreSummary>, Vec<BlockMeasurement>) {
    let channels = config.canonical_pcm.channel_count;
    let frames = [
        x0.len() / channels,
        x1.len() / channels,
        x2.len() / channels,
    ];
    support.first_projection_frame_count = Some(frames[1]);
    support.second_projection_frame_count = Some(frames[2]);
    let minimum_frames = *frames.iter().min().expect("three frame counts");
    let maximum_frames = *frames.iter().max().expect("three frame counts");
    if maximum_frames - minimum_frames > config.projection.maximum_length_difference_frames {
        support.supported = false;
        support.reason = "projection_length_mismatch";
        return (support, None, Vec::new());
    }
    support.aligned_frame_count = Some(minimum_frames);
    let edge = config.measurement.edge_exclusion_frames;
    if minimum_frames <= edge * 2 {
        support.supported = false;
        support.reason = "no_measurement_interval";
        return (support, None, Vec::new());
    }
    let eligible = (minimum_frames - edge * 2) / config.measurement.block_frames;
    support.eligible_measurement_block_count = Some(eligible);
    let mut blocks = Vec::new();
    for block_index in 0..eligible {
        let start_frame = edge + block_index * config.measurement.block_frames;
        let end_frame = start_frame + config.measurement.block_frames;
        let start = start_frame * channels;
        let end = end_frame * channels;
        let Some(block) = score_block(
            block_index,
            &x0[start..end],
            &x1[start..end],
            &x2[start..end],
        ) else {
            continue;
        };
        if block.signal_power > config.measurement.minimum_power_exclusive
            && block.first_residual_power > config.measurement.minimum_power_exclusive
            && block.second_residual_power > config.measurement.minimum_power_exclusive
        {
            blocks.push(block);
        }
    }
    let supported_count = blocks.len();
    let supported_fraction = if eligible > 0 {
        supported_count as f64 / eligible as f64
    } else {
        0.0
    };
    support.supported_measurement_block_count = Some(supported_count);
    support.supported_measurement_block_fraction = Some(supported_fraction);
    if supported_count < config.measurement.minimum_supported_blocks
        || supported_fraction < config.measurement.minimum_supported_block_fraction
    {
        support.supported = false;
        support.reason = "insufficient_residual_support";
        return (support, None, blocks);
    }
    let r1: Vec<f64> = blocks
        .iter()
        .map(|block| block.r1_cycle_residual_retention)
        .collect();
    let r1_db: Vec<f64> = blocks.iter().map(|block| block.r1_equivalent_db).collect();
    let r2: Vec<f64> = blocks
        .iter()
        .map(|block| block.r2_residual_directional_recurrence)
        .collect();
    let score = ScoreSummary {
        r1_cycle_residual_retention: quantile(&r1, 0.5).expect("supported r1"),
        r1_interquartile_range: quantile(&r1, 0.75).expect("supported r1")
            - quantile(&r1, 0.25).expect("supported r1"),
        r1_equivalent_db_median: quantile(&r1_db, 0.5).expect("supported r1 db"),
        r2_residual_directional_recurrence: quantile(&r2, 0.5).expect("supported r2"),
        r2_interquartile_range: quantile(&r2, 0.75).expect("supported r2")
            - quantile(&r2, 0.25).expect("supported r2"),
    };
    support.supported = true;
    support.reason = "supported";
    (support, Some(score), blocks)
}

#[cfg(any(target_os = "macos", target_os = "linux"))]
fn peak_resident_bytes() -> Option<u64> {
    let mut usage = std::mem::MaybeUninit::<libc::rusage>::zeroed();
    // SAFETY: getrusage initializes the provided rusage structure on success.
    let result = unsafe { libc::getrusage(libc::RUSAGE_SELF, usage.as_mut_ptr()) };
    if result != 0 {
        return None;
    }
    // SAFETY: the successful call above initialized the structure.
    let usage = unsafe { usage.assume_init() };
    #[cfg(target_os = "macos")]
    let bytes = usage.ru_maxrss as u64;
    #[cfg(target_os = "linux")]
    let bytes = usage.ru_maxrss as u64 * 1024;
    Some(bytes)
}

#[cfg(not(any(target_os = "macos", target_os = "linux")))]
fn peak_resident_bytes() -> Option<u64> {
    None
}

fn write_timing(path: &Path, value: &TimingReport) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "timing output has no parent".to_owned())?;
    fs::create_dir_all(parent).map_err(|error| format!("create timing directory: {error}"))?;
    let temporary = parent.join(format!(
        ".{}.{}.tmp",
        path.file_name().unwrap_or_default().to_string_lossy(),
        std::process::id()
    ));
    let mut output = File::create(&temporary).map_err(|error| format!("create timing: {error}"))?;
    serde_json::to_writer_pretty(&mut output, value)
        .map_err(|error| format!("serialize timing: {error}"))?;
    output
        .write_all(b"\n")
        .map_err(|error| format!("write timing: {error}"))?;
    output
        .flush()
        .map_err(|error| format!("flush timing: {error}"))?;
    fs::rename(&temporary, path).map_err(|error| format!("commit timing: {error}"))
}

fn execute(
    case_id: String,
    config_path: PathBuf,
    ffmpeg: PathBuf,
    source: PathBuf,
    timing_path: PathBuf,
) -> Result<OracleReport, String> {
    let started = Instant::now();
    let config = read_configuration(&config_path)?;
    let decoded = decode_source(&ffmpeg, &source, &config.canonical_pcm)?;
    let canonicalized = canonicalize(&decoded, &config.canonical_pcm);
    let (projection_performed, support, scores, blocks, command_count) =
        if canonicalized.support.supported {
            let (x1, x2) = projection_cycles(&ffmpeg, &canonicalized.samples, &config)?;
            let (support, scores, blocks) = measure(
                &canonicalized.samples,
                &x1,
                &x2,
                &config,
                canonicalized.support,
            );
            (true, support, scores, blocks, 5)
        } else {
            (false, canonicalized.support, None, Vec::new(), 1)
        };
    let report = OracleReport {
        schema_version: 1,
        state: "codec_projection_raw_case_v1",
        feature_version: 0,
        public_verdict_enabled: false,
        case_id: case_id.clone(),
        algorithm: config.algorithm,
        projection_performed,
        support,
        scores,
        blocks,
    };
    write_timing(
        &timing_path,
        &TimingReport {
            schema_version: 1,
            state: "codec_projection_case_timing_v1",
            case_id,
            elapsed_ms: started.elapsed().as_secs_f64() * 1000.0,
            peak_resident_bytes: peak_resident_bytes(),
            ffmpeg_command_count: command_count,
        },
    )?;
    Ok(report)
}

fn main() -> Result<(), String> {
    let arguments: Vec<String> = env::args().collect();
    if arguments.len() != 6 {
        return Err(format!(
            "usage: {} CASE_ID CONFIG_JSON FFMPEG SOURCE_AUDIO TIMING_JSON",
            arguments.first().map(String::as_str).unwrap_or("oracle")
        ));
    }
    let report = execute(
        arguments[1].clone(),
        PathBuf::from(&arguments[2]),
        PathBuf::from(&arguments[3]),
        PathBuf::from(&arguments[4]),
        PathBuf::from(&arguments[5]),
    )?;
    serde_json::to_writer(io::stdout().lock(), &report)
        .map_err(|error| format!("serialize report: {error}"))?;
    println!();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_configuration() -> Configuration {
        serde_json::from_str(include_str!("../config.json")).expect("configuration")
    }

    #[test]
    fn configuration_is_valid() {
        validate_configuration(&test_configuration()).expect("valid configuration");
    }

    #[test]
    fn quantiles_use_frozen_linear_method() {
        let values = [0.0, 1.0, 2.0, 3.0];
        assert_eq!(quantile(&values, 0.25), Some(0.75));
        assert_eq!(quantile(&values, 0.5), Some(1.5));
        assert_eq!(quantile(&values, 0.75), Some(2.25));
    }

    #[test]
    fn formulas_match_golden_values() {
        let x0 = [100_i16, -100, 200, -200];
        let x1 = [90_i16, -90, 180, -180];
        let x2 = [85_i16, -85, 170, -170];
        let block = score_block(0, &x0, &x1, &x2).expect("supported block");
        assert!((block.r1_cycle_residual_retention - 0.2).abs() < 1.0e-15);
        assert!((block.r1_equivalent_db + 6.020599913279624).abs() < 1.0e-12);
        assert!((block.r2_residual_directional_recurrence - 1.0).abs() < 1.0e-15);
    }

    #[test]
    fn canonical_gain_normalization_is_stable() {
        let config = test_configuration();
        let frames = config.canonical_pcm.sample_rate_hz * 18;
        let quiet: Vec<f32> = (0..frames)
            .flat_map(|frame| {
                let value = if frame % 2 == 0 { 0.02 } else { -0.02 };
                [value, value]
            })
            .collect();
        let loud: Vec<f32> = quiet.iter().map(|value| value * 2.0).collect();
        let first = canonicalize(&quiet, &config.canonical_pcm);
        let second = canonicalize(&loud, &config.canonical_pcm);
        assert!(first.support.supported);
        assert!(second.support.supported);
        assert_eq!(first.samples, second.samples);
    }

    #[test]
    fn clipping_is_unsupported() {
        let config = test_configuration();
        let frames = config.canonical_pcm.sample_rate_hz * 18;
        let decoded = vec![1.0_f32; frames * 2];
        let result = canonicalize(&decoded, &config.canonical_pcm);
        assert!(!result.support.supported);
        assert_eq!(result.support.reason, "clipped");
    }

    #[test]
    fn score_bounds_hold_for_deterministic_sequences() {
        let x0: Vec<i16> = (0..2048).map(|value| (value % 251) as i16 - 125).collect();
        let x1: Vec<i16> = x0
            .iter()
            .enumerate()
            .map(|(index, value)| value.saturating_sub((index % 7) as i16 - 3))
            .collect();
        let x2: Vec<i16> = x1
            .iter()
            .enumerate()
            .map(|(index, value)| value.saturating_add((index % 5) as i16 - 2))
            .collect();
        let block = score_block(0, &x0, &x1, &x2).expect("supported block");
        assert!((0.0..=1.0).contains(&block.r1_cycle_residual_retention));
        assert!((0.0..=1.0).contains(&block.r2_residual_directional_recurrence));
    }
}
