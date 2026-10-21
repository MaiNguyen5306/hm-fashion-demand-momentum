"""Run the H&M pipeline sequentially with logs and a pre-run output snapshot."""

import argparse
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    "validate_raw_data.py", "build_daily_panel.py", "validate_processed_data.py",
    "create_eda_summary.py", "create_lifecycle_summary.py",
    "profile_momentum_eligibility.py", "build_momentum_panel.py",
    "create_momentum_metrics.py", "contextualize_momentum.py",
    "analyze_catalog_surges.py", "create_cumulative_lifecycle_metrics.py",
    "create_product_profiles.py", "create_category_insights.py",
    "validate_analysis_data.py", "export_dashboard_data.py",
    "validate_product_access.py",
    "export_web_data.py", "validate_web_export.py",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-at", choices=STEPS, default=STEPS[0],
                        help="Resume at a step; its prerequisite files must already exist.")
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = ROOT / "data/interim/pipeline_runs" / run_id
    baseline = run_dir / "previous_outputs"
    baseline.mkdir(parents=True)
    for path in (ROOT / "outputs").glob("*.csv"):
        shutil.copy2(path, baseline / path.name)
    record = {"run_id": run_id, "python": sys.version, "steps": []}
    print(f"Run logs and previous outputs: {run_dir}", flush=True)
    raw_files = {}
    for name in ["articles.csv", "transactions_train.csv"]:
        path = ROOT / "data/raw" / name
        if not path.is_file():
            raise SystemExit(f"Missing raw input: {path}")
        with path.open("rb") as handle:
            raw_files[name] = {"bytes": path.stat().st_size,
                               "sha256": hashlib.file_digest(handle, "sha256").hexdigest()}
    manifest = {"source": "https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data",
                "files": raw_files}
    (ROOT / "outputs/raw_data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    record["raw_inputs"] = raw_files
    for step in STEPS[STEPS.index(args.start_at):]:
        print(f"Starting {step}", flush=True)
        started = datetime.now(timezone.utc)
        with (run_dir / f"{step}.log").open("w") as log:
            result = subprocess.run([sys.executable, "-u", str(ROOT / "src" / step)],
                                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        record["steps"].append({"script": step, "returncode": result.returncode,
                                "seconds": (datetime.now(timezone.utc) - started).total_seconds()})
        (run_dir / "run.json").write_text(json.dumps(record, indent=2) + "\n")
        if result.returncode:
            print((run_dir / f"{step}.log").read_text(), flush=True)
            raise SystemExit(f"Pipeline stopped at {step}; exit code {result.returncode}.")
        print(f"Passed {step}", flush=True)
    comparison = subprocess.run([sys.executable, str(ROOT / "src/compare_outputs.py"), str(baseline)], cwd=ROOT)
    record["comparison_returncode"] = comparison.returncode
    (run_dir / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    if comparison.returncode:
        raise SystemExit("Rebuilt CSVs differ from the snapshot; inspect outputs/rebuild_comparison.json.")
    print("Pipeline complete, including analytical validation and dashboard export.", flush=True)


if __name__ == "__main__":
    main()
