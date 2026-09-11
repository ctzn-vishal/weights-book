"""Appendix A build: notation and crosswalk.

This page holds no data-derived numbers of its own (it cites a few Chapter 7
design facts by id), so the build only writes the minimal manifest the checker
and exporter need.

    python build.py   -> artifacts/manifest.json
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"

manifest = {
    "key": "appA",
    "slug": "appendix-a-notation",
    "status": "draft",
    "inputs": [
        {"path": "book/docs/PROPOSAL_weighting_booklet_v3_FINAL.md",
         "note": "section 2.2 notation contract; section 7 binding corrections"},
        {"path": "NHANES/reports/cluster_std_error/survey_weights_vs_design_intuition.md",
         "note": "seed article; its section 5 survey-econometrics table is corrected here"},
    ],
    "code": "build.py",
    "validation": [],
    "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
ART.mkdir(parents=True, exist_ok=True)
with open(ART / "manifest.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(manifest, f, sort_keys=True, indent=2, ensure_ascii=False)
    f.write("\n")
print("appA: manifest written")
