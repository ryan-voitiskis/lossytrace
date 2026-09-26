from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import lossprint_challenge as challenge


def cases():
    rows = []
    for domain in ("a", "b"):
        for group in range(8):
            ref_id = f"{domain}-{group}-negative"
            for label in ("negative", "controlled_positive"):
                identity = f"{domain}-{group}-{label}"
                rows.append({"case_id": identity, "source_domain": domain,
                             "source_group": f"{domain}-{group}", "partition_group": f"{domain}-{group}",
                             "expectation": label, "reference_case_id": ref_id if label != "negative" else None,
                             "evidence_partition": "mechanism_development", "_analysis_pcm_sha256": identity,
                             "audio_sha256": identity, "audio_bytes": 10, "frame_count": 96000,
                             "sample_rate_hz": 48000, "channel_count": 1, "lossless_wrapper_id": "wav16",
                             "codec_family": "mp3" if label != "negative" else "none",
                             "post_transform_ids": [], "history_class": label})
    return rows


class SelectionTests(unittest.TestCase):
    def select(self, rows=None, **kwargs):
        return challenge.select_cases(cases() if rows is None else rows, {"a", "b"}, **kwargs)

    def test_fixed_selection_is_order_independent(self):
        forward = self.select()
        self.assertEqual(forward, self.select(list(reversed(cases()))))
        self.assertEqual(len(forward[0]), 20)
        self.assertEqual(len(forward[1]), 20)

    def test_all_selected_variants_retained(self):
        selected, _ = self.select()
        variant = dict(selected[0], case_id="new", audio_sha256="new", _analysis_pcm_sha256="new")
        result, _ = self.select(cases() + [variant])
        self.assertEqual(len(result), 21)

    def test_no_truncation_at_cap(self):
        with self.assertRaisesRegex(ValueError, "cap"):
            self.select(cap=19)

    def test_duplicate_case_fails(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.select(cases() + [cases()[0]])

    def test_sealed_partition_fails(self):
        rows = cases()
        rows[0]["evidence_partition"] = "external_transfer"
        with self.assertRaisesRegex(ValueError, "mechanism"):
            self.select(rows)

    def test_insufficient_groups_fails(self):
        with self.assertRaisesRegex(ValueError, "insufficient"):
            self.select(per_domain=9)

    def test_wrong_domain_fails(self):
        with self.assertRaisesRegex(ValueError, "domains"):
            self.select([c for c in cases() if c["source_domain"] == "a"])

    def test_reference_outside_selection_fails(self):
        rows = cases()
        for c in rows:
            if c["expectation"] == "controlled_positive":
                c["reference_case_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "reference"):
            self.select(rows)

    def test_exact_aliases_deduplicated_but_kept(self):
        selected, _ = self.select()
        alias = dict(selected[0], case_id="alias")
        rows, reps = self.select(cases() + [alias])
        self.assertEqual((len(rows), len(reps)), (21, 20))
        shared = [c for c in rows if c["audio_sha256"] == alias["audio_sha256"]]
        self.assertEqual(len({c["representative_case_id"] for c in shared}), 1)

    def test_inconsistent_alias_fails(self):
        selected, _ = self.select()
        alias = dict(selected[0], case_id="alias", audio_sha256="different")
        with self.assertRaisesRegex(ValueError, "aliases"):
            self.select(cases() + [alias])

    def test_support_boundary(self):
        case = cases()[0]
        self.assertIsNone(challenge.unsupported_reason(case))
        for mutation in ({"frame_count": 95999}, {"sample_rate_hz": 4000}, {"channel_count": 6}):
            self.assertIsNotNone(challenge.unsupported_reason(dict(case, **mutation)))

    def test_public_summary_has_no_identities(self):
        rows, reps = self.select()
        summary = challenge.summarize(rows, reps)
        self.assertEqual(summary["domain_group_entries"], 10)
        self.assertFalse(summary["scores_opened"])
        self.assertEqual(summary["planned_slots"], 40)
        challenge.assert_public_path_free(summary)

    def test_negative_metadata_may_omit_codec_and_transforms(self):
        rows, reps = self.select()
        for c in rows:
            if c["expectation"] == "negative":
                del c["codec_family"]
                del c["post_transform_ids"]
        summary = challenge.summarize(rows, reps)
        self.assertEqual(summary["domains"]["a"]["codecs"]["none"], 5)


if __name__ == "__main__":
    unittest.main()
