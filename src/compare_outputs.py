"""Compare rebuilt CSVs to a pipeline snapshot, allowing numeric rounding noise."""

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="A pipeline run's previous_outputs directory")
    args = parser.parse_args()
    files = list(args.baseline.glob("*.csv"))
    if not files:
        parser.error("No baseline CSVs found.")
    checks = {}
    for path in sorted(files):
        try:
            before = pd.read_csv(path)
            after = pd.read_csv(ROOT / "outputs" / path.name)
            columns = list(before.columns)
            if list(after.columns) != columns:
                raise AssertionError("Column names or order changed.")
            before = before.sort_values(columns).reset_index(drop=True)
            after = after.sort_values(columns).reset_index(drop=True)
            pd.testing.assert_frame_equal(before, after, check_exact=False, rtol=1e-9, atol=1e-9)
            checks[path.name] = {"passed": True, "rows": len(after)}
        except (AssertionError, FileNotFoundError) as exc:
            checks[path.name] = {"passed": False, "detail": str(exc)}
    passed = all(check["passed"] for check in checks.values())
    report = {"passed": passed, "comparison": "Row-order independent; numeric rtol=atol=1e-9", "files": checks}
    (ROOT / "outputs/rebuild_comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Passed {sum(c['passed'] for c in checks.values())}/{len(checks)} CSV comparisons.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
