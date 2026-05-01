from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineSettings(BaseSettings):
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    timeout_seconds: float = Field(default=20.0, alias="LEGIBILITY_TIMEOUT_SECONDS")
    user_agent: str = Field(
        default="LegibilityEngine/0.1 (+https://sjklabs.co)",
        alias="LEGIBILITY_USER_AGENT",
    )
    audits_dir: str = Field(default="audits", alias="LEGIBILITY_AUDITS_DIR")

    model_config = SettingsConfigDict(
        populate_by_name=True,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )


class AuditTypeConfig(BaseModel):
    label: str
    proxy_weights: dict[str, float]


class BenchmarkConfig(BaseModel):
    composite: float
    proxies: dict[str, float]


class AuditConfig(BaseModel):
    audit_types: dict[str, AuditTypeConfig]
    benchmarks: dict[str, BenchmarkConfig]
    tier_1_domains: list[str]
    tier_2_domains: list[str]
    owned_surface_domains: list[str]
    prompt_dir: Path

    def get_audit_type(self, audit_type: str) -> AuditTypeConfig:
        return self.audit_types.get(audit_type, self.audit_types["default"])

    def get_benchmark(self, audit_type: str) -> BenchmarkConfig:
        return self.benchmarks.get(audit_type, self.benchmarks["default"])


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def load_audit_config(base_dir: Path | None = None) -> AuditConfig:
    root = (base_dir or Path(__file__).resolve().parents[2]) / "config"
    audit_types = _read_yaml(root / "audit_types.yaml").get("audit_types", {})
    benchmarks = _read_yaml(root / "benchmarks.yaml").get("audit_type_benchmarks", {})
    tier_lists = _read_yaml(root / "tier_lists.yaml")
    return AuditConfig(
        audit_types={key: AuditTypeConfig(**value) for key, value in audit_types.items()},
        benchmarks={key: BenchmarkConfig(**value) for key, value in benchmarks.items()},
        tier_1_domains=tier_lists.get("tier_1_domains", []),
        tier_2_domains=tier_lists.get("tier_2_domains", []),
        owned_surface_domains=tier_lists.get("owned_surface_domains", []),
        prompt_dir=root / "prompts",
    )
