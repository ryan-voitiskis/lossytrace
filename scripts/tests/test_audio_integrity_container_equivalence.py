import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "stage-audio-integrity-container-equivalence.py"
)
SPEC = importlib.util.spec_from_file_location("container_equivalence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ContainerEquivalenceTests(unittest.TestCase):
    def manifest(self):
        cases = []
        for domain in ("domain-a", "domain-b"):
            for group_index in range(5):
                group = f"{domain}-group-{group_index}"
                cases.extend(
                    [
                        {
                            "case_id": f"{group}-reference",
                            "source_group": group,
                            "source_domain": domain,
                            "class": "untouched_lossless",
                            "expectation": "negative",
                        },
                        {
                            "case_id": f"{group}-lowpass",
                            "source_group": group,
                            "source_domain": domain,
                            "class": "lowpass_only_pcm",
                            "expectation": "negative",
                        },
                    ]
                )
        return {"cases": cases}

    def test_selection_is_deterministic_and_uses_preferred_references(self):
        first = MODULE.select_references(self.manifest(), 2)
        second = MODULE.select_references(self.manifest(), 2)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertTrue(all(case["class"] == "untouched_lossless" for case in first))
        counts = {domain: 0 for domain in ("domain-a", "domain-b")}
        for case in first:
            counts[case["source_domain"]] += 1
        self.assertEqual(counts, {"domain-a": 2, "domain-b": 2})

    def test_sanitizes_both_private_roots(self):
        command = ["ffmpeg", "-i", "/private/corpus/source.wav", "/private/run/out.flac"]
        self.assertEqual(
            MODULE.sanitize(command, Path("/private/corpus"), Path("/private/run")),
            ["ffmpeg", "-i", "<CORPUS_ROOT>/source.wav", "<OUTPUT_ROOT>/out.flac"],
        )

    def test_encoder_probe_is_stereo_for_native_vorbis(self):
        command = MODULE.encoder_probe_command(
            "ffmpeg", ["-c:a", "vorbis"], 44100, Path("probe.ogg")
        )
        self.assertEqual(command[command.index("-ac") + 1], "2")
        self.assertEqual(command[command.index("-ar") + 1], "44100")
        self.assertLess(command.index("-ac"), command.index("-c:a"))

    def test_opus_profile_uses_a_supported_sample_rate(self):
        opus = next(codec for codec in MODULE.CODECS if codec["id"] == "opus_96")
        self.assertEqual(opus["sample_rate_hz"], 48000)
        self.assertFalse(opus["include_lossy_original_case"])
        self.assertIn("no_opus_codec", opus["original_omission_reason"])


if __name__ == "__main__":
    unittest.main()
