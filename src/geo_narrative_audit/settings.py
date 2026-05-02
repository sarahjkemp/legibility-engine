from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    timeout_seconds: float = Field(
        default=20.0,
        validation_alias=AliasChoices("GEO_AUDIT_TIMEOUT_SECONDS", "LEGIBILITY_TIMEOUT_SECONDS"),
    )
    user_agent: str = Field(
        default="GEONarrativeAudit/0.1 (+https://sjklabs.co)",
        validation_alias=AliasChoices("GEO_AUDIT_USER_AGENT", "LEGIBILITY_USER_AGENT"),
    )
    audits_dir: str = Field(
        default="audits",
        validation_alias=AliasChoices("GEO_AUDIT_AUDITS_DIR", "LEGIBILITY_AUDITS_DIR"),
    )
    website_additional_page_limit: int = Field(
        default=4,
        validation_alias=AliasChoices("GEO_AUDIT_WEBSITE_PAGE_LIMIT", "LEGIBILITY_WEBSITE_PAGE_LIMIT"),
    )

    model_config = SettingsConfigDict(
        populate_by_name=True,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )
