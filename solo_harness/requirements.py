"""Load and validate the small part of the ARC requirement contract we use."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yaml


@dataclass(frozen=True)
class RequirementBundle:
    source: Path
    root: dict[str, Any]

    @property
    def nodes(self) -> tuple[dict[str, Any], ...]:
        return tuple(_walk(self.root))

    @property
    def actionable_nodes(self) -> tuple[dict[str, Any], ...]:
        return tuple(node for node in self.nodes if _node_id(node) != "ROOT")


def _walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    children = node.get("children") or []
    if not isinstance(children, list):
        return
    for child in children:
        if isinstance(child, dict):
            yield from _walk(child)


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("id") or node.get("req_id") or "").strip()


def resolve_requirements_file(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if path.is_dir():
        path = path / "requirements.yaml"
    if not path.is_file():
        raise ValueError(f"requirements.yaml not found: {path}")
    return path


def load_requirements(value: str | Path) -> RequirementBundle:
    source = resolve_requirements_file(value)
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read requirements: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("requirements.yaml must contain one mapping at the root")
    if _node_id(payload) != "ROOT":
        raise ValueError("requirements root id must be ROOT")
    children = payload.get("children")
    if not isinstance(children, list) or not children:
        raise ValueError("ROOT must contain at least one child requirement")

    ids: set[str] = set()
    for node in _walk(payload):
        node_id = _node_id(node)
        if not node_id:
            raise ValueError("every requirement node must have an id")
        if node_id in ids:
            raise ValueError(f"duplicate requirement id: {node_id}")
        ids.add(node_id)
        if "children" in node and not isinstance(node["children"], list):
            raise ValueError(f"children must be a list for requirement {node_id}")

    return RequirementBundle(source=source, root=payload)
