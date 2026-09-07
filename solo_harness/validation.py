"""Deterministic build and startup checks for generated web applications."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    summary: str
    duration_seconds: float


@dataclass(frozen=True)
class ValidationReport:
    checks: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def summary(self) -> str:
        return "\n".join(
            f"{'PASS' if item.passed else 'FAIL'} {item.name}: {item.summary}"
            for item in self.checks
        )

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "checks": [asdict(item) for item in self.checks],
        }


def _safe_environment(**extra: str) -> dict[str, str]:
    allowed = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "SYSTEMROOT")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.update(
        {
            "CI": "1",
            "NPM_CONFIG_IGNORE_SCRIPTS": "true",
            "npm_config_ignore_scripts": "true",
            **extra,
        }
    )
    return environment


def _run(command: list[str], cwd: Path, timeout: int) -> CheckResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=_safe_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
        summary = output[-2000:] or f"exit code {completed.returncode}"
        return CheckResult(
            " ".join(command),
            completed.returncode == 0,
            summary,
            time.monotonic() - started,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            " ".join(command), False, f"timeout after {timeout}s", time.monotonic() - started
        )
    except OSError as exc:
        return CheckResult(
            " ".join(command), False, str(exc), time.monotonic() - started
        )


def _structure_check(root: Path) -> CheckResult:
    started = time.monotonic()
    required = ("frontend/package.json", "backend/package.json")
    missing = [value for value in required if not (root / value).is_file()]
    if missing:
        return CheckResult(
            "structure", False, "missing: " + ", ".join(missing), time.monotonic() - started
        )
    for value, script in ((required[0], "build"), (required[1], "start")):
        try:
            payload = json.loads((root / value).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return CheckResult("structure", False, str(exc), time.monotonic() - started)
        if not str((payload.get("scripts") or {}).get(script) or "").strip():
            return CheckResult(
                "structure",
                False,
                f"{value} is missing script {script}",
                time.monotonic() - started,
            )
    return CheckResult("structure", True, "required package scripts found", time.monotonic() - started)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _startup_check(root: Path, requested_port: int) -> CheckResult:
    started = time.monotonic()
    port = requested_port or _free_port()
    process: subprocess.Popen[str] | None = None
    output = ""
    passed = False
    summary = "server did not become ready"
    try:
        process = subprocess.Popen(
            ["npm", "start"],
            cwd=root / "backend",
            env=_safe_environment(PORT=str(port)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
        deadline = time.monotonic() + 15
        url = f"http://127.0.0.1:{port}/api/health"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                summary = f"server exited with code {process.returncode}"
                break
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        body = response.read(1000).decode("utf-8", errors="replace")
                        passed = True
                        summary = f"{url} returned 200: {body}"
                        break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                summary = str(exc)
                time.sleep(0.2)
    except OSError as exc:
        summary = str(exc)
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if process is not None and process.stdout is not None:
            try:
                output = process.stdout.read()[-2000:]
            except OSError:
                output = ""
            process.stdout.close()
    if not passed and output.strip():
        summary += "\n" + output.strip()
    return CheckResult(
        "backend startup", passed, summary, time.monotonic() - started
    )


class Validator:
    def __init__(self, root: Path, smoke_port: int = 0) -> None:
        self.root = root.resolve()
        self.smoke_port = smoke_port

    def validate(self) -> ValidationReport:
        checks: list[CheckResult] = [_structure_check(self.root)]
        if not checks[-1].passed:
            return ValidationReport(tuple(checks))

        for directory in (self.root / "frontend", self.root / "backend"):
            check = _run(
                ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund"],
                directory,
                180,
            )
            checks.append(check)
            if not check.passed:
                return ValidationReport(tuple(checks))

        build = _run(["npm", "run", "build"], self.root / "frontend", 180)
        checks.append(build)
        if not build.passed:
            return ValidationReport(tuple(checks))

        checks.append(_startup_check(self.root, self.smoke_port))
        return ValidationReport(tuple(checks))
