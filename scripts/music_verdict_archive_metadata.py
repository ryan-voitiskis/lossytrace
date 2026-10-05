#!/usr/bin/env python3
"""Read public Internet Archive metadata only; never fetch or qualify audio.

One request per invocation, no credentials, redirects, retries or file-download
endpoints. Snapshots stay outside Git; the research ledger records conclusions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
FIELDS = ("identifier", "creator", "title", "date", "collection", "licenseurl", "source", "lineage")
USER_AGENT = "LossyTraceResearch/0.1 (OpenAI GPT-5 based Codex; metadata-only)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect refused; inspect destination separately")


def request_url(*, query=None, item=None, rows=100, page=1):
    if (query is None) == (item is None):
        raise ValueError("choose exactly one query or item")
    if item is not None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", item):
            raise ValueError("invalid item identifier")
        return "https://archive.org/metadata/" + item
    if not isinstance(query, str) or not query.strip() or len(query) > 4096:
        raise ValueError("invalid query")
    if type(rows) is not int or not 1 <= rows <= 1000 or type(page) is not int or page < 1:
        raise ValueError("invalid page or rows")
    params = {"q": query, "fl[]": FIELDS, "sort[]": "identifier asc",
              "rows": rows, "page": page, "output": "json"}
    return "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)


def strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return []


def summarize(document, *, is_search):
    if not isinstance(document, dict) or "error" in document:
        raise ValueError("invalid or error metadata response")
    if is_search:
        response = document.get("response")
        if not isinstance(response, dict) or not isinstance(response.get("docs"), list):
            raise ValueError("missing search response")
        rows = response["docs"]
        total = response.get("numFound")
        if type(total) is not int or total < len(rows):
            raise ValueError("invalid result count")
    else:
        if not isinstance(document.get("metadata"), dict):
            raise ValueError("missing item metadata")
        rows, total = [document["metadata"]], 1
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid metadata row")
    creators = {s.casefold().strip() for row in rows for s in strings(row.get("creator"))}
    licenses = Counter(s for row in rows for s in strings(row.get("licenseurl")))
    return {
        "result_count": total,
        "returned_rows": len(rows),
        "distinct_creator_strings_casefolded": len(creators),
        "creator_strings_are_independent_groups": False,
        "rows_with_source_text": sum(bool(strings(r.get("source"))) for r in rows),
        "rows_with_lineage_text": sum(bool(strings(r.get("lineage"))) for r in rows),
        "license_url_counts": dict(sorted(licenses.items())),
        "source_qualification_performed": False,
        "audio_accessed": False,
        "execution_ready": False,
    }


def collect(url, out, *, is_search):
    parsed = urllib.parse.urlsplit(url)
    expected_path = "/advancedsearch.php" if is_search else "/metadata/"
    if (parsed.scheme != "https" or parsed.netloc != "archive.org" or parsed.fragment
            or (is_search and parsed.path != expected_path)
            or (not is_search and not re.fullmatch(r"/metadata/[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", parsed.path))):
        raise ValueError("only public Archive metadata endpoints are allowed")
    # Create a fresh directory before networking; never overwrite an earlier run.
    out.mkdir(parents=False, exist_ok=False)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=30) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise ValueError("expected HTTP 200 JSON metadata")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeded per-request safety limit")
    document = json.loads(raw)
    summary = summarize(document, is_search=is_search)
    receipt = {"schema_version": 1, "retrieved_at": datetime.now(timezone.utc).isoformat(),
               "url": url, "user_agent": USER_AGENT, "byte_count": len(raw),
               "sha256": hashlib.sha256(raw).hexdigest(), "summary": summary}
    with (out / "response.json").open("xb") as handle:
        handle.write(raw)
    with (out / "receipt.json").open("x") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--query")
    choice.add_argument("--item")
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True, help="new snapshot directory; metadata only")
    args = parser.parse_args()
    try:
        url = request_url(query=args.query, item=args.item, rows=args.rows, page=args.page)
        receipt = collect(url, args.out, is_search=args.query is not None)
    except (ValueError, OSError, urllib.error.URLError) as exc:
        parser.exit(1, f"metadata intake stopped ({type(exc).__name__}); no automatic retry or qualification\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
