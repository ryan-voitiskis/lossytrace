use assert_cmd::Command;
use serde_json::Value;
use std::{fs, path::Path};

const SAMPLES: [i32; 10] = [-32768, 32767, -1, 2, 0, 1, 30000, -20000, 1234, 4321];
// SAMPLES promoted to 24 bits and encoded with libFLAC 1.5.0, STREAMINFO only.
const FLAC: &[u8] = &[
    0x66, 0x4c, 0x61, 0x43, 0x80, 0x0, 0x0, 0x22, 0x10, 0x0, 0x10, 0x0, 0x0, 0x0, 0x21, 0x0, 0x0,
    0x21, 0xa, 0xc4, 0x43, 0x70, 0x0, 0x0, 0x0, 0x5, 0x18, 0x7a, 0x72, 0x11, 0xab, 0x6f, 0x34,
    0xda, 0x88, 0x82, 0xec, 0x9a, 0x9c, 0x9d, 0xf, 0x6b, 0xff, 0xf8, 0x69, 0x1c, 0x0, 0x4, 0x8,
    0x3, 0x1, 0x80, 0x0, 0xff, 0xff, 0x0, 0x0, 0x75, 0x30, 0x4, 0xd2, 0x3, 0x1, 0x7f, 0xff, 0x0,
    0x2, 0x0, 0x1, 0xb1, 0xe0, 0x10, 0xe1, 0xa8, 0x3d,
];

fn wav(path: &Path, samples: &[i32], bits: u16, channels: u16, rate: u32) {
    let spec = hound::WavSpec {
        channels,
        sample_rate: rate,
        bits_per_sample: bits,
        sample_format: hound::SampleFormat::Int,
    };
    let mut writer = hound::WavWriter::create(path, spec).unwrap();
    for sample in samples {
        writer.write_sample(*sample).unwrap();
    }
    writer.finalize().unwrap();
}

fn command(left: &Path, right: &Path) -> Command {
    let mut cmd = Command::cargo_bin("lossytrace").unwrap();
    cmd.arg("compare").arg(left).arg(right).arg("--pretty");
    cmd
}

fn compare(left: &Path, right: &Path) -> Value {
    let result = command(left, right).assert().success();
    serde_json::from_slice(&result.get_output().stdout).unwrap()
}

#[test]
fn exact_depth_promotion_and_rewrap_match_reference_digest() {
    let dir = tempfile::tempdir().unwrap();
    let left = dir.path().join("first.wav");
    let right = dir.path().join("renamed.bin");
    wav(&left, &SAMPLES, 16, 2, 44100);
    fs::write(&right, FLAC).unwrap();
    let before = fs::read(&left).unwrap();
    let report = compare(&left, &right);
    assert_eq!(report["same_decoded_audio"], true);
    assert_eq!(report["left"]["bits_per_sample"], 16);
    assert_eq!(report["right"]["bits_per_sample"], 24);
    for side in ["left", "right"] {
        assert_eq!(report[side]["frames"], 5);
        assert_eq!(report[side]["channel_count"], 2);
        // Independently calculated with the Python research fingerprint.
        assert_eq!(
            report[side]["canonical_pcm_sha256"],
            "ff4aa28ef18cb0c17448793cbb734f9ec01cdf93a17a501ab498c9b885543666"
        );
    }
    assert_eq!(fs::read(left).unwrap(), before);
    assert_eq!(fs::read(right).unwrap(), FLAC);
}

#[test]
fn exact_comparison_preserves_sample_precision_channels_rate_and_length() {
    let dir = tempfile::tempdir().unwrap();
    let left = dir.path().join("left.flac");
    let right = dir.path().join("right.wav");
    fs::write(&left, FLAC).unwrap();
    let mut samples = SAMPLES.map(|s| s << 8);
    wav(&right, &samples, 24, 2, 44100);
    assert_eq!(compare(&left, &right)["same_decoded_audio"], true);
    for (channels, rate, count) in [(1, 44100, 10), (2, 48000, 10), (2, 44100, 8)] {
        wav(&right, &samples[..count], 24, channels, rate);
        assert_eq!(compare(&left, &right)["same_decoded_audio"], false);
    }
    samples[9] += 1;
    wav(&right, &samples, 24, 2, 44100);
    assert_eq!(compare(&left, &right)["same_decoded_audio"], false);
    samples[9] -= 1;
    samples.swap(0, 1);
    wav(&right, &samples, 24, 2, 44100);
    assert_eq!(compare(&left, &right)["same_decoded_audio"], false);
}

#[test]
fn invalid_inputs_produce_no_comparison() {
    let dir = tempfile::tempdir().unwrap();
    let left = dir.path().join("valid.wav");
    let right = dir.path().join("other.wav");
    wav(&left, &SAMPLES, 16, 2, 44100);
    let mut partial_frame = fs::read(&left).unwrap();
    // Hound writes the conventional 44-byte header for 16-bit PCM.
    partial_frame.extend_from_slice(&[0, 0]);
    let size = partial_frame.len() as u32;
    partial_frame[4..8].copy_from_slice(&(size - 8).to_le_bytes());
    partial_frame[40..44].copy_from_slice(&(size - 44).to_le_bytes());
    let mut bad_rate = fs::read(&left).unwrap();
    bad_rate[24..28].copy_from_slice(&0_u32.to_le_bytes());
    let mut bad_checksum = FLAC.to_vec();
    bad_checksum[26] ^= 1;
    for data in [
        partial_frame,
        bad_rate,
        bad_checksum,
        FLAC[..FLAC.len() - 2].to_vec(),
        b"ID3".to_vec(),
    ] {
        fs::write(&right, data).unwrap();
        command(&left, &right).assert().code(1).stdout("");
    }
    wav(&right, &SAMPLES, 32, 2, 44100);
    command(&left, &right).assert().code(1).stdout("");
}
