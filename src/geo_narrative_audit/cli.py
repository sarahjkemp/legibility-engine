from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from .analysis import run_audit
from .models import AuditInput
from .settings import AppSettings
from .storage import save_record

app = typer.Typer(help="Run a GEO narrative audit from declared channels.")


@app.command()
def audit(
    company_name: str,
    website_url: str,
    company_linkedin_url: str | None = None,
    company_substack_url: str | None = None,
    company_medium_url: str | None = None,
    company_youtube_url: str | None = None,
    spokesperson_name: str | None = None,
    spokesperson_linkedin_url: str | None = None,
    spokesperson_substack_url: str | None = None,
    spokesperson_medium_url: str | None = None,
    spokesperson_youtube_url: str | None = None,
) -> None:
    settings = AppSettings()
    audit_input = AuditInput(
        company_name=company_name,
        website_url=website_url,
        company_linkedin_url=company_linkedin_url,
        company_substack_url=company_substack_url,
        company_medium_url=company_medium_url,
        company_youtube_url=company_youtube_url,
        spokesperson_name=spokesperson_name,
        spokesperson_linkedin_url=spokesperson_linkedin_url,
        spokesperson_substack_url=spokesperson_substack_url,
        spokesperson_medium_url=spokesperson_medium_url,
        spokesperson_youtube_url=spokesperson_youtube_url,
    )
    record = asyncio.run(run_audit(audit_input, settings))
    output_path = save_record(record, Path(settings.audits_dir))
    typer.echo(str(output_path))
