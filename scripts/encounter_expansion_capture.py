"""Capture an explicit, small research allowlist; never deploy third-party narratives.

Pinned UFOlio is a discovery transcription, not Rosales' original or HERA's export.
No crawler, authentication, access-control workaround, or source replacement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

COMMIT = "de7df473ddbd7849f7905522158dd3b43e65ab75"
BASE = f"https://raw.githubusercontent.com/ebrinz/ufolio/{COMMIT}/"
MIB = 1024 * 1024
SOURCES = [
    ("ufolio_rosales", BASE + "rosales/data/rosales_parsed.csv", "ufolio_rosales.csv", 10 * MIB, "third_party_transcription"),
    ("ufolio_readme", BASE + "README.md", "ufolio_readme.md", MIB, "third_party_documentation"),
    ("ufolio_parser", BASE + "rosales/scrape_rosales.py", "ufolio_parser.py.txt", MIB, "third_party_parser_not_executed"),
    ("ufolio_scrape_log", BASE + "rosales/scrape.log", "ufolio_scrape.log.txt", MIB, "third_party_capture_log"),
    ("urecat_index", "https://ufologie.patrickgross.org/ce3/_full.htm", "urecat_index.html", MIB, "compiler_index"),
    ("nicap_directory", "https://www.nicap.org/cat7.htm", "nicap_directory.html", MIB, "custodian_directory"),
    ("nicap_occupants", "https://www.nicap.org/Occupant.htm", "nicap_occupants.html", MIB, "custodian_hosted_compilation"),
    ("nicap_regional", "https://www.nicap.org/rsid3.htm", "nicap_regional.html", MIB, "custodian_hosted_compilation"),
    ("nicap_cat7", "https://www.nicap.org/NSID_DBListingbyCat7.pdf", "nicap_cat7.pdf", MIB, "custodian_hosted_compilation"),
]
TOTAL_CAP = 15 * MIB
PDF_YEARS = {
    "1909": "20140426112349",
    "1940": "20140426111749", "1942": "20140426112801", "1943": "20140426112144",
    "1944": "20140426112404", "1945": "20140426113131", "1946": "20140426110316",
    "1949": "20140426110643", "1957": "20140426112921", "1958": "20140426113046",
    "1960": "20140426112950", "1961": "20140426112617", "1962": "20140426111530",
    "1963": "20140426105649", "1964": "20140426110742", "1983": "20140426112347",
    "1984": "20140426112132", "1985": "20140426112814",
    "1994": "20140426110052", "1995": "20140426111350",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--sample-archives", action="store_true", help="Only three exact public archive URLs identified by the pinned third-party log")
    ap.add_argument("--logged-archives", type=Path, help="Explicit archived year URLs with positive parse counts in the pinned transcription log")
    ap.add_argument("--reuse-manifest", type=Path, help="Reuse identical protected sample captures instead of copying them")
    ap.add_argument("--retry-connection-manifest", type=Path, help="One delayed retry of connection-refused failures; never retries denied access")
    ap.add_argument("--missing-pdf-archives", action="store_true", help="20 exact public CDX-discovered PDF URLs: 18 HTML-only gaps plus two failed HTML replays")
    ap.add_argument("--pdf-raw-replay", action="store_true", help="Use the public archive's raw PDF representation instead of its HTML viewer")
    args = ap.parse_args()
    dest = args.output.resolve()
    if dest.exists():
        raise SystemExit("Protected capture directory exists; use its manifest. No recapture or overwrite.")
    dest.mkdir(parents=True)
    lifecycle = {
        "purpose": "Bounded encounter source discovery and provenance/overlap audit; not a runtime dataset.",
        "rebuild": "Replay normalization and overlap scripts from pinned captures. Capture script refuses replacement.",
        "retention": "Retain unique source inputs and derived audit; no complete corpus or deployment copy.",
        "totalResearchBudgetBytes": 64 * MIB,
        "captureBudgetBytes": TOTAL_CAP,
        "publicRedistribution": "Not authorized by acquisition; narratives remain private and excluded from Git/runtime.",
        "canonicalRuntime": "Unchanged existing encounter evidence and canonical UFO corpus.",
        "rollback": "Existing validated production and known-good rollback retained unchanged.",
    }
    (dest / "lifecycle.json").write_text(json.dumps(lifecycle, indent=2) + "\n", encoding="utf-8")
    captures = dest / "captures"
    captures.mkdir()
    manifest = {
        "schemaId": "ufo-encounter-expansion-captures-v1",
        "ufolioCommit": COMMIT,
        "sources": [],
        "captureCapBytes": TOTAL_CAP,
        "policy": lifecycle["publicRedistribution"],
        "accessObservations": [
            {"url": "https://www.iraap.org/rosales/", "status": 403},
            {"url": "https://www.iraap.org/rosales/1993.htm", "status": 403},
            {"url": "https://www.ufoinfo.com/humanoid/index.shtml", "status": 403},
            {"url": "https://ufocasebook.com/contactindex.html", "status": 404},
            {"url": "https://www.thelosthaven.co.uk/conthumanoid.html", "status": "TLS_certificate_validation_failed"},
        ],
    }
    total = 0
    sources = SOURCES
    if args.missing_pdf_archives:
        modifier = "id_" if args.pdf_raw_replay else ""
        sources = [("rosales_pdf_" + year, f"https://web.archive.org/web/{stamp}{modifier}/http://www.ufoinfo.com/humanoid/humanoid-{year}.pdf", "rosales" + year + ".pdf", 4 * MIB, "original_host_public_pdf_archive") for year, stamp in PDF_YEARS.items()]
        manifest["discovery"] = "Ordinary public CDX prefix inventory identified PDF names, rather than constructed humanoidYEAR.shtml paths. Replay signature and hashes independently checked."
    reused = {}
    if args.reuse_manifest:
        for row in json.loads(args.reuse_manifest.read_text(encoding="utf-8"))["sources"]:
            if row.get("status") in {"captured", "reused"}:
                path = Path(row["path"])
                if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                    raise ValueError("Protected reused capture changed")
                reused[row["url"]] = row
    if args.sample_archives:
        sources = [
            ("rosales_1954_archive", "https://web.archive.org/web/20080217002358/http://www.ufoinfo.com/humanoid/humanoid1954.shtml", "rosales1954.html", MIB, "original_host_public_archive_sample"),
            ("rosales_1993_archive", "https://web.archive.org/web/20080101172539/http://www.ufoinfo.com/humanoid/humanoid1993.shtml", "rosales1993.html", MIB, "original_host_public_archive_sample"),
            ("rosales_2000_archive", "https://web.archive.org/web/20080101172544/http://www.ufoinfo.com/humanoid/humanoid2000.shtml", "rosales2000.html", MIB, "original_host_public_archive_sample"),
        ]
    if args.logged_archives:
        urls, parsed = {}, {}
        for line in args.logged_archives.read_text(encoding="utf-8").splitlines():
            m = re.search(r"Fetching (ancient|\d{4}) from (https://web\.archive\.org/web/\d{14}/http://www\.ufoinfo\.com/humanoid/humanoid(?:ancient|\d{4})\.shtml)", line)
            if m:
                urls[m[1]] = m[2]
            m = re.search(r"Parsed (\d+) entries from page (ancient|\d{4})", line)
            if m and int(m[1]) > 0 and m[2] in urls:
                parsed[m[2]] = urls[m[2]]
        if len(parsed) != 55:
            raise ValueError("Pinned discovery log should identify exactly 55 positive year pages")
        sources = [("rosales_" + year, url, "rosales" + year + ".html", MIB, "original_host_public_archive") for year, url in parsed.items()]
        manifest["discoveryLog"] = {"path": str(args.logged_archives.resolve()), "sha256": hashlib.sha256(args.logged_archives.read_bytes()).hexdigest()}
    if args.retry_connection_manifest:
        prior = json.loads(args.retry_connection_manifest.read_text(encoding="utf-8"))
        sources = []
        for row in prior["sources"]:
            if row.get("status") != "unavailable" or "10061" not in row.get("error", ""):
                continue
            if not re.fullmatch(r"https://web\.archive\.org/web/\d{14}/http://www\.ufoinfo\.com/humanoid/humanoid(?:ancient|\d{4})\.shtml", row["url"]):
                raise ValueError("Retry URL outside explicit archive scope")
            sources.append((row["sourceId"], row["url"], row["sourceId"].replace("_", "") + ".html", MIB, "original_host_public_archive_connection_retry"))
        manifest["retryOf"] = {"path": str(args.retry_connection_manifest.resolve()), "sha256": hashlib.sha256(args.retry_connection_manifest.read_bytes()).hexdigest()}
    for source_id, url, name, cap, role in sources:
        if args.retry_connection_manifest or args.missing_pdf_archives:
            time.sleep(1)
        row = {"sourceId": source_id, "url": url, "role": role, "captureUtc": datetime.now(timezone.utc).isoformat()}
        try:
            if url in reused:
                old = reused[url]
                row.update(status="reused", path=old["path"], bytes=old["bytes"], sha256=old["sha256"], reusedFrom=str(args.reuse_manifest.resolve()))
                row["publicRedistribution"] = "not_authorized_by_this_capture"
                manifest["sources"].append(row)
                manifest["totalBytes"] = total
                (dest / "capture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({"sourceId": source_id, "status": "reused", "bytes": old["bytes"]}), flush=True)
                continue
            # Honest default Python client. No credential/header impersonation or TLS downgrade.
            with urllib.request.urlopen(url, timeout=30) as response:
                advertised = int(response.headers.get("Content-Length") or 0)
                if advertised > cap or (advertised and total + advertised > TOTAL_CAP):
                    raise ValueError("Source would exceed explicit capture budget")
                raw = response.read(min(cap, TOTAL_CAP - total) + 1)
                if len(raw) > cap or total + len(raw) > TOTAL_CAP:
                    raise ValueError("Source exceeded explicit capture budget")
                if name.endswith(".pdf") and not raw.startswith(b"%PDF"):
                    raise ValueError("Expected PDF signature missing")
                path = captures / name
                with path.open("xb") as f:
                    f.write(raw)
                total += len(raw)
                row.update(status="captured", path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                           httpStatus=response.status, finalUrl=response.url, contentType=response.headers.get("Content-Type"),
                           advertisedBytes=advertised, etag=response.headers.get("ETag"), lastModified=response.headers.get("Last-Modified"))
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            row.update(status="unavailable", error=str(exc), bytes=0, sha256=None)
        row["publicRedistribution"] = "not_authorized_by_this_capture"
        manifest["sources"].append(row)
        manifest["totalBytes"] = total
        (dest / "capture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: row.get(k) for k in ("sourceId", "status", "bytes", "error")}), flush=True)
    print(json.dumps({"manifest": str(dest / "capture_manifest.json"), "totalBytes": total}))


if __name__ == "__main__":
    main()
