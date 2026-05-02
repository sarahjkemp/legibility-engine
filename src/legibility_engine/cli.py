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
    founder_linkedin_url: str | None = typer.Option(None, help="Optional founder LinkedIn URL."),
    founder_name: str | None = typer.Option(None, help="Optional founder name."),
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
        competitor_urls=(competitor_urls or [])[:3],
    )
    result = asyncio.run(run_audit(target, config=load_audit_config(), settings=settings))
    paths = save_audit_result(result, output_dir or Path(settings.audits_dir))
    typer.echo(f"Wrote {paths['json']}")
    typer.echo(f"Wrote {paths['worksheet']}")


if __name__ == "__main__":
    app()
