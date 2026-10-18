"""Prepare bounded private source/native evidence for the 177 priority reviews."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from collections import defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path("C:/Users/jarod/Desktop/UFO Timeline map tool")
RESEARCH = SHARED / "data/research/encounter-expansion-20261017"
DEST = SHARED / "data/research/encounter-reviewed-20261017"
SPEC = importlib.util.spec_from_file_location("originals", ROOT / "scripts/encounter_rosales_originals.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def source_text(payload):
    if payload.startswith(b"%PDF"):
        from pypdf import PdfReader
        parts = []
        for n, page in enumerate(PdfReader(io.BytesIO(payload)).pages, 1):
            text = re.sub(rf"\A\s*{n}\s*\n", "", page.extract_text() or "")
            parts.append(M.normalize_layout(text) + "\n")
        return "".join(parts)
    html, _ = M.decode_html(payload)
    p = M.PlainText()
    p.feed(html)
    return M.normalize_layout("".join(p.parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=DEST, help="New empty private evidence-pack destination; original inputs stay shared")
    args = ap.parse_args()
    dest = args.output.resolve()
    if dest.exists():
        raise ValueError("Protected review directory exists; no replacement")
    native_path = RESEARCH / "rosales-originals/combined-originals.json.gz"
    rows = {r["sourceEntryId"]: r for r in json.loads(gzip.decompress(native_path.read_bytes()))["records"]}
    queued = json.loads(gzip.decompress((RESEARCH / "review_queue.json.gz").read_bytes()))["records"]
    selected = [r for r in queued if r["priority"] == "precise_unambiguous_native_review"]
    assert len(selected) == 177
    by_capture = defaultdict(list)
    for q in selected:
        by_capture[rows[q["sourceEntryId"]]["capture"]["path"]].append(q)
    blocks = {}
    for path, entries in by_capture.items():
        payload = Path(path).read_bytes()
        text = source_text(payload)
        boundaries = list(M.NUMBER.finditer(text))
        for q in entries:
            row = rows[q["sourceEntryId"]]
            assert sha(payload) == row["capture"]["sha256"]
            i = row["sourceEntryOrdinal"] - 1
            block = text[boundaries[i].end():boundaries[i + 1].start() if i + 1 < len(boundaries) else len(text)].strip()
            stop = M.STOP.search(block)
            if stop:
                block = block[:stop.start()].strip()
            assert sha(M.compact(block).encode()) == row["sourceBlockSha256"]
            blocks[q["sourceEntryId"]] = block
    by_chunk = defaultdict(list)
    for q in selected:
        link = q["nativeCitationLinks"][0]
        by_chunk[link["sourceRef"]["chunk"]].append((q, link))
    native = {}
    pins = []
    for chunk, entries in by_chunk.items():
        path = SHARED / "data/canonical_web/event_chunks" / (chunk + ".json")
        raw = path.read_bytes()
        digest = sha(raw)
        events = json.loads(raw)
        pins.append({"path": str(path), "bytes": len(raw), "sha256": digest})
        for q, link in entries:
            assert digest == link["sourceRef"]["chunkSha256"]
            e = events[link["sourceRef"]["detailIndex"]]
            assert str(e["event_id"]) == link["eventId"] and e["source"] == link["source"]
            rf = e.get("raw_fields") or e.get("raw_source_row") or {}
            keep = {"URN", "PRN", "IRN", "NAMES", "NOTES", "SOURCE", "PAGEVOL", "ISOURCE", "IPAGEVOL", "TIME", "TZ", "DATE", "CITY", "LOC", "TYPE", "HYNEK", "VALLEE", "UFONAUT", "HEIGHT", "UNIFORM", "OBJS", "ENTS"}
            native[q["sourceEntryId"]] = {"eventId": str(e["event_id"]), "source": e["source"], "sourceId": e.get("source_id"), "dateRaw": e.get("date_raw"), "dateIso": e.get("date_iso"), "datePrecision": e.get("date_precision"), "timeRaw": e.get("time_raw"), "locationRaw": e.get("location_raw"), "description": e.get("description"), "sourceRef": link["sourceRef"], "rawFields": {k: v for k, v in rf.items() if k.upper() in keep}}
    dest.mkdir(parents=True)
    total = 0
    for cohort in range(3):
        pack = [{"account": rows[q["sourceEntryId"]], "sourceBlockPrivate": blocks[q["sourceEntryId"]], "native": native[q["sourceEntryId"]]} for q in selected[cohort * 59:(cohort + 1) * 59]]
        out = dest / ("review-pack-" + "abc"[cohort] + ".json")
        encoded = (json.dumps({"schemaId": "encounter-manual-review-pack-v1", "records": pack, "policy": "Private bounded review excerpts. Never commit or publish full source blocks. Every acceptance requires manual source/native identity and semantic review."}, ensure_ascii=False, indent=2) + "\n").encode()
        assert len(encoded) < 4 * 1024 * 1024
        out.write_bytes(encoded)
        total += len(encoded)
    lifecycle = {"purpose": "Manual identity and factual annotation review of 177 priority matches; full-text review packs remain private.", "canonicalInputs": str(RESEARCH), "budgetBytes": 20 * 1024 * 1024, "capturePins": pins, "rebuild": "Run encounter_review_prepare.py against immutable original captures, combined metadata and held review queue; choose a new empty review destination.", "retention": "Preserve unique review decisions, source pins and private evidence packs. Prior source intake, runtime, production and rollback remain unchanged.", "totalPackBytes": total}
    (dest / "lifecycle.json").write_text(json.dumps(lifecycle, indent=2) + "\n")
    print(json.dumps({"destination": str(dest), "accounts": len(selected), "packBytes": total, "originalChunksReadInPlace": len(pins)}))


if __name__ == "__main__":
    main()
