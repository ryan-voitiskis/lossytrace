use assert_cmd::Command;
use serde_json::Value;
use std::f32::consts::TAU;

#[test]
fn analyze_emits_explicitly_experimental_evidence() {
    let directory = tempfile::tempdir().unwrap();
    let audio_path = directory.path().join("fixture.wav");
    let specification = hound::WavSpec {
        channels: 1,
        sample_rate: 44_100,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };
    let mut writer = hound::WavWriter::create(&audio_path, specification).unwrap();
    for index in 0..44_100 * 3 {
        let time = index as f32 / 44_100.0;
        let sample = ((440.0 * TAU * time).sin() * 0.5 * i16::MAX as f32) as i16;
        writer.write_sample(sample).unwrap();
    }
    writer.finalize().unwrap();

    let output = Command::cargo_bin("lossytrace")
        .unwrap()
        .args(["analyze", audio_path.to_str().unwrap()])
        .output()
        .unwrap();
    assert!(output.status.success());
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["schema_version"], 1);
    assert_eq!(report["state"], "experimental_measurements_only");
    assert_eq!(report["public_verdict_enabled"], false);
    assert_eq!(report["compression_trace"]["feature_version"], 0);
    assert_eq!(report["input_sha256"].as_str().unwrap().len(), 64);
}
