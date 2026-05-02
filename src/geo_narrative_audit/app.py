from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .analysis import run_audit
from .models import AuditInput
from .settings import AppSettings
from .storage import find_record, list_records, save_record

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
settings = AppSettings()
app = FastAPI(title="GEO Narrative Audit")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    audits_dir = _audits_dir()
    records = list_records(audits_dir)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "records": records,
            "total_audits": len(records),
        },
    )


@app.post("/audits")
async def create_audit(
    company_name: str = Form(...),
    website_url: str = Form(...),
    about_page_url: str = Form(""),
    company_linkedin_url: str = Form(""),
    company_linkedin_post_urls: str = Form(""),
    company_substack_url: str = Form(""),
    company_substack_article_urls: str = Form(""),
    company_medium_url: str = Form(""),
    company_medium_article_urls: str = Form(""),
    company_youtube_url: str = Form(""),
    company_youtube_video_urls: str = Form(""),
    spokesperson_name: str = Form(""),
    spokesperson_linkedin_url: str = Form(""),
    spokesperson_linkedin_post_urls: str = Form(""),
    spokesperson_substack_url: str = Form(""),
    spokesperson_substack_article_urls: str = Form(""),
    spokesperson_medium_url: str = Form(""),
    spokesperson_medium_article_urls: str = Form(""),
    spokesperson_youtube_url: str = Form(""),
    spokesperson_youtube_video_urls: str = Form(""),
) -> RedirectResponse:
    try:
        audit_input = AuditInput(
            company_name=company_name.strip(),
            website_url=website_url.strip(),
            about_page_url=_blank_to_none(about_page_url),
            company_linkedin_url=_blank_to_none(company_linkedin_url),
            company_linkedin_post_urls=_multi_urls(company_linkedin_post_urls),
            company_substack_url=_blank_to_none(company_substack_url),
            company_substack_article_urls=_multi_urls(company_substack_article_urls),
            company_medium_url=_blank_to_none(company_medium_url),
            company_medium_article_urls=_multi_urls(company_medium_article_urls),
            company_youtube_url=_blank_to_none(company_youtube_url),
            company_youtube_video_urls=_multi_urls(company_youtube_video_urls),
            spokesperson_name=_blank_to_none(spokesperson_name),
            spokesperson_linkedin_url=_blank_to_none(spokesperson_linkedin_url),
            spokesperson_linkedin_post_urls=_multi_urls(spokesperson_linkedin_post_urls),
            spokesperson_substack_url=_blank_to_none(spokesperson_substack_url),
            spokesperson_substack_article_urls=_multi_urls(spokesperson_substack_article_urls),
            spokesperson_medium_url=_blank_to_none(spokesperson_medium_url),
            spokesperson_medium_article_urls=_multi_urls(spokesperson_medium_article_urls),
            spokesperson_youtube_url=_blank_to_none(spokesperson_youtube_url),
            spokesperson_youtube_video_urls=_multi_urls(spokesperson_youtube_video_urls),
        )
        record = await run_audit(audit_input, settings)
        save_record(record, _audits_dir())
        return RedirectResponse(url=f"/audits/{record.audit_id}", status_code=303)
    except Exception as exc:
        return HTMLResponse(
            content=(
                "<!doctype html><html><body style=\"font-family: sans-serif; padding: 32px;\">"
                "<h1>Audit could not be completed</h1>"
                "<p>The app hit a temporary error while processing the declared channels.</p>"
                f"<p><strong>Reason:</strong> {str(exc) or 'Unknown error'}</p>"
                "<p><a href=\"/\">Go back</a></p>"
                "</body></html>"
            ),
            status_code=500,
        )


@app.get("/audits/{audit_id}", response_class=HTMLResponse)
async def view_audit(audit_id: str, request: Request) -> HTMLResponse:
    record = find_record(_audits_dir(), audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    return templates.TemplateResponse(
        request,
        "audit.html",
        {
            "record": record,
        },
    )


def run_dev() -> None:
    import uvicorn

    uvicorn.run("geo_narrative_audit.app:app", host="127.0.0.1", port=8010, reload=False)


def _audits_dir() -> Path:
    path = Path(settings.audits_dir)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def _blank_to_none(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _multi_urls(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]
