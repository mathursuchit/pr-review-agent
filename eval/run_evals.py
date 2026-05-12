"""
Eval runner — called by CI and locally.

Usage:
    python eval/run_evals.py [--fail-below 0.80]

Reads golden cases from eval/cases/*.json.
Each case must have: id, pr_url, expected_findings (list of category strings).
"""
import asyncio
import json
import sys
import argparse
from pathlib import Path

from agent.graph import build_graph
from eval.scorer import score_case, EvalResult


async def run_evals(fail_below: float = 0.80) -> bool:
    graph = build_graph()
    cases_dir = Path(__file__).parent / "cases"
    results: list[EvalResult] = []

    for case_file in sorted(cases_dir.glob("*.json")):
        cases = json.loads(case_file.read_text())
        for case in cases:
            if case.get("skip"):
                print(f"  SKIP  {case['id']}: {case.get('skip_reason', '')}")
                continue

            print(f"  RUN   {case['id']} — {case['pr_url']}")
            try:
                final = await graph.ainvoke({
                    "pr_url": case["pr_url"],
                    "raw_diff": "",
                    "chunks": [],
                    "injection_flagged": False,
                    "secrets_found": [],
                    "security_findings": [],
                    "logic_findings": [],
                    "test_findings": [],
                    "final_report": None,
                    "guardrail_passed": False,
                    "retry_count": 0,
                    "error": None,
                })
                report = final.get("final_report") or {}
                actual = [f["category"] for f in report.get("findings", [])]
            except Exception as e:
                print(f"         ERROR: {e}")
                actual = []

            result = score_case(case["id"], case["expected_findings"], actual, fail_below)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"  {status}  precision={result.precision:.2f}  recall={result.recall:.2f}")

    if not results:
        print("No eval cases found.")
        return True

    avg_p = sum(r.precision for r in results) / len(results)
    avg_r = sum(r.recall for r in results) / len(results)
    overall_pass = avg_p >= fail_below and avg_r >= fail_below

    print(f"\nOverall: precision={avg_p:.2f}  recall={avg_r:.2f}  threshold={fail_below}")
    print("PASS" if overall_pass else "FAIL")
    return overall_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-below", type=float, default=0.80)
    args = parser.parse_args()

    passed = asyncio.run(run_evals(args.fail_below))
    sys.exit(0 if passed else 1)
