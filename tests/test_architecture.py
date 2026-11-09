"""Layering rules (hexagonal): dependencies point inwards only.

domain          -> (domain, config)            pure rules, no I/O, no frameworks
application     -> (domain, config, application) use cases, tenant guard, ports
infrastructure  -> (domain, infrastructure)    adapters: SQLite, Excel
interfaces      -> anything                    composition roots: CLI, REST API, web UI
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "kccs_evidence"
ALLOWED = {
    "domain": {"domain", "config"},
    "application": {"domain", "config", "application"},
    "infrastructure": {"domain", "infrastructure"},
    "config": {"domain", "config"},
}
FRAMEWORKS = {"fastapi", "starlette", "uvicorn", "pydantic", "sqlite3", "openpyxl"}


def _imports(py: Path) -> list[tuple[str, int]]:
    """(absolute kccs_evidence sub-package or top-level module, level) for each import in a file."""
    rel = py.relative_to(SRC).with_suffix("").parts
    out = []
    for node in ast.walk(ast.parse(py.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(rel[: len(rel) - node.level])
                target = [*base, *(node.module or "").split(".")] if node.module else base
                out.append((target[0] if target else "", 1))
            elif node.module:
                out.append((node.module.split(".")[0], 0))
        elif isinstance(node, ast.Import):
            out += [(a.name.split(".")[0], 0) for a in node.names]
    return out


@pytest.mark.parametrize("layer", sorted(ALLOWED))
def test_layer_only_depends_inwards(layer):
    bad = []
    for py in (SRC / layer).rglob("*.py"):
        for target, internal in _imports(py):
            if internal and target and target not in ALLOWED[layer] and target != "__init__":
                bad.append(f"{py.relative_to(SRC)} -> {target}")
            if not internal and target == "kccs_evidence":
                bad.append(f"{py.relative_to(SRC)} uses an absolute self-import")
    assert not bad, bad


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_core_layers_do_not_import_frameworks_or_drivers(layer):
    bad = [
        f"{py.relative_to(SRC)} -> {t}"
        for py in (SRC / layer).rglob("*.py")
        for t, internal in _imports(py)
        if not internal and t in FRAMEWORKS
    ]
    assert not bad, bad


def test_fingerprint_excludes_interfaces_but_covers_rules():
    from kccs_evidence.application.assessment import FINGERPRINTED_LAYERS

    assert "interfaces" not in FINGERPRINTED_LAYERS
    assert {"domain", "application", "infrastructure", "config"} <= set(FINGERPRINTED_LAYERS)
