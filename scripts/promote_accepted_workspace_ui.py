"""Promote the accepted whole-site preview, without copying any datasets.

Use --preview-root for the small retained UI-source directory. The resulting
assets are committed in ui/accepted-workspace and run without the preview server.
Existing edits are preserved; all three source transformations assert their
expected inputs before any file is changed. Repeating promotion verifies assets.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

VERSION = "2026-10-08-accepted-workspace-v1"
MARKER = "<!-- accepted-workspace-ui:v1 -->"
STYLES = ("polish.css", "laptop.css", "workspace-preview.css", "analysis-preview.css",
          "site-workflow-preview.css", "chronology-preview.css", "analysis-navigation.css")
SCRIPTS = ("workspace-preview.js", "analysis-preview.js", "site-workflow-preview.js",
           "chronology-preview.js", "analysis-view-groups.js", "analysis-navigation.js", "polish.js")


def encode_like(raw: bytes, text: str) -> bytes:
    crlf = raw.count(b"\r\n")
    newline = "\r\n" if crlf > (raw.count(b"\n") - crlf) else "\n"
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    return bom + text.replace("\r\n", "\n").replace("\n", newline).encode("utf-8")


def promote(product: Path, preview: Path, check: bool = False) -> dict:
    product = product.resolve()
    preview = preview.resolve()
    transform_source = preview / "preview_transforms.py"
    spec = importlib.util.spec_from_file_location("accepted_workspace_source", transform_source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    asset_root = product / "ui" / "accepted-workspace"
    index_raw = (product / "index.html").read_bytes()
    index = index_raw.decode("utf-8-sig").replace("\r\n", "\n")
    already_promoted = MARKER in index
    writes: dict[Path, bytes] = {}
    if already_promoted:
        for asset in STYLES + SCRIPTS:
            if index.count("./ui/accepted-workspace/" + asset + "?v=" + VERSION) != 1:
                raise ValueError("Accepted asset is missing or duplicated in index: " + asset)
        app = (product / "app.js").read_text(encoding="utf-8-sig")
        analysis = (product / "analysis_view.js").read_text(encoding="utf-8-sig")
        if "if (!els.timelineCanvasWrap || els.timelineCanvasWrap.clientWidth < 1) return;" not in app:
            raise ValueError("Accepted hidden timeline geometry guard is absent")
        if analysis.count("    _openSupportingChart(chartId) {") != 1:
            raise ValueError("Accepted supporting-chart navigation is absent or duplicated")
        if "buildEvidencePackage(this.latestResult, this.latestMeta)" not in analysis:
            raise ValueError("Accepted result-snapshot export scope is absent")
    if not already_promoted:
        if check:
            raise ValueError("Accepted whole-site UI has not been promoted")
        for name in ("index.html", "app.js", "analysis_view.js"):
            raw = (product / name).read_bytes()
            source = raw.decode("utf-8-sig").replace("\r\n", "\n")
            output = module.transform_preview_asset(name, source)
            if name == "index.html":
                styles = "\n".join('  <link rel="stylesheet" href="./ui/accepted-workspace/' + asset + '?v=' + VERSION + '">' for asset in STYLES)
                initialization = '''  <script>
    document.documentElement.classList.add("faithful-polish-preview");
    if (!sessionStorage.getItem("ufoTimeline.acceptedWorkspaceSizing.v1")) {
      localStorage.removeItem("ufoTimeline.mapSurfaceHeight.v1");
      sessionStorage.setItem("ufoTimeline.acceptedWorkspaceSizing.v1", "1");
    }
  </script>'''
                output = output.replace("</head>", MARKER + "\n" + styles + "\n" + initialization + "\n</head>", 1)
                scripts = "\n".join('  <script defer src="./ui/accepted-workspace/' + asset + '?v=' + VERSION + '"></script>' for asset in SCRIPTS)
                output = output.replace("</body>", scripts + "\n</body>", 1)
            writes[product / name] = encode_like(raw, output)
    asset_pins = []
    for name in STYLES + SCRIPTS:
        raw = (preview / name).read_bytes()
        target = asset_root / name
        if already_promoted and (not target.is_file() or target.read_bytes() != raw):
            raise ValueError("Promoted UI source differs from accepted preview: " + name)
        if not already_promoted:
            writes[target] = raw
        asset_pins.append({"path": target.relative_to(product).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    if not check:
        for target, raw in writes.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    return {"schema": "accepted-workspace-ui-promotion-v1", "version": VERSION,
            "promoted": True, "alreadyPromoted": already_promoted, "checkOnly": check,
            "assets": asset_pins, "assetBytes": sum(row["bytes"] for row in asset_pins),
            "transformSourceSha256": hashlib.sha256(transform_source.read_bytes()).hexdigest(),
            "transformedSourceFiles": ["index.html", "app.js", "analysis_view.js"],
            "excludedWithdrawnAsset": "laptop.js", "datasetCopies": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--preview-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(promote(args.product_root, args.preview_root, args.check), indent=2))
