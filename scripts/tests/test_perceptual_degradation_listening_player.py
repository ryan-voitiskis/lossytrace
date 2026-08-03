from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAYER = ROOT / "research" / "listening-player"
EVIDENCE = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-player-dry-run-observed-20260803-001.json"
)


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
    def test_observed_evidence_binds_sources_and_remains_non_evidentiary(self) -> None:
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        bindings = evidence["source_bindings"]
        expected = {
            "index_html_sha256": PLAYER / "index.html",
            "style_css_sha256": PLAYER / "style.css",
            "player_javascript_sha256": PLAYER / "player.js",
            "favicon_svg_sha256": PLAYER / "favicon.svg",
        }
        for key, path in expected.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), bindings[key])
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

    def test_player_has_no_external_resources(self) -> None:
        parser = LinkParser()
        parser.feed((PLAYER / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(["favicon.svg", "style.css", "player.js"], parser.references)
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
