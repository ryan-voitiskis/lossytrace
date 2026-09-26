use assert_cmd::Command;
use serde_json::Value;
use std::f32::consts::TAU;

#[test]
fn explain_prints_bundled_guide_without_creating_files() {
    let directory = tempfile::tempdir().unwrap();
    let output = Command::cargo_bin("lossytrace")
        .unwrap()
        .current_dir(directory.path())
        .arg("explain")
        .output()
        .unwrap();
    assert!(output.status.success());
    assert!(output.stderr.is_empty());
    assert_eq!(output.stdout, include_bytes!("../docs/inspection-guide.md"));
    assert_eq!(std::fs::read_dir(directory.path()).unwrap().count(), 0);
}

#[test]
fn explain_does_not_accept_an_audio_target() {
    Command::cargo_bin("lossytrace")
        .unwrap()
        .args(["explain", "not-an-audio-input.wav"])
        .assert()
        .failure();
}

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

    // The explanation is separate from the unchanged evidence envelope.
    let expected_fields = [
        "schema_version",
        "state",
        "public_verdict_enabled",
        "input_sha256",
        "analyzed_sample_count",
        "analyzed_duration_seconds",
        "truncated_by_limit",
        "source_facts",
        "compression_trace",
    ];
    let fields = report.as_object().unwrap();
    assert_eq!(fields.len(), expected_fields.len());
    for field in expected_fields {
        assert!(fields.contains_key(field));
    }
    let guide = include_str!("../docs/inspection-guide.md");
    for section in ["source_facts", "compression_trace"] {
        for field in report[section].as_object().unwrap().keys() {
            assert!(
                guide.contains(&format!("`{field}`")),
                "undocumented {field}"
            );
        }
    }
}
