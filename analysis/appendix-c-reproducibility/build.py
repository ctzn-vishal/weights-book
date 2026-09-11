"""Appendix C build: tool versions and the published benchmarks the pipeline reproduces.

    python build.py   -> artifacts/manifest.json
                         artifacts/figures/tool_versions.json
                         artifacts/figures/benchmarks.json

The tool table records the versions installed on the build machine when this
script runs; the benchmark table is parsed from logs/validation_benchmarks_clean.md.
"""
from __future__ import annotations

import datetime as dt
import importlib.metadata as md
import json
import platform
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
KEY, SLUG = "appC", "appendix-c-reproducibility"
BENCH = Path(r"C:\Users\Vishal Singh\Box\ipums\logs\validation_benchmarks_clean.md")
REPO = Path(r"C:\github\weights-book")
RSCRIPT = Path(r"C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def pyver(dist: str) -> str:
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return "not installed"


def run(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return (out.stdout or out.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable ({type(exc).__name__})"


def npm(pkg: str) -> str:
    p = REPO / "node_modules" / Path(*pkg.split("/")) / "package.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))["version"]
    except Exception:  # noqa: BLE001
        return "not found"


# ------------------------------------------------------------------ tools
r_out = run([str(RSCRIPT), "-e",
             "cat(paste(R.version$major, R.version$minor, sep='.'), "
             "as.character(packageVersion('survey')), as.character(packageVersion('arrow')), sep='|')"])
r_parts = r_out.split("|") if r_out.count("|") == 2 else ["unavailable"] * 3
tools = [
    ("Python", platform.python_version(), "analysis language for every build.py"),
    ("svy", pyver("svy"), "design-based estimation (Taylor and replication); the book's computational spine"),
    ("svy-rs", pyver("svy-rs"), "compiled engine behind svy"),
    ("duckdb", pyver("duckdb"), "scans and pre-aggregation over the parquet store"),
    ("polars", pyver("polars"), "data frames; the independent second path for point estimates"),
    ("pandas", pyver("pandas"), "interchange with pyfixest"),
    ("numpy", pyver("numpy"), "simulation and hand-coded formulas"),
    ("scipy", pyver("scipy"), "t quantiles"),
    ("pyarrow", pyver("pyarrow"), "parquet I/O"),
    ("pyfixest", pyver("pyfixest"), "regressions with fixed effects and cluster-robust variance"),
    ("R", r_parts[0], "independent oracle for design-based results"),
    ("R survey", r_parts[1], "sentinel checks (svydesign, svrepdesign)"),
    ("R arrow", r_parts[2], "reads the parquet store directly from R"),
    ("Node.js", run(["node", "--version"]).lstrip("v"), "site build and scripts/check-mdx.mjs"),
    ("Next.js", npm("next"), "static site framework"),
    ("@mdx-js/mdx", npm("@mdx-js/mdx"), "MDX 3 compiler"),
    ("KaTeX", npm("katex"), "math rendering"),
    ("React", npm("react"), "components and widgets"),
]
tool_fig = {
    "type": "table",
    "title": "Tool versions on the build machine",
    "subtitle": "Captured by appendix-c-reproducibility/build.py when the artifacts were last built",
    "alt": "Table of the software used to build the book, with the version installed on the build machine "
           "and each tool's role.",
    "columns": [
        {"key": "tool", "label": "Tool", "align": "left"},
        {"key": "version", "label": "Version", "align": "left"},
        {"key": "role", "label": "Role in the book", "align": "left"},
    ],
    "rows": [{"tool": t, "version": v, "role": r} for t, v, r in tools],
    "source": "importlib.metadata (Python), packageVersion() via Rscript (R), node --version, "
              "node_modules/*/package.json (site)",
    "note": "Versions differ across machines; the manifests record which chapter was built when.",
}

# ------------------------------------------------------------------ benchmarks
text = BENCH.read_text(encoding="utf-8")
sections = re.split(r"^## ", text, flags=re.M)[1:]
bench_rows, acceptance = [], ""
for sec in sections:
    lines = [ln.rstrip() for ln in sec.splitlines()]
    title = lines[0].strip()
    if title.lower().startswith("acceptance"):
        acceptance = " ".join(ln.lstrip("- ").strip() for ln in lines[1:] if ln.strip())
        continue
    published = next((ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("Published:")), "")
    table = [ln for ln in lines if ln.startswith("|")]
    body = [[c.strip() for c in ln.strip("|").split("|")] for ln in table[2:]]
    years = [b[0] for b in body]
    raw = [b[1] for b in body]
    clean = [b[2] for b in body]
    same = all(a == b for a, b in zip(raw, clean))
    diffs = [f"{y}: {a} vs {b}" for y, a, b in zip(years, raw, clean) if a != b]
    bench_rows.append({
        "series": title,
        "published": published,
        "years": f"{years[0]}\u2013{years[-1]} ({len(years)} years)" if years else "",
        "clean": " / ".join(f"{y}: {c}" for y, c in zip(years, clean)),
        "raw_vs_clean": "identical" if same else "differs where the clean store uses a derived variable ("
                                                    + "; ".join(diffs) + ")",
    })
bench_fig = {
    "type": "table",
    "title": "Published benchmarks the data pipeline reproduces",
    "subtitle": "Re-run on the cleaned analysis store; each value compared with the producer's published figure",
    "alt": "Table of external benchmarks: for each series, the published figure recorded in the validation log, "
           "the years re-computed, the clean-store values, and whether raw and clean stores agree.",
    "columns": [
        {"key": "series", "label": "Series", "align": "left"},
        {"key": "published", "label": "Published benchmark (as recorded)", "align": "left"},
        {"key": "years", "label": "Years", "align": "left"},
        {"key": "clean", "label": "Clean-store values", "align": "left"},
        {"key": "raw_vs_clean", "label": "Raw vs clean store", "align": "left"},
    ],
    "rows": bench_rows,
    "source": "logs/validation_benchmarks_clean.md (generated 2026-07-11)",
    "note": f"Log's acceptance line: {acceptance}. External benchmarks, not truth: "
            "published figures carry their own sampling and processing error.",
}

write_json(ART / "figures" / "tool_versions.json", tool_fig)
write_json(ART / "figures" / "benchmarks.json", bench_fig)
write_json(ART / "manifest.json", {
    "key": KEY, "slug": SLUG, "status": "draft",
    "inputs": [{"path": "ipums/logs/validation_benchmarks_clean.md", "rows": len(bench_rows),
                "note": "benchmark re-run on the analysis (clean) store"}],
    "code": "build.py",
    "validation": [{"check": "benchmark log parsed", "series": len(bench_rows), "acceptance": acceptance,
                    "pass": bool(bench_rows) and "ALL MATCH" in acceptance}],
    "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
})
print("appC: tools", [(t, v) for t, v, _ in tools])
print("appC: benchmarks", [r["series"] for r in bench_rows], "| acceptance:", acceptance)
