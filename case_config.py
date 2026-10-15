"""Casos admitidos y rutas comunes a evaluación, reparación y revisión."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from case_evidence import read_regular, require


@dataclass(frozen=True)
class CaseConfig:
    contract: str
    reviewer_prompt: str
    contract_version: Optional[int] = None


CASE_CONFIGS = {
    "case_01": CaseConfig("001-sum-by-subject.md", "reviewer_case_01.md"),
    "case_02": CaseConfig("002-classify-run.md", "reviewer.md", 2),
}
# Conserva la tabla pública usada por los controladores anteriores.
CASES = {case_id: config.contract for case_id, config in CASE_CONFIGS.items()}


def get_case(case_id):
    require(isinstance(case_id, str) and case_id in CASE_CONFIGS, "Caso no admitido")
    return CASE_CONFIGS[case_id]


def reference_paths(project_root, case_id):
    config = get_case(case_id)
    root = Path(project_root)
    return {
        "solution.py": root / "benchmark" / case_id / "solution.py",
        "test_solution.py": root / "benchmark" / case_id / "test_solution.py",
        "contrato.md": root / "tasks" / config.contract,
    }


def reviewer_prompt_path(project_root, case_id):
    return Path(project_root) / "prompts" / get_case(case_id).reviewer_prompt


def load_reference(project_root, case_id="case_02"):
    reference = {}
    for name, source in reference_paths(project_root, case_id).items():
        content = read_regular(source)
        if content is None:
            raise OSError(f"Falta un archivo regular requerido: {source}")
        reference[name] = content
    return reference
