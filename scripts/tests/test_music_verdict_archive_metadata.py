"""Offline tests for metadata intake boundaries; no real source qualification."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

SCRIPT = Path(__file__).resolve().parents[1] / "music_verdict_archive_metadata.py"
SPEC = importlib.util.spec_from_file_location("archive_metadata", SCRIPT)
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


class ArchiveMetadataTest(unittest.TestCase):
    def test_item_endpoint_cannot_download_files_or_escape_origin(self):
        self.assertEqual(metadata.request_url(item="a-1.flac"), "https://archive.org/metadata/a-1.flac")
        for item in ("../download/file", "//evil.org", "a?b", "a/b", "", "a#b", "%2e%2e"):
            with self.subTest(item=item), self.assertRaises(ValueError):
                metadata.request_url(item=item)

    def test_search_query_is_encoded_data_and_sorted(self):
        url = metadata.request_url(query="a&output=xml", rows=1000, page=2)
        parts = urlparse(url)
        self.assertEqual(parts.netloc, "archive.org")
        self.assertEqual(parts.path, "/advancedsearch.php")
        query = parse_qs(parts.query)
        self.assertEqual(query["q"], ["a&output=xml"])
        self.assertEqual(query["output"], ["json"])
        self.assertEqual(query["sort[]"], ["identifier asc"])

    def test_request_bounds(self):
        for kwargs in ({}, {"query": "q", "item": "id"}, {"query": ""},
                       {"query": "q", "rows": 1001}, {"query": "q", "page": 0},
                       {"query": "q", "rows": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                metadata.request_url(**kwargs)

    def test_creator_strings_never_become_independent_sources(self):
        doc = {"response": {"numFound": 3, "docs": [
            {"creator": "Artist", "source": "WAV", "licenseurl": "CC0"},
            {"creator": ["ARTIST", "Guest"], "lineage": "recorded"}, {}]}}
        result = metadata.summarize(doc, is_search=True)
        self.assertEqual(result["distinct_creator_strings_casefolded"], 2)
        self.assertEqual(result["rows_with_source_text"], 1)
        self.assertFalse(result["creator_strings_are_independent_groups"])
        self.assertFalse(result["source_qualification_performed"])
        self.assertFalse(result["execution_ready"])

    def test_item_summary_never_qualifies_license_or_provenance(self):
        result = metadata.summarize({"metadata": {"source": "direct PCM"}}, is_search=False)
        self.assertEqual(result["returned_rows"], 1)
        self.assertFalse(result["audio_accessed"])
        self.assertFalse(result["source_qualification_performed"])

    def test_malformed_or_error_response_fails(self):
        for document in ([], {}, {"error": "bad"}, {"response": {"numFound": 0, "docs": [{}]}},
                         {"response": {"numFound": 1, "docs": ["bad"]}}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                metadata.summarize(document, is_search=True)

    def test_redirect_fails_closed(self):
        with self.assertRaises(ValueError):
            metadata.NoRedirect().redirect_request(None, None, 302, None, {}, "https://archive.org/download/x")

    def test_existing_output_never_overwritten_or_networked(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(metadata.urllib.request, "build_opener") as opener:
            with self.assertRaises(FileExistsError):
                metadata.collect("https://archive.org/metadata/x", Path(directory), is_search=False)
            opener.assert_not_called()

    def test_collector_rejects_nonmetadata_urls_before_any_side_effect(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(metadata.urllib.request, "build_opener") as opener:
            out = Path(directory) / "new"
            for url in ("https://archive.org/download/x", "http://archive.org/metadata/x",
                        "https://127.0.0.1/metadata/x", "https://archive.org.evil.test/metadata/x",
                        "https://archive.org/metadata/../download/x", "https://archive.org/metadata/x#fragment"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    metadata.collect(url, out, is_search=False)
            self.assertFalse(out.exists())
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
