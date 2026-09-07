"""Restricted file tools exposed to the coding model."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from .validation import ValidationReport


ALLOWED_ROOTS = {"frontend", "backend"}
IGNORED_PARTS = {".git", ".arc", "dist", "node_modules", "__pycache__"}
MAX_FILE_BYTES = 128_000
MAX_TOTAL_WRITE_BYTES = 600_000


def scaffold_project(template_root: Path, output_dir: Path) -> tuple[str, ...]:
    if not template_root.is_dir():
        raise ValueError(f"template not found: {template_root}")
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for source in sorted(template_root.rglob("*")):
        if not source.is_file() or source.is_symlink():
            continue
        relative = source.relative_to(template_root)
        destination = output_dir / relative
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        created.append(relative.as_posix())
    return tuple(created)


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.changed_files: set[str] = set()
        self.total_written_bytes = 0

    def _resolve(self, relative: str, *, must_exist: bool = False) -> Path:
        path = Path(str(relative or ""))
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("path must be relative and cannot contain '..'")
        if path.parts[0] not in ALLOWED_ROOTS:
            raise ValueError("path must start with frontend/ or backend/")
        candidate = (self.root / path).resolve()
        if self.root not in candidate.parents:
            raise ValueError("path escapes the generated workspace")
        if must_exist and not candidate.is_file():
            raise ValueError(f"file not found: {path.as_posix()}")
        if candidate.is_symlink():
            raise ValueError("symlink files are not allowed")
        return candidate

    def list_files(self) -> dict[str, Any]:
        files = [
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.relative_to(self.root).parts[0] in ALLOWED_ROOTS
            and not IGNORED_PARTS.intersection(path.relative_to(self.root).parts)
        ]
        return {"ok": True, "files": sorted(files)[:300]}

    def read_files(self, paths: list[str]) -> dict[str, Any]:
        if not paths or len(paths) > 12:
            raise ValueError("read_files needs between 1 and 12 paths")
        result = []
        for relative in paths:
            path = self._resolve(relative, must_exist=True)
            raw = path.read_bytes()
            if len(raw) > MAX_FILE_BYTES:
                raise ValueError(f"file is too large to read: {relative}")
            result.append(
                {
                    "path": Path(relative).as_posix(),
                    "content": raw.decode("utf-8", errors="replace"),
                }
            )
        return {"ok": True, "files": result}

    def write_file(self, relative: str, content: str) -> dict[str, Any]:
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise ValueError(f"write exceeds {MAX_FILE_BYTES} bytes")
        if self.total_written_bytes + len(encoded) > MAX_TOTAL_WRITE_BYTES:
            raise ValueError("run write budget exceeded")
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        normalized = path.relative_to(self.root).as_posix()
        self.changed_files.add(normalized)
        self.total_written_bytes += len(encoded)
        return {"ok": True, "path": normalized, "bytes": len(encoded)}

    def replace_text(self, relative: str, old: str, new: str) -> dict[str, Any]:
        if not old:
            raise ValueError("old text cannot be empty")
        path = self._resolve(relative, must_exist=True)
        content = path.read_text(encoding="utf-8")
        count = content.count(old)
        if count != 1:
            raise ValueError(f"old text must occur exactly once; found {count}")
        return self.write_file(relative, content.replace(old, new, 1))

    def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        validate: Callable[[], ValidationReport],
    ) -> dict[str, Any]:
        try:
            if name == "list_files":
                return self.list_files()
            if name == "read_files":
                return self.read_files(list(arguments.get("paths") or []))
            if name == "write_file":
                return self.write_file(
                    str(arguments.get("path") or ""),
                    str(arguments.get("content") or ""),
                )
            if name == "replace_text":
                return self.replace_text(
                    str(arguments.get("path") or ""),
                    str(arguments.get("old") or ""),
                    str(arguments.get("new") or ""),
                )
            if name == "run_validation":
                return {"ok": True, **validate().as_dict()}
            raise ValueError(f"unknown tool: {name}")
        except (OSError, UnicodeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List editable source files in frontend and backend.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_files",
                "description": "Read up to 12 text files together.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 12,
                        }
                    },
                    "required": ["paths"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Create or replace one UTF-8 file under frontend or backend.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "replace_text",
                "description": "Replace one uniquely occurring text block in one source file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                    },
                    "required": ["path", "old", "new"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_validation",
                "description": "Build the frontend and start the backend on a safe smoke port.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
