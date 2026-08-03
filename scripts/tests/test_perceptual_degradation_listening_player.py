from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAYER = ROOT / "research" / "listening-player"
EVIDENCE_V1 = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-player-dry-run-observed-20260803-001.json"
)
EVIDENCE_V2 = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-player-dry-run-observed-20260803-002.json"
)
EVIDENCE_V3 = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-player-dry-run-observed-20260803-003.json"
)
SYNTHETIC_MANIFEST = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-stimulus-manifest.synthetic.json"
)
STIMULUS_SCHEMA = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-stimulus-manifest.schema.json"
)
ALLOCATOR = ROOT / "scripts" / "perceptual_degradation_listening_allocation.py"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for key in ("href", "src"):
            if values.get(key):
                self.references.append(values[key] or "")


class ListeningPlayerTest(unittest.TestCase):
    def test_historical_v1_evidence_remains_non_evidentiary(self) -> None:
        evidence = json.loads(EVIDENCE_V1.read_text(encoding="utf-8"))
        bindings = evidence["source_bindings"]
        expected_hashes = {
            "index_html_sha256": "f23e5f0b9574f0b6140dd09317daac08b4f40c58dc0fd4cd05dec9f33ba489de",
            "style_css_sha256": "d37ff69c92fc8d986c3027395394d1eea0a3722d0ee108b4ba8c9c2ea9e00caf",
            "player_javascript_sha256": "c0bfe0555362e87d2d45fc374e75bd4e1dab123d28be6fad372390261e230087",
            "favicon_svg_sha256": "2da3789b595cd99d06a7141004bd5e18b9dc459cbd48345040a0389634b56f27",
            "offline_test_sha256": "e6fa859420203ccdb681533b9981a0620ae1f4db839a0a48d29b0f32677371e6",
        }
        self.assertEqual(expected_hashes, bindings)
        self.assertTrue(
            evidence["observed_checks"][
                "operator_confirmed_all_generated_sounds_audible"
            ]
        )
        self.assertFalse(
            evidence["privacy_and_evidence_boundary"]["listener_response_collected"]
        )
        self.assertFalse(evidence["player_implementation_frozen"])
        self.assertFalse(evidence["playback_qualification_frozen"])
        self.assertFalse(evidence["human_collection_authorized"])

    def test_v2_evidence_binds_current_sources_and_remains_non_evidentiary(self) -> None:
        evidence = json.loads(EVIDENCE_V2.read_text(encoding="utf-8"))
        bindings = evidence["source_bindings"]
        expected = {
            "index_html_sha256": PLAYER / "index.html",
            "style_css_sha256": PLAYER / "style.css",
            "assignment_javascript_sha256": PLAYER / "synthetic-assignment.js",
            "player_javascript_sha256": PLAYER / "player.js",
            "favicon_svg_sha256": PLAYER / "favicon.svg",
            "stimulus_manifest_sha256": SYNTHETIC_MANIFEST,
            "stimulus_schema_sha256": STIMULUS_SCHEMA,
            "allocator_sha256": ALLOCATOR,
        }
        for key, path in expected.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), bindings[key])
        self.assertEqual(
            "349187da820b0b55894858e9fd01823a56cd7fe258e68f75cccc347de37690f9",
            bindings["offline_test_sha256"],
        )
        self.assertEqual(
            "assignment-4e73c040a36c3f7a0c0db1a0",
            evidence["assignment_provenance"]["assignment_id"],
        )
        self.assertTrue(
            evidence["assignment_provenance"]["exact_allocator_replay_passed"]
        )
        self.assertTrue(evidence["environment"]["browser_binary_binding_complete"])
        self.assertFalse(
            evidence["observed_checks"]["operator_audibility_confirmation_collected"]
        )
        self.assertFalse(
            evidence["privacy_and_evidence_boundary"]["listener_response_collected"]
        )
        self.assertFalse(evidence["player_implementation_frozen"])
        self.assertFalse(evidence["playback_qualification_frozen"])
        self.assertFalse(evidence["human_collection_authorized"])

    def test_v3_records_only_current_operator_audibility_check(self) -> None:
        evidence = json.loads(EVIDENCE_V3.read_text(encoding="utf-8"))
        bindings = evidence["source_bindings"]
        expected = {
            "index_html_sha256": PLAYER / "index.html",
            "style_css_sha256": PLAYER / "style.css",
            "assignment_javascript_sha256": PLAYER / "synthetic-assignment.js",
            "player_javascript_sha256": PLAYER / "player.js",
            "favicon_svg_sha256": PLAYER / "favicon.svg",
            "offline_test_sha256": Path(__file__),
            "stimulus_manifest_sha256": SYNTHETIC_MANIFEST,
            "stimulus_schema_sha256": STIMULUS_SCHEMA,
            "allocator_sha256": ALLOCATOR,
        }
        for key, path in expected.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), bindings[key])
        self.assertEqual(
            "perceptual-degradation-listening-player-dry-run-20260803-002",
            evidence["supersedes_evidence_id"],
        )
        self.assertEqual(
            "direct_operator_statement_after_v2_control_playback",
            evidence["operator_check"]["confirmation_source"],
        )
        self.assertTrue(
            evidence["operator_check"][
                "operator_confirmed_all_generated_sounds_audible"
            ]
        )
        self.assertTrue(
            evidence["observed_checks"]["operator_audibility_confirmation_collected"]
        )
        boundary = evidence["privacy_and_evidence_boundary"]
        self.assertFalse(boundary["listener_response_collected"])
        self.assertFalse(boundary["operator_confirmation_is_listening_truth"])
        self.assertFalse(boundary["operator_confirmation_is_calibration_evidence"])
        self.assertFalse(boundary["browser_automation_values_are_listening_truth"])
        self.assertFalse(boundary["prior_v1_operator_confirmation_reused_for_v2"])
        for key in (
            "player_implementation_frozen",
            "playback_qualification_frozen",
            "human_collection_authorized",
            "recruitment_authorized",
            "response_storage_authorized",
            "public_verdict_enabled",
        ):
            self.assertFalse(evidence[key])

    def test_player_has_no_external_resources(self) -> None:
        parser = LinkParser()
        parser.feed((PLAYER / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(
            ["favicon.svg", "style.css", "synthetic-assignment.js", "player.js"],
            parser.references,
        )
        for reference in parser.references:
            self.assertNotIn("://", reference)
            self.assertTrue((PLAYER / reference).is_file())

    def test_player_has_no_network_identity_or_persistence_api(self) -> None:
        source = (PLAYER / "player.js").read_text(encoding="utf-8")
        forbidden = (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "sendBeacon",
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "getUserMedia",
            "MediaRecorder",
            "document.cookie",
        )
        for token in forbidden:
            self.assertNotIn(token, source)
        self.assertIn("identity_included: false", source)
        self.assertIn("network_storage_used: false", source)

    def test_protocol_sequence_is_explicit(self) -> None:
        source = (PLAYER / "player.js").read_text(encoding="utf-8")
        self.assertIn('byId("forced-choice").disabled = true', source)
        self.assertIn('byId("grade-field").disabled = false', source)
        self.assertIn("state.subtleHeard.size !== 2", source)
        self.assertIn("Object.keys(state.mushraRatings).length", source)

    def test_player_consumes_opaque_assignment_without_roles_or_recipes(self) -> None:
        assignment_source = (PLAYER / "synthetic-assignment.js").read_text(
            encoding="utf-8"
        )
        player = (PLAYER / "player.js").read_text(encoding="utf-8")
        self.assertIn("globalThis.LOSSYTRACE_ASSIGNMENT", assignment_source)
        self.assertIn("const assignment = globalThis.LOSSYTRACE_ASSIGNMENT", player)
        for token in ("condition_class", '"role"', "recipe_", "generator_source"):
            self.assertNotIn(token, assignment_source)
        self.assertIn('condition_recipes_included": false', assignment_source)

        prefix = "globalThis.LOSSYTRACE_ASSIGNMENT = Object.freeze(\n"
        assignment = json.loads(
            assignment_source.split(prefix, 1)[1].rsplit("\n);\n", 1)[0]
        )
        stimulus_ids = set()
        for block in assignment["blocks"]:
            for trial in block["trials"]:
                stimulus_ids.add(trial["visible_reference_id"])
                stimulus_ids.update(
                    positioned["stimulus_id"]
                    for positioned in trial["candidate_positions"]
                )
        registry_ids = set(
            re.findall(r'^  "(stimulus-[^"]+)": "g[0-9]+",$', player, re.MULTILINE)
        )
        self.assertEqual(stimulus_ids, registry_ids)
        for stimulus_id in stimulus_ids:
            for leaked_role in ("reference", "hidden", "condition", "anchor"):
                self.assertNotIn(leaked_role, stimulus_id)

        manifest = json.loads(SYNTHETIC_MANIFEST.read_text(encoding="utf-8"))
        player_sha256 = hashlib.sha256((PLAYER / "player.js").read_bytes()).hexdigest()
        for stimulus in manifest["stimuli"]:
            delivery = stimulus["delivery"]
            self.assertEqual(
                hashlib.sha256(delivery["recipe_id"].encode()).hexdigest(),
                delivery["recipe_id_sha256"],
            )
            self.assertEqual(player_sha256, delivery["generator_source_sha256"])

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_javascript_parses(self) -> None:
        subprocess.run(
            ["node", "--check", str(PLAYER / "player.js")],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
