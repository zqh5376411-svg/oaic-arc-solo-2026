"""Small ARC-Bench event, traceability, and checkpoint adapter."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def _resolve_under(project_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_dir / path


def _safe_value(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(marker in lowered for marker in ("api_key", "authorization", "password", "token")):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): _safe_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:4000]
    return value


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe_value(payload), ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _load_official_runtime(project_dir: Path) -> Any | None:
    try:
        from arcbench_agent_runtime import AgentRuntime
    except ModuleNotFoundError as exc:
        if exc.name == "arcbench_agent_runtime":
            return None
        raise
    return AgentRuntime.from_env(project_dir=str(project_dir))


_RUNNER_EVENT_METHODS = {
    "running": "mark_run_started",
    "completed": "mark_run_completed",
    "failed": "mark_run_failed",
    "paused": "mark_run_paused",
    "resumed": "mark_run_resumed",
}

_REQUIREMENT_EVENT_METHODS = {
    ("design", "running"): "mark_design_started",
    ("design", "completed"): "mark_design_done",
    ("design", "failed"): "mark_design_failed",
    ("implement", "running"): "mark_implementation_started",
    ("implement", "completed"): "mark_implementation_done",
    ("implement", "failed"): "mark_implementation_failed",
    ("test", "passed"): "mark_test_passed",
    ("test", "failed"): "mark_test_failed",
}


class Runtime:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir.resolve()
        self._official = _load_official_runtime(self.project_dir)
        events_value = os.environ.get(
            "ARCBENCH_RUNNER_EVENTS_PATH", ".arc/runner-events.jsonl"
        )
        traceability_value = os.environ.get(
            "ARCBENCH_TRACEABILITY_DIR", ".arc/traceability"
        )
        self.events_path = _resolve_under(self.project_dir, events_value)
        self.traceability_dir = _resolve_under(self.project_dir, traceability_value)
        self.production_trace_path = self.project_dir / ".arc" / "production-trace.jsonl"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.traceability_dir.mkdir(parents=True, exist_ok=True)

    @property
    def backend(self) -> str:
        return "official-sdk" if self._official is not None else "local-fallback"

    def runner_state(self, state: str, message: str = "") -> None:
        if self._official is not None:
            method_name = _RUNNER_EVENT_METHODS.get(state)
            if method_name is None:
                raise ValueError(f"unsupported runner state: {state}")
            getattr(self._official.events, method_name)(message or None)
            return
        _append_jsonl(
            self.events_path,
            {
                "type": "runner_state",
                "state": state,
                "timestamp": utc_timestamp(),
                "message": message or None,
            },
        )

    def requirement_state(
        self, node_id: str, phase: str, status: str, message: str = ""
    ) -> None:
        if self._official is not None:
            method_name = _REQUIREMENT_EVENT_METHODS.get((phase, status))
            if method_name is None:
                raise ValueError(
                    f"unsupported requirement state: {phase}/{status}"
                )
            getattr(self._official.events, method_name)(node_id, message or None)
            return
        _append_jsonl(
            self.events_path,
            {
                "type": "requirement_state",
                "node_id": node_id,
                "phase": phase,
                "status": status,
                "timestamp": utc_timestamp(),
                "message": message or None,
            },
        )
        states_path = self.traceability_dir / "node_states.json"
        states = self._read_object(states_path)
        states[node_id] = {
            "node_id": node_id,
            "phase": phase,
            "status": status,
            "updated_at": utc_timestamp(),
        }
        _write_json(states_path, states)

    def trace(self, event_type: str, **payload: Any) -> None:
        _append_jsonl(
            self.production_trace_path,
            {"timestamp": utc_timestamp(), "type": event_type, **payload},
        )

    def store_requirement_tree(self, root: dict[str, Any]) -> None:
        if self._official is not None:
            self._official.traceability.init_store()
            self._official.traceability.store_requirement_tree(root)
            return
        requirements: dict[str, Any] = {}
        scenarios: dict[str, Any] = {}

        def walk(node: dict[str, Any], parent_id: str | None = None) -> None:
            node_id = str(node.get("id") or node.get("req_id") or "").strip()
            children = [
                item for item in (node.get("children") or []) if isinstance(item, dict)
            ]
            child_ids = [
                str(item.get("id") or item.get("req_id") or "").strip()
                for item in children
            ]
            node_scenarios = [
                item for item in (node.get("scenarios") or []) if isinstance(item, dict)
            ]
            requirements[node_id] = {
                "req_id": node_id,
                "name": str(node.get("name") or ""),
                "description": str(node.get("description") or ""),
                "parent_id": parent_id,
                "children_ids": child_ids,
                "dependencies": node.get("dependencies") or [],
                "scenarios": node_scenarios,
            }
            for scenario in node_scenarios:
                scenario_id = str(
                    scenario.get("id") or scenario.get("scenario_id") or ""
                ).strip()
                if scenario_id:
                    scenarios[scenario_id] = {
                        "scenario_id": scenario_id,
                        "req_id": node_id,
                        "name": str(scenario.get("name") or scenario_id),
                        "steps": scenario.get("steps") or [],
                    }
            for child in children:
                walk(child, node_id)

        walk(root)
        _write_json(self.traceability_dir / "requirements.json", requirements)
        _write_json(self.traceability_dir / "scenarios.json", scenarios)

    def checkpoint(self, message: str) -> str | None:
        if self._official is not None:
            self._official.git.ensure_repo(create_initial_commit=False)
            self._official.git.commit(message)
            return self._official.git.current_head()
        self._ensure_repository()
        self._git("add", ".")
        committed = self._git("commit", "-m", message, check=False)
        combined = (committed.stdout + committed.stderr).lower()
        if committed.returncode != 0:
            if "nothing to commit" in combined:
                return self._head()
            raise RuntimeError(combined.strip() or "git checkpoint failed")
        revision = self._head()
        _append_jsonl(
            self.events_path,
            {
                "type": "signal",
                "reason": "git_checkpoint",
                "timestamp": utc_timestamp(),
                "message": message,
                "revision": revision,
                "refresh": {"commit_history": True, "preview": True},
            },
        )
        return revision

    def _ensure_repository(self) -> None:
        if not (self.project_dir / ".git").exists():
            self._git("init")
        self._git("config", "user.name", "Jianxian ARC Agent")
        self._git("config", "user.email", "arc-agent@example.invalid")
        gitignore = self.project_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "frontend/node_modules/\nfrontend/dist/\nbackend/node_modules/\n"
                ".arc/runner-events.jsonl\n.arc/production-trace.jsonl\n",
                encoding="utf-8",
            )

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if check and completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(detail or f"git {' '.join(args)} failed")
        return completed

    def _head(self) -> str | None:
        result = self._git("rev-parse", "HEAD", check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}
