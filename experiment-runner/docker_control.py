"""
Phase 10 — Docker Compose control.

Wraps the `docker compose` CLI rather than the Docker SDK, matching how the
rest of this dissertation already operates the stack manually (Phase 5-9
were all verified via `docker compose up -d --build` from the shell) — no
new dependency, same mental model Pavan already has.
"""

import subprocess
import time
import urllib.request
import urllib.error
import json

import config


class DockerControlError(RuntimeError):
    pass


def _run(cmd: list, env: dict | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd,
        cwd=config.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise DockerControlError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def stack_up(build: bool = False) -> None:
    """Bring the whole stack up with the default ('none') resilience
    profile. Used once at the start of a run, not per-trial."""
    cmd = ["docker", "compose", "up", "-d"]
    if build:
        cmd.append("--build")
    _run(cmd, env=config.docker_compose_env("none"), timeout=600)


def stack_down() -> None:
    _run(["docker", "compose", "down"], timeout=120)


def switch_resilience_profile(profile: str) -> None:
    """Recreate order-service with RESILIENCE_PROFILE=<profile> and block
    until it reports UP. This is the operation that runs once per
    (profile) group — 4 times total per full run, not once per trial."""
    if profile not in config.RESILIENCE_PROFILES:
        raise ValueError(f"unknown resilience profile: {profile}")

    env = config.docker_compose_env(profile)
    _run(
        ["docker", "compose", "up", "-d", "--force-recreate", "--no-deps", "order-service"],
        env=env,
        timeout=180,
    )
    wait_for_health(config.ORDER_SERVICE_HEALTH_URL, label="order-service")


def wait_for_health(url: str, label: str, timeout_seconds: int = None) -> None:
    timeout_seconds = timeout_seconds or config.SERVICE_HEALTH_TIMEOUT_SECONDS
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = json.loads(resp.read())
                if body.get("status") == "UP":
                    return
                last_error = f"status={body.get('status')}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = str(exc)
        time.sleep(config.SERVICE_HEALTH_POLL_INTERVAL_SECONDS)
    raise DockerControlError(
        f"{label} did not report UP within {timeout_seconds}s at {url}; last error: {last_error}"
    )


def wait_for_full_stack_health(timeout_seconds: int = None) -> None:
    for url, label in [
        (config.ORDER_SERVICE_HEALTH_URL, "order-service"),
        (config.INVENTORY_SERVICE_HEALTH_URL, "inventory-service"),
        (config.PAYMENT_SERVICE_HEALTH_URL, "payment-service"),
        (config.GATEWAY_HEALTH_URL, "gateway"),
    ]:
        wait_for_health(url, label, timeout_seconds)
