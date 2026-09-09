from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from solo_harness.agent import CodingAgent
from solo_harness.model import OpenAIChatClient
from solo_harness.requirements import load_requirements
from solo_harness.runtime import Runtime
from solo_harness.validation import Validator
from solo_harness.workspace import Workspace, scaffold_project


REPO_ROOT = Path(__file__).resolve().parent.parent


class RequirementTests(unittest.TestCase):
    def test_loads_example_requirement_tree(self) -> None:
        bundle = load_requirements(REPO_ROOT / "examples")
        self.assertEqual(bundle.root["id"], "ROOT")
        self.assertEqual([node["id"] for node in bundle.actionable_nodes], ["task-list"])

    def test_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "requirements.yaml"
            path.write_text(
                "id: ROOT\nchildren:\n  - id: same\n  - id: same\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_requirements(path)


class WorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        scaffold_project(REPO_ROOT / "templates" / "web", self.root)
        self.workspace = Workspace(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_lists_and_reads_starter_files(self) -> None:
        listing = self.workspace.list_files()
        self.assertIn("frontend/src/index.html", listing["files"])
        result = self.workspace.read_files(["frontend/src/index.html"])
        self.assertIn("Ready for requirements", result["files"][0]["content"])

    def test_write_and_unique_replace(self) -> None:
        self.workspace.write_file("frontend/src/note.txt", "old value")
        self.workspace.replace_text("frontend/src/note.txt", "old", "new")
        self.assertEqual(
            (self.root / "frontend/src/note.txt").read_text(encoding="utf-8"),
            "new value",
        )

    def test_rejects_paths_outside_generated_sources(self) -> None:
        with self.assertRaises(ValueError):
            self.workspace.write_file("../secret.txt", "no")
        with self.assertRaises(ValueError):
            self.workspace.write_file(".arc/trace.json", "no")


class RuntimeTests(unittest.TestCase):
    def test_local_fallback_writes_runner_event_and_traceability(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            with patch(
                "solo_harness.runtime._load_official_runtime", return_value=None
            ):
                runtime = Runtime(Path(value))
            runtime.runner_state("running", "test")
            runtime.requirement_state("R1", "design", "running")
            self.assertEqual(runtime.backend, "local-fallback")
            event = json.loads(runtime.events_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(event["type"], "runner_state")
            states = json.loads(
                (runtime.traceability_dir / "node_states.json").read_text(encoding="utf-8")
            )
            self.assertEqual(states["R1"]["status"], "running")

    def test_prefers_official_runtime_for_events_traceability_and_git(self) -> None:
        sdk = Mock()
        sdk.git.current_head.return_value = "official-head"
        factory = Mock()
        factory.from_env.return_value = sdk
        module = ModuleType("arcbench_agent_runtime")
        module.AgentRuntime = factory  # type: ignore[attr-defined]
        requirement_tree = {"id": "ROOT", "children": [{"id": "R1"}]}

        with tempfile.TemporaryDirectory() as value, patch.dict(
            sys.modules, {"arcbench_agent_runtime": module}
        ):
            root = Path(value).resolve()
            runtime = Runtime(root)
            runtime.runner_state("running", "start")
            runtime.runner_state("completed", "done")
            runtime.runner_state("failed", "broken")
            runtime.requirement_state("R1", "design", "running")
            runtime.requirement_state("R1", "design", "completed")
            runtime.requirement_state("R1", "implement", "running")
            runtime.requirement_state("R1", "implement", "completed")
            runtime.requirement_state("R1", "implement", "failed")
            runtime.requirement_state("R1", "test", "passed")
            runtime.requirement_state("R1", "test", "failed")
            runtime.store_requirement_tree(requirement_tree)
            revision = runtime.checkpoint("checkpoint")

        self.assertEqual(runtime.backend, "official-sdk")
        factory.from_env.assert_called_once_with(project_dir=str(root))
        sdk.events.mark_run_started.assert_called_once_with("start")
        sdk.events.mark_run_completed.assert_called_once_with("done")
        sdk.events.mark_run_failed.assert_called_once_with("broken")
        sdk.events.mark_design_started.assert_called_once_with("R1", None)
        sdk.events.mark_design_done.assert_called_once_with("R1", None)
        sdk.events.mark_implementation_started.assert_called_once_with("R1", None)
        sdk.events.mark_implementation_done.assert_called_once_with("R1", None)
        sdk.events.mark_implementation_failed.assert_called_once_with("R1", None)
        sdk.events.mark_test_passed.assert_called_once_with("R1", None)
        sdk.events.mark_test_failed.assert_called_once_with("R1", None)
        sdk.traceability.init_store.assert_called_once_with()
        sdk.traceability.store_requirement_tree.assert_called_once_with(requirement_tree)
        sdk.git.ensure_repo.assert_called_once_with(create_initial_commit=False)
        sdk.git.commit.assert_called_once_with("checkpoint")
        self.assertEqual(revision, "official-head")
        self.assertFalse(runtime.events_path.exists())


class ModelTests(unittest.TestCase):
    def test_builds_chat_completions_endpoint(self) -> None:
        client = OpenAIChatClient("key", "https://example.test/v1/", "model")
        self.assertEqual(client.endpoint, "https://example.test/v1/chat/completions")


@unittest.skipUnless(shutil.which("node") and shutil.which("npm"), "Node.js is required")
class ValidationTests(unittest.TestCase):
    def test_starter_builds_and_starts(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            scaffold_project(REPO_ROOT / "templates" / "web", root)
            report = Validator(root).validate()
            self.assertTrue(report.passed, report.summary)

    def test_agent_tool_loop_changes_and_validates_project(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def complete(self, messages: list[dict], tools: list[dict]) -> dict:
                self.calls += 1
                if self.calls == 1:
                    return {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "replace_text",
                                    "arguments": json.dumps(
                                        {
                                            "path": "frontend/src/index.html",
                                            "old": "Ready for requirements",
                                            "new": "Demo requirement implemented",
                                        }
                                    ),
                                },
                            }
                        ],
                    }
                return {"content": "Implementation complete."}

        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            scaffold_project(REPO_ROOT / "templates" / "web", root)
            runtime = Runtime(root)
            agent = CodingAgent(
                FakeClient(),  # type: ignore[arg-type]
                Workspace(root),
                Validator(root),
                runtime,
            )
            outcome = agent.run(load_requirements(REPO_ROOT / "examples").root)
            self.assertTrue(outcome.passed, outcome.report.summary)
            self.assertIn("frontend/src/index.html", outcome.changed_files)
            self.assertEqual(outcome.turns, 2)

    def test_runs_project_owned_test_against_live_server(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            scaffold_project(REPO_ROOT / "templates" / "web", root)
            package_path = root / "backend" / "package.json"
            package = json.loads(package_path.read_text(encoding="utf-8"))
            package["scripts"]["test"] = "node test-live.mjs"
            package_path.write_text(json.dumps(package), encoding="utf-8")
            (root / "backend" / "test-live.mjs").write_text(
                """const base = process.env.ARCBENCH_BASE_URL;
if (!base) throw new Error("ARCBENCH_BASE_URL is missing");
const response = await fetch(`${base}/api/health`);
if (!response.ok) throw new Error(`health returned ${response.status}`);
""",
                encoding="utf-8",
            )

            report = Validator(root).validate()

            self.assertTrue(report.passed, report.summary)
            self.assertIn("backend npm run test", [check.name for check in report.checks])

    def test_project_owned_test_failure_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            scaffold_project(REPO_ROOT / "templates" / "web", root)
            package_path = root / "backend" / "package.json"
            package = json.loads(package_path.read_text(encoding="utf-8"))
            package["scripts"]["test"] = "node test-fail.mjs"
            package_path.write_text(json.dumps(package), encoding="utf-8")
            (root / "backend" / "test-fail.mjs").write_text(
                "throw new Error('expected project test failure');\n",
                encoding="utf-8",
            )

            report = Validator(root).validate()

            self.assertFalse(report.passed)
            failure = next(
                check for check in report.checks if check.name == "backend npm run test"
            )
            self.assertIn("expected project test failure", failure.summary)


if __name__ == "__main__":
    unittest.main()
