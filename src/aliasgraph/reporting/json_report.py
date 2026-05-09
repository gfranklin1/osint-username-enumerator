from __future__ import annotations

from pathlib import Path

from aliasgraph.models import ScanResult


def to_json(result: ScanResult, indent: int = 2) -> str:
    return result.model_dump_json(indent=indent)


def write_json(result: ScanResult, path: Path) -> None:
    path.write_text(to_json(result))
