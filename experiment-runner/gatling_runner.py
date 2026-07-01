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

REGEX HISTORY — this was wrong once already, fixed against real output:
The first version of these patterns was written blind (no way to run
Gatling in the sandbox that built it) against the OLD Gatling 2.x/early
3.x console format: `> request count    45 (OK=42     KO=3     )`. Pavan's
first real --smoke run (2026-06-30) failed all 16 trials against that
version — correctly, loudly, exactly as designed — and the captured stdout
dumps in results/run.log showed Gatling 3.15.1 actually prints a
pipe-delimited table with comma-thousands-separated numbers instead:

    ---- Global Information ----------------|---Total---|-----OK----|----KO----
    > request count                         |       144 |       144 |         -
    > response time 95th percentile (ms)    |     2,531 |     2,531 |         -
    > mean throughput (rps)                 |      2.15 |      2.15 |         -

and, separately, under an earlier "---- Requests ----" section:

    > Global                                |       144 |       144 |         0

The patterns below were rewritten against that real captured text (not
guessed again) — see _to_num() for the comma-stripping this format needs
that the old one didn't. Still worth treating as "confirmed against 0-KO
trials only": every one of Pavan's 16 smoke trials had KO=0, so the KO
column's non-dash, non-zero format has not actually been observed yet.
If a future trial has real KOs and the parser misbehaves on that column,
that's the specific gap to look at first.
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


def _to_num(s: str) -> float:
    """Gatling 3.15.1's table format uses comma thousands separators
    (e.g. "2,531"); strip them before float() or it raises."""
    return float(s.replace(",", "").strip())


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


# Anchors into Gatling 3.15.1's pipe-delimited "Global Information" console
# table (see module docstring for a real captured sample). Each captures the
# first ("Total") column's number, which may contain comma thousands
# separators — always run through _to_num(), never float() directly.
_NUM = r"([\d,]+(?:\.\d+)?)"
_PATTERNS = {
    "request_count": re.compile(r">\s*request count\s*\|\s*" + _NUM),
    "p50_ms": re.compile(r">\s*response time 50th percentile \(ms\)\s*\|\s*" + _NUM),
    "p95_ms": re.compile(r">\s*response time 95th percentile \(ms\)\s*\|\s*" + _NUM),
    "p99_ms": re.compile(r">\s*response time 99th percentile \(ms\)\s*\|\s*" + _NUM),
    "mean_response_ms": re.compile(r">\s*mean response time \(ms\)\s*\|\s*" + _NUM),
    "mean_requests_per_sec": re.compile(r">\s*mean throughput \(rps\)\s*\|\s*" + _NUM),
}

# "> Global | <total> | <ok> | <ko>" under the "---- Requests ----" section.
# This line (unlike "Global Information"'s "request count" row, which prints
# "-" for KO when there are none) prints real 0/N values in all three
# columns, and is Gatling's own aggregate across all request types — so it's
# the more reliable source for the OK/KO split. It also appears once per
# periodic progress snapshot DURING the run, not just at the end, so take
# the LAST match (the final tally), not the first.
_GLOBAL_LINE = re.compile(r">\s*Global\s*\|\s*" + _NUM + r"\s*\|\s*" + _NUM + r"\s*\|\s*" + _NUM)

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _parse_console_summary(stdout: str) -> dict:
    stdout = _ANSI_ESCAPE.sub("", stdout)  # defensive: strip color codes if present
    missing = []
    values = {}
    for key, pattern in _PATTERNS.items():
        m = pattern.search(stdout)
        if not m:
            missing.append(key)
            continue
        values[key] = _to_num(m.group(1))

    global_matches = list(_GLOBAL_LINE.finditer(stdout))
    if not global_matches:
        missing.append("global_ok_ko_line")
    else:
        total, ok, ko = (_to_num(g) for g in global_matches[-1].groups())
        values["request_count"] = total  # overrides the "request count" row above; same value, more trustworthy source
        values["ok_count"] = int(ok)
        values["ko_count"] = int(ko)

    if missing:
        tail = stdout[-4000:]
        raise GatlingRunError(
            "Could not find expected fields in Gatling console summary: "
            f"{missing}. This means the console output format differs from "
            "what this parser expects (see module docstring for the format "
            "this was last confirmed against, and its history of being "
            "wrong once already). "
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
