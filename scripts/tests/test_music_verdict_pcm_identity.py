"""Exact signal aliases and historical references must stay together in inventory v3."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import music_verdict_study as study
from test_music_verdict_study import inventory

has_audio_tools = all(importlib.util.find_spec(x) for x in ("soundfile", "numpy"))
if has_audio_tools:
    import numpy as np
    import soundfile as sf
    from music_verdict_pcm_identity import identify


class InventoryPCMTest(unittest.TestCase):
    def setUp(self):
        self.doc = inventory()
        self.doc.update(schema_version=3, identity_references=[])
        for row in self.doc["sources"]:
            row["canonical_pcm_sha256"] = hashlib.sha256(("PCM:" + row["source_id"]).encode()).hexdigest()

    def test_rewrapped_identical_audio_across_splits(self):
        self.assertEqual(study.audit_inventory(self.doc)["errors"], {})
        train, evaluation = self.doc["sources"][0], self.doc["sources"][-1]
        evaluation["canonical_pcm_sha256"] = train["canonical_pcm_sha256"]
        self.assertIn("cross_partition_identity_component", study.audit_inventory(self.doc)["errors"])

    def test_pcm_alias_carries_complete_copy_history(self):
        row = self.doc["sources"][0]
        row["consumed"] = False
        ref = dict(source_id="old", artist_ids=[], session_ids=[], lineage_ids=[],
                   audio_sha256=None, canonical_pcm_sha256=row["canonical_pcm_sha256"],
                   history_status="consumed", identity_refs=["synthetic old ledger"])
        self.doc["identity_references"].append(ref)
        self.assertEqual(study.audit_inventory(self.doc)["errors"], {"unlabelled_consumed_reference_copy": 1})
        ref["history_status"] = "sealed"
        self.assertEqual(study.audit_inventory(self.doc)["errors"], {"historically_sealed_reference_copy": 1})
        ref["canonical_pcm_sha256"] = None
        self.assertEqual(study.audit_inventory(self.doc)["errors"], {})
        ref["canonical_pcm_sha256"] = "bad"
        self.assertIn("invalid_identity_reference", study.audit_inventory(self.doc)["errors"])

    def test_missing_and_contradictory_sample_identities_fail(self):
        first, second = self.doc["sources"][:2]
        second["audio_sha256"] = first["audio_sha256"]
        self.assertIn("conflicting_pcm_commitment_for_file", study.audit_inventory(self.doc)["errors"])
        first["canonical_pcm_sha256"] = None
        self.assertIn("invalid_or_missing_metadata", study.audit_inventory(self.doc)["errors"])


@unittest.skipUnless(has_audio_tools, "requires research audio dependencies")
class FingerprintTest(unittest.TestCase):
    def test_native_layout_depth_and_low_bits(self):
        # More than one decoding block. Cover signed endpoints and adjacent samples.
        mono = np.resize(np.array([-32768, -1, 0, 1, 32767], dtype=np.int32), 65539) << 16
        stereo = np.column_stack((mono, -1 - mono)).astype("int32")
        stereo[:, 1] &= -65536
        with tempfile.TemporaryDirectory() as directory:
            def key(name, array, rate, subtype):
                path = Path(directory) / name
                sf.write(path, array, rate, subtype=subtype)
                file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                return identify(path, file_hash)["canonical_pcm_sha256"]

            canonical = key("x.wav", stereo, 44100, "PCM_16")
            self.assertEqual(canonical, key("x.flac", stereo, 44100, "PCM_24"))
            expected = hashlib.sha256(b"lossytrace:music-verdict-v1:native-s32le:v1\0"
                                      + struct.pack("<IHQ", 44100, 2, len(stereo))
                                      + stereo.astype("<i4").tobytes()).hexdigest()
            self.assertEqual(canonical, expected)
            self.assertNotEqual(canonical, key("swapped.wav", stereo[:, ::-1], 44100, "PCM_16"))
            self.assertNotEqual(canonical, key("rate.wav", stereo, 48000, "PCM_16"))
            self.assertNotEqual(canonical, key("mono.wav", stereo.ravel(), 44100, "PCM_16"))
            stereo[-1, 0] += 256
            self.assertNotEqual(canonical, key("one-bit.flac", stereo, 44100, "PCM_24"))
            with self.assertRaises(ValueError):
                identify(Path(directory) / "x.wav", "0" * 64)
            with self.assertRaises(ValueError):
                key("float.wav", np.zeros(32), 44100, "FLOAT")
