"""
Phase 10 — Gatling trial driver.

IMPORTANT / KNOWN LIMITATION (read before trusting this module blindly):

OrderSimulation.java's own docstring (Phase 8) claims `simulation.log` is
"tab-separated" and that Phase 10/11 should parse it directly. That's wrong
for the Gatling version actually pinned in gatling/pom.xml (3.15.1) — I
opened a real simulation.log from one of the dated run directories in this
repo (gatling/target/gatling/ordersimulation-2026...) and it's a
length-prefixed BINARY format, not tab-separated text. Reverse-engineering
that binary format from one sample file, with no access to Gatling's source
or a way to run it myself in this environment, is not something I'm willing
to do for data that feeds a dissertation's statistics — a silently-wrong
byte-offset assumption would produce confident-looking garbage percentiles.

Instead, this module parses the plain-text "Global Information" summary
block Gatling prints to stdout at the end of every `mvn gatling:test` run.
That console format has been stable and documented across Gatling 2.x-3.x
and is what most third-party CI integrations parse — but I have NOT been
able to run Gatling in this sandbox (no Docker/JDK21/Maven available) to
capture a real sample of it for THIS version and confirm the regexes below
match exactly. `run_experiment.py --smoke` is designed to surface a parse
failure immediately and loudly (raising with the raw captured stdout
attached) rather than silently recording zeros, specifically so this gets
caught on the first real trial instead of trial #200.

Net effect: total request count, OK/KO count, and p50/p95/p99 response time
come from Gatling's own console summary (this module). Error-rate-over-time
and recovery time come from Prometheus instead (metrics_collector.py),
which was verified working end-to-end in Phase 9 — so the runner doesn't
depend on the binary log for any of the five planned metrics.
"""

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import config


class GatlingRunError(RuntimeError):
    pass


@dataclass
class GatlingResult:
    request_count: int
    ok_count: int
    ko_count: int
    p50_ms: Optional[float]
    p95_ms: Optional[float]
    p99_ms: Optional[float]
    mean_response_ms: Optional[float]
    mean_requests_per_sec: Optional[float]
    started_at: float  # unix epoch, set by caller before subprocess launch
    ended_at: float  # unix epoch, set by caller after subprocess returns
    report_dir: Optional[Path]
    raw_stdout_tail: str = field(repr=False, default="")

    @property
    def error_rate(self) -> Optional[float]:
        if self.request_count == 0:
            return None
        return self.ko_count / self.request_count


# Anchors into Gatling's "Global Information" console summary block.
# Tolerant of arbitrary whitespace; each captures the *first* numeric value
# on the line (Gatling's overall figure, before the "(OK=... KO=...)" split).
_PATTERNS = {
    "request_count": re.compile(r">\s*request count\s+(\d+)"),
    "p50_ms": re.compile(r">\s*response time 50th percentile\s+(-?\d+(?:\.\d+)?)"),
    "p95_ms": re.compile(r">\s*response time 95th percentile\s+(-?\d+(?:\.\d+)?)"),
    "p99_ms": re.compile(r">\s*response time 99th percentile\s+(-?\d+(?:\.\d+)?)"),
    "mean_response_ms": re.compile(r">\s*mean response time\s+(-?\d+(?:\.\d+)?)"),
    "mean_requests_per_sec": re.compile(r">\s*mean requests/sec\s+(-?\d+(?:\.\d+)?)"),
}
_OK_KO_PATTERN = re.compile(r"request count\s+\d+\s+\(OK=(\d+)\s+KO=(\d+)\s*\)")


def _parse_console_summary(stdout: str) -> dict:
    missing = []
    values = {}
    for key, pattern in _PATTERNS.items():
        m = pattern.search(stdout)
        if not m:
            missing.append(key)
            continue
        values[key] = float(m.group(1))

    ok_ko = _OK_KO_PATTERN.search(stdout)
    if not ok_ko:
        missing.append("ok_ko_split")
    else:
        values["ok_count"] = int(ok_ko.group(1))
        values["ko_count"] = int(ok_ko.group(2))

    if missing:
        tail = stdout[-4000:]
        raise GatlingRunError(
            "Could not find expected fields in Gatling console summary: "
            f"{missing}. This almost certainly means the console output "
            "format differs from what this parser was written against "
            "(see module docstring — never verified against a real run). "
            f"Last 4000 chars of captured stdout for debugging:\n{tail}"
        )
    return values


def _find_new_report_dir(before: set, after: set) -> Optional[Path]:
    new_dirs = after - before
    if not new_dirs:
        return None
    # if more than one appeared (shouldn't happen for a single sequential
    # run), take the most recently modified
    return max((Path(d) for d in new_dirs), key=lambda p: p.stat().st_mtime)


def run_trial(
    base_url: str,
    target_users: int,
    ramp_seconds: int,
    sustain_minutes: int,
    timeout_seconds: int = 1800,
) -> GatlingResult:
    """Runs one Gatling trial via `mvn gatling:test` against a live stack.
    Blocks until completion. Raises GatlingRunError on non-zero exit or on
    a console summary that doesn't match the expected shape."""

    gatling_results_dir = config.GATLING_DIR / "target" / "gatling"
    before = set(str(p) for p in gatling_results_dir.glob("*")) if gatling_results_dir.exists() else set()

    cmd = [
        "./mvnw" if (config.GATLING_DIR / "mvnw").exists() else "mvn",
        "gatling:test",
        f"-DbaseUrl={base_url}",
        f"-DtargetUsers={target_users}",
        f"-DrampSeconds={ramp_seconds}",
        f"-DsustainMinutes={sustain_minutes}",
    ]

    started_at = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=config.GATLING_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise GatlingRunError(
            f"Gatling trial exceeded {timeout_seconds}s timeout (target_users={target_users}, "
            f"sustain_minutes={sustain_minutes}) and was killed."
        ) from exc
    ended_at = time.time()

    after = set(str(p) for p in gatling_results_dir.glob("*")) if gatling_results_dir.exists() else set()
    report_dir = _find_new_report_dir(before, after)

    if result.returncode != 0:
        raise GatlingRunError(
            f"`mvn gatling:test` exited {result.returncode}.\n"
            f"--- stdout tail ---\n{result.stdout[-4000:]}\n"
            f"--- stderr tail ---\n{result.stderr[-2000:]}"
        )

    values = _parse_console_summary(result.stdout)

    return GatlingResult(
        request_count=int(values["request_count"]),
        ok_count=values["ok_count"],
        ko_count=values["ko_count"],
        p50_ms=values.get("p50_ms"),
        p95_ms=values.get("p95_ms"),
        p99_ms=values.get("p99_ms"),
        mean_response_ms=values.get("mean_response_ms"),
        mean_requests_per_sec=values.get("mean_requests_per_sec"),
        started_at=started_at,
        ended_at=ended_at,
        report_dir=report_dir,
        raw_stdout_tail=result.stdout[-2000:],
    )
