from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from .config import EngineSettings, load_audit_config
from .inputs import infer_founder_name
from .models import AuditTarget
from .orchestrator import run_audit
from .storage import save_audit_result

app = typer.Typer(help="Run Legibility Gap audits.")


@app.callback()
def main() -> None:
    """Legibility engine command group."""


@app.command("audit")
def audit(
    company_name: str,
    primary_url: str,
    audit_type: str = typer.Option("default", help="Audit type key from config."),
    sector: str = typer.Option("other", help="Sector key for sector-specific authority logic."),
    companies_house_id: str | None = typer.Option(None, help="Optional Companies House identifier."),
    founder_linkedin_url: str | None = typer.Option(None, help="Legacy founder LinkedIn URL."),
    founder_name: str | None = typer.Option(None, help="Legacy founder name."),
    company_linkedin_url: str | None = typer.Option(None, help="Optional company LinkedIn URL."),
    company_substack_url: str | None = typer.Option(None, help="Optional company Substack URL."),
    company_medium_url: str | None = typer.Option(None, help="Optional company Medium URL."),
    company_youtube_url: str | None = typer.Option(None, help="Optional company YouTube URL."),
    spokesperson_name: str | None = typer.Option(None, help="Optional spokesperson name."),
    spokesperson_linkedin_url: str | None = typer.Option(None, help="Optional spokesperson LinkedIn URL."),
    spokesperson_substack_url: str | None = typer.Option(None, help="Optional spokesperson Substack URL."),
    spokesperson_medium_url: str | None = typer.Option(None, help="Optional spokesperson Medium URL."),
    spokesperson_youtube_url: str | None = typer.Option(None, help="Optional spokesperson YouTube URL."),
    official_substack_url: str | None = typer.Option(None, help="Optional official Substack URL."),
    official_medium_url: str | None = typer.Option(None, help="Optional official Medium URL."),
    official_youtube_url: str | None = typer.Option(None, help="Optional official YouTube URL."),
    competitor_urls: list[str] | None = typer.Option(None, help="Up to three competitor URLs."),
    output_dir: Path = typer.Option(Path("audits"), help="Directory for generated files."),
) -> None:
    settings = EngineSettings()
    target = AuditTarget(
        company_name=company_name,
        primary_url=primary_url,
        audit_type=audit_type,
        sector=sector,
        companies_house_id=companies_house_id,
        founder_linkedin_url=founder_linkedin_url,
        founder_name=infer_founder_name(founder_linkedin_url, founder_name),
        company_linkedin_url=company_linkedin_url,
        company_substack_url=company_substack_url,
        company_medium_url=company_medium_url,
        company_youtube_url=company_youtube_url,
        spokesperson_name=spokesperson_name or infer_founder_name(spokesperson_linkedin_url, None) or founder_name,
        spokesperson_linkedin_url=spokesperson_linkedin_url or founder_linkedin_url,
        spokesperson_substack_url=spokesperson_substack_url,
        spokesperson_medium_url=spokesperson_medium_url,
        spokesperson_youtube_url=spokesperson_youtube_url,
        official_substack_url=official_substack_url,
        official_medium_url=official_medium_url,
        official_youtube_url=official_youtube_url,
        competitor_urls=(competitor_urls or [])[:3],
    )
    result = asyncio.run(run_audit(target, config=load_audit_config(), settings=settings))
    paths = save_audit_result(result, output_dir or Path(settings.audits_dir))
    typer.echo(f"Wrote {paths['json']}")
    typer.echo(f"Wrote {paths['worksheet']}")


if __name__ == "__main__":
    app()
