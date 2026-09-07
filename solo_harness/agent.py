"""One bounded coding loop plus one targeted repair cycle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .model import OpenAIChatClient
from .runtime import Runtime
from .validation import ValidationReport, Validator
from .workspace import Workspace, tool_schemas


SYSTEM_PROMPT = """You are a coding agent inside a scored ARC-Bench harness.
Implement the supplied requirements in the existing frontend/ and backend/ application.

Rules:
- Use tools to inspect and edit files; do not only describe a solution.
- Only frontend/ and backend/ are writable.
- Keep frontend buildable with `npm run build` and backend startable with `npm start` using PORT.
- Implement behavior end to end and persist mutable state in the backend when requirements imply persistence.
- Put authorization, validation, and state-transition rules in backend logic, not only disabled UI controls.
- Use visible labels, semantic plain-text buttons, type="text" inputs, and local DOM status/error messages.
- Do not use alert(), confirm(), prompt(), screenshots, hard-coded test answers, or hidden-test guesses.
- Make the smallest coherent change. Read related files together, then write them in batches.
- Call run_validation once after the planned edits and repair every reported failure before stopping.
Return a short summary only after the implementation is ready."""


@dataclass(frozen=True)
class AgentOutcome:
    passed: bool
    report: ValidationReport
    changed_files: tuple[str, ...]
    turns: int
    summary: str


class CodingAgent:
    def __init__(
        self,
        client: OpenAIChatClient,
        workspace: Workspace,
        validator: Validator,
        runtime: Runtime,
        max_turns: int = 12,
    ) -> None:
        self.client = client
        self.workspace = workspace
        self.validator = validator
        self.runtime = runtime
        self.max_turns = max_turns
        self.turns = 0
        self.last_summary = ""

    def run(self, requirements: dict[str, Any]) -> AgentOutcome:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Implement this requirement tree:\n"
                + json.dumps(requirements, ensure_ascii=False, indent=2),
            },
        ]
        self._run_turns(messages, self.max_turns, phase="implementation")
        report = self.validator.validate()

        needs_repair = not report.passed or not self.workspace.changed_files
        if needs_repair:
            reason = report.summary
            if not self.workspace.changed_files:
                reason += "\nFAIL agent edits: no generated source file was changed"
            self.runtime.trace("repair_started", reason=reason)
            messages.append(
                {
                    "role": "user",
                    "content": "One final repair cycle is available. Fix only these concrete gaps, "
                    "then run validation once:\n" + reason,
                }
            )
            self._run_turns(messages, 4, phase="repair")
            report = self.validator.validate()

        passed = report.passed and bool(self.workspace.changed_files)
        return AgentOutcome(
            passed=passed,
            report=report,
            changed_files=tuple(sorted(self.workspace.changed_files)),
            turns=self.turns,
            summary=self.last_summary,
        )

    def _run_turns(
        self, messages: list[dict[str, Any]], limit: int, *, phase: str
    ) -> None:
        for _ in range(limit):
            self.turns += 1
            self.runtime.trace("model_request", phase=phase, turn=self.turns)
            reply = self.client.complete(messages, tool_schemas())
            content = _content_text(reply.get("content"))
            tool_calls = reply.get("tool_calls") or []
            self.runtime.trace(
                "model_response",
                phase=phase,
                turn=self.turns,
                content=content,
                tools=[
                    str((item.get("function") or {}).get("name") or "")
                    for item in tool_calls
                    if isinstance(item, dict)
                ],
            )

            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": content or None,
            }
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            messages.append(assistant_message)

            if not tool_calls:
                self.last_summary = content
                return

            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    continue
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                call_id = str(call.get("id") or f"call-{self.turns}-{index}")
                arguments = _arguments(function.get("arguments"))
                result = self.workspace.dispatch(name, arguments, self.validator.validate)
                self.runtime.trace(
                    "tool_call",
                    phase=phase,
                    turn=self.turns,
                    tool=name,
                    arguments=arguments,
                    result=result,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )


def _arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(item.get("text") or "") if isinstance(item, dict) else str(item)
            for item in value
        ).strip()
    return ""
