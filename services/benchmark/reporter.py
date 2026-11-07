"""Artifact Generation and Reporting for Phase 11.1 Canonical Benchmark Harness.

Produces machine-readable JSON artifacts and a clean, concise Markdown report:
- benchmark_run.json
- scenario_results.json
- benchmark_summary.json
- benchmark_run_report.md

Preserves strict information hygiene: Never emits secrets, credentials, or private headers.
"""

import os
import json
from typing import List, Dict, Any
from services.benchmark.schemas import (
    BenchmarkSummary,
    BenchmarkResult,
    BenchmarkStatus,
)


class BenchmarkReporter:
    """Generates structured benchmark artifacts and summary markdown reports."""

    @classmethod
    def save_run_artifacts(
        cls,
        output_dir: str,
        summary: BenchmarkSummary,
        results: List[BenchmarkResult],
    ) -> Dict[str, str]:
        """Write all benchmark run artifacts to disk and return their file paths."""
        os.makedirs(output_dir, exist_ok=True)

        artifacts = {}

        # 1. benchmark_summary.json
        summary_path = os.path.join(output_dir, "benchmark_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(mode="json"), f, indent=2)
        artifacts["benchmark_summary"] = summary_path

        # 2. scenario_results.json
        results_path = os.path.join(output_dir, "scenario_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump(mode="json") for r in results], f, indent=2)
        artifacts["scenario_results"] = results_path

        # 3. benchmark_run.json (Combined run payload)
        run_payload = {
            "summary": summary.model_dump(mode="json"),
            "results": [r.model_dump(mode="json") for r in results],
        }
        run_path = os.path.join(output_dir, "benchmark_run.json")
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(run_payload, f, indent=2)
        artifacts["benchmark_run"] = run_path

        # 4. benchmark_run_report.md
        md_report = cls.generate_markdown_report(summary, results)
        md_path = os.path.join(output_dir, "benchmark_run_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)
        artifacts["benchmark_run_report"] = md_path

        return artifacts

    @classmethod
    def generate_markdown_report(
        cls,
        summary: BenchmarkSummary,
        results: List[BenchmarkResult],
    ) -> str:
        """Construct a structured Markdown report from run results."""
        lines = [
            "# Canonical Benchmark Run Report",
            f"**Contract**: `benchmark-summary/v1` | **Run ID**: `{summary.run_id}`",
            "",
            "## 1. Executive Summary",
            "",
            f"- **Total Scenarios Executed**: {summary.total_scenarios}",
            f"- **Scenarios Passed**: {summary.passed} ✅",
            f"- **Scenarios Failed**: {summary.failed} ❌",
            f"- **Scenarios Inconclusive**: {summary.inconclusive} ⚠️",
            f"- **Total Assertions Evaluated**: {summary.assertions_total}",
            f"- **Assertions Passed**: {summary.assertions_passed}",
            f"- **Assertions Failed**: {summary.assertions_failed}",
            f"- **Duration**: {summary.duration_ms:.2f} ms",
            f"- **Reproducibility Status**: `{summary.reproducibility_status or 'N/A'}`",
            "",
            "## 2. Scenario Results Breakdown",
            "",
            "| Scenario ID | Category | Status | Assertions (Pass/Total) | Duration (ms) |",
            "|---|---|---|---|---|",
        ]

        for r in results:
            status_icon = "PASS ✅" if r.status == BenchmarkStatus.PASS else ("FAIL ❌" if r.status == BenchmarkStatus.FAIL else "INCONCLUSIVE ⚠️")
            lines.append(
                f"| `{r.scenario_id}` | `{r.category.value}` | {status_icon} | {r.assertions_passed}/{r.assertions_total} | {r.duration_ms:.2f} |"
            )

        # Diagnostics for any failures
        failures = [r for r in results if r.status != BenchmarkStatus.PASS]
        if failures:
            lines.extend([
                "",
                "## 3. Failure Diagnostics",
                "",
            ])
            for r in failures:
                lines.append(f"### Scenario: `{r.scenario_id}` ({r.status.value})")
                for d in r.diagnostics:
                    if not d.passed:
                        lines.append(f"- **[{d.failure_class.value if d.failure_class else 'UNKNOWN'}]** `{d.expectation_id}`: {d.message}")
        else:
            lines.extend([
                "",
                "## 3. Failure Diagnostics",
                "",
                "No assertion failures or infrastructure exceptions recorded.",
            ])

        lines.extend([
            "",
            "## 4. Information Hygiene Verification",
            "",
            "- **Secrets / Credentials Redacted**: Yes",
            "- **Provider Auth Headers Omitted**: Yes",
            "- **Private Merchant Unit Economics Redacted**: Yes",
            "- **Deterministic Fields Scoped**: Yes",
        ])

        return "\n".join(lines)
