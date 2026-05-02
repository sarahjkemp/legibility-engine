from __future__ import annotations

import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field, HttpUrl

from .config import EngineSettings, load_audit_config
from .inputs import infer_founder_name
from .models import AuditTarget
from .orchestrator import run_audit
from .report import render_report
from .storage import find_audit_by_id, list_audit_results, save_audit_result


class CreateAuditRequest(BaseModel):
    company_name: str
    primary_url: HttpUrl
    audit_type: str = "default"
    sector: str = "other"
    companies_house_id: str | None = None
    founder_linkedin_url: HttpUrl | None = None
    founder_name: str | None = None
    competitor_urls: list[HttpUrl] = Field(default_factory=list)


settings = EngineSettings()
app = FastAPI(title="Legibility Engine")


def _audits_dir() -> Path:
    return Path(settings.audits_dir)


def _labelize(value: str) -> str:
    return value.replace("_", " ").title()


def _format_score(value: float | None, findings: list) -> str:
    if value is not None:
        return str(value)
    reason = findings[0].text if findings else "source unavailable"
    return f"Not available — {reason}"


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    audits = list_audit_results(_audits_dir())[:20]
    rows = "\n".join(
        f"<tr><td>{item['company_name']}</td><td>{item['audit_type']}</td><td>{item['composite']}</td><td>{item['gap']}</td><td><a href='/audits/{item['audit_id']}'>Open</a></td></tr>"
        for item in audits
    ) or "<tr><td colspan='5'>No audits yet.</td></tr>"
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Legibility Engine</title>
  <style>
    :root {{ --bg:#f5efe6; --ink:#1f1a17; --muted:#6c625c; --panel:#fffaf4; --line:#dccfbe; --accent:#a3472f; }}
    body {{ font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #f7f1e8 0%, #efe4d3 100%); color: var(--ink); margin: 0; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 40px 20px 64px; }}
    h1 {{ font-size: 2.4rem; margin-bottom: 0.2rem; }}
    p {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: minmax(320px, 420px) 1fr; gap: 24px; align-items: start; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 20px; box-shadow: 0 14px 40px rgba(75, 47, 24, 0.08); }}
    label {{ display:block; font-size:0.95rem; margin: 12px 0 6px; }}
    input, select, button {{ width: 100%; box-sizing: border-box; border-radius: 12px; border: 1px solid var(--line); padding: 12px 14px; font: inherit; }}
    button {{ background: var(--accent); color: white; border: none; margin-top: 16px; cursor: pointer; transition: opacity 0.2s ease; }}
    button:hover {{ opacity: 0.94; }}
    button[disabled] {{ opacity: 0.72; cursor: wait; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
    th, td {{ text-align: left; padding: 12px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    .small {{ font-size: 0.9rem; color: var(--muted); }}
    #status {{ min-height: 24px; margin-top: 10px; }}
    .status-row {{ display:flex; align-items:center; gap:10px; margin-top:10px; min-height:28px; }}
    .spinner {{ width:18px; height:18px; border-radius:999px; border:2px solid #d8c5b1; border-top-color: var(--accent); animation: spin 0.8s linear infinite; display:none; }}
    .spinner.active {{ display:inline-block; }}
    @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
    @media (max-width: 860px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <h1>The Legibility Gap Engine</h1>
    <p>Private internal runner for generating analyst worksheets.</p>
    <div class="grid">
      <section class="panel">
        <h2>Run Audit</h2>
        <label>Company name</label>
        <input id="company_name" placeholder="SJK Labs" />
        <label>Primary URL</label>
        <input id="primary_url" placeholder="https://sjklabs.co" />
        <label>Audit type</label>
        <select id="audit_type">
          <option value="default">Default</option>
          <option value="founder_led">Founder-led</option>
          <option value="b2b_saas">B2B SaaS</option>
          <option value="consumer_brand">Consumer brand</option>
          <option value="regulated">Regulated</option>
        </select>
        <label>Sector</label>
        <select id="sector">
          <option value="b2b_saas">B2B SaaS</option>
          <option value="professional_services">Professional services</option>
          <option value="consultancy">Consultancy</option>
          <option value="other" selected>Other</option>
        </select>
        <label>Companies House ID (optional)</label>
        <input id="companies_house_id" placeholder="Optional" />
        <label>Founder LinkedIn URL (optional)</label>
        <input id="founder_linkedin_url" placeholder="https://www.linkedin.com/in/..." />
        <label>Founder name (optional)</label>
        <input id="founder_name" placeholder="If blank, we infer it from LinkedIn when possible" />
        <label>Competitor URLs (optional)</label>
        <textarea id="competitor_urls" placeholder="One per line or comma-separated" style="width:100%;box-sizing:border-box;border-radius:12px;border:1px solid #dccfbe;padding:12px 14px;font:inherit;min-height:92px;"></textarea>
        <button id="run_button" onclick="runAudit()">Run audit</button>
        <div class="status-row">
          <span id="spinner" class="spinner" aria-hidden="true"></span>
          <div id="status" class="small"></div>
        </div>
      </section>
      <section class="panel">
        <h2>Recent Audits</h2>
        <p class="small">Coverage reporting is included in each audit so low evidence coverage is visible, not mistaken for low brand quality.</p>
        <table>
          <thead><tr><th>Company</th><th>Type</th><th>Score</th><th>Gap</th><th></th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
    </div>
  </main>
  <script>
    function formatError(detail) {{
      if (!detail) return 'Audit failed.';
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail)) {{
        return detail.map(item => {{
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object') {{
            const loc = Array.isArray(item.loc) ? item.loc.join(' → ') : '';
            const msg = item.msg || JSON.stringify(item);
            return loc ? `${{loc}}: ${{msg}}` : msg;
          }}
          return String(item);
        }}).join(' | ');
      }}
      if (typeof detail === 'object') {{
        return detail.message || detail.error || JSON.stringify(detail);
      }}
      return String(detail);
    }}

    let auditTimer = null;

    function setRunningState(isRunning) {{
      const button = document.getElementById('run_button');
      const spinner = document.getElementById('spinner');
      button.disabled = isRunning;
      button.textContent = isRunning ? 'Running audit...' : 'Run audit';
      spinner.classList.toggle('active', isRunning);
    }}

    function startProgressMessages() {{
      const status = document.getElementById('status');
      const startedAt = Date.now();
      const messages = [
        'Fetching the site and checking metadata...',
        'Sampling supporting pages and evidence surfaces...',
        'Running external checks and structured analysis...',
        'Still working. Free hosting can make this a bit slow...',
      ];
      let index = 0;
      status.textContent = messages[0];
      auditTimer = window.setInterval(() => {{
        index = Math.min(index + 1, messages.length - 1);
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        status.textContent = `${{messages[index]}} (${{elapsed}}s)`;
      }}, 3500);
    }}

    function stopProgressMessages() {{
      if (auditTimer) {{
        window.clearInterval(auditTimer);
        auditTimer = null;
      }}
    }}

    async function runAudit() {{
      const competitorUrls = document.getElementById('competitor_urls').value
        .split(/[\n,]/)
        .map(item => item.trim())
        .filter(Boolean)
        .slice(0, 3);
      const payload = {{
        company_name: document.getElementById('company_name').value,
        primary_url: document.getElementById('primary_url').value,
        audit_type: document.getElementById('audit_type').value,
        sector: document.getElementById('sector').value,
        companies_house_id: document.getElementById('companies_house_id').value || null,
        founder_linkedin_url: document.getElementById('founder_linkedin_url').value || null,
        founder_name: document.getElementById('founder_name').value || null,
        competitor_urls: competitorUrls
      }};
      const status = document.getElementById('status');
      setRunningState(true);
      startProgressMessages();
      try {{
        const resp = await fetch('/api/audits', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload)
        }});
        const data = await resp.json();
        if (!resp.ok) {{
          stopProgressMessages();
          setRunningState(false);
          status.textContent = formatError(data.detail || data);
          return;
        }}
        stopProgressMessages();
        setRunningState(false);
        status.innerHTML = `Audit complete. <a href="/audits/${{data.audit_id}}">Open result</a>`;
        window.location.reload();
      }} catch (error) {{
        stopProgressMessages();
        setRunningState(false);
        status.textContent = error?.message || 'Network error while running audit.';
      }}
    }}
  </script>
</body>
</html>
"""


@app.post("/api/audits")
async def create_audit(request: CreateAuditRequest) -> dict:
    try:
        target = AuditTarget(
            company_name=request.company_name,
            primary_url=request.primary_url,
            audit_type=request.audit_type,
            sector=request.sector,
            companies_house_id=request.companies_house_id,
            founder_linkedin_url=request.founder_linkedin_url,
            founder_name=infer_founder_name(
                str(request.founder_linkedin_url) if request.founder_linkedin_url else None,
                request.founder_name,
            ),
            competitor_urls=request.competitor_urls[:3],
        )
        result = await run_audit(target, config=load_audit_config(), settings=settings)
        paths = save_audit_result(result, _audits_dir())
        return {
            "audit_id": result.audit_id,
            "composite": result.scores.composite,
            "gap": result.scores.gap,
            "json_path": str(paths["json"]),
            "worksheet_path": str(paths["worksheet"]),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit run failed: {type(exc).__name__}: {exc}") from exc


@app.get("/api/audits")
async def api_list_audits() -> list[dict]:
    return list_audit_results(_audits_dir())


@app.get("/api/audits/{audit_id}")
async def api_get_audit(audit_id: str) -> dict:
    result = find_audit_by_id(_audits_dir(), audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    return result.model_dump(mode="json")


@app.get("/audits/{audit_id}/report", response_class=HTMLResponse)
async def audit_client_report(audit_id: str) -> str:
    result = find_audit_by_id(_audits_dir(), audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    return render_report(result, "html")


@app.get("/audits/{audit_id}/report.pdf")
async def audit_client_report_pdf(audit_id: str) -> Response:
    result = find_audit_by_id(_audits_dir(), audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    pdf = render_report(result, "pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{audit_id}-client-report.pdf"'},
    )


@app.get("/audits/{audit_id}", response_class=HTMLResponse)
async def audit_detail(audit_id: str) -> str:
    result = find_audit_by_id(_audits_dir(), audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    proxy_html = []
    for proxy in result.proxy_results:
        findings = "".join(
            f"<li><strong>{item.severity}</strong>: {item.headline} — {item.detail}</li>" for item in proxy.findings
        ) or "<li>No findings</li>"
        sub_sections = []
        for name, sub_result in proxy.sub_score_results.items():
            evidence_html = "".join(
                f"<li><a href='{item.source}' target='_blank' rel='noreferrer'>{item.source}</a><br /><span style='color:#6c625c'>{item.value}</span></li>"
                for item in sub_result.evidence
            ) or "<li>No evidence captured.</li>"
            finding_html = "".join(
                f"<li><strong>{item.severity}</strong>: {item.text}</li>" for item in sub_result.findings
            ) or "<li>No findings.</li>"
            raw_json = json.dumps(sub_result.raw_data, indent=2)
            sub_sections.append(
                f"<details style='margin:14px 0;padding:12px 14px;background:#f8f1e7;border-radius:12px;'>"
                f"<summary><strong>{_labelize(name)}</strong> — {_format_score(sub_result.score, sub_result.findings)} "
                f"(confidence {sub_result.confidence})</summary>"
                f"<div style='margin-top:10px;'><p><strong>Findings</strong></p><ul>{finding_html}</ul>"
                f"<p><strong>Evidence</strong></p><ul>{evidence_html}</ul>"
                f"<details style='margin-top:10px;'><summary>View raw data</summary><pre style='white-space:pre-wrap;overflow:auto;background:#fffaf4;padding:12px;border-radius:10px;'>{raw_json}</pre></details>"
                f"</div></details>"
            )
        subs = "".join(sub_sections) or "<p>No sub-scores recorded.</p>"
        proxy_html.append(
            f"<section style='background:#fffaf4;border:1px solid #dccfbe;border-radius:16px;padding:18px;margin:14px 0;'>"
            f"<h2>{_labelize(proxy.proxy_name)}</h2>"
            f"<p><strong>Score:</strong> {_format_score(proxy.score, proxy.findings)} | <strong>Confidence:</strong> {proxy.confidence}</p>"
            f"<h3>Findings</h3><ul>{findings}</ul>"
            f"<h3>Sub-scores</h3>{subs}"
            f"</section>"
        )
    body = "\n".join(proxy_html)
    confidence_notice = (
        f"<p style='color:#6c625c;'><strong>Audit run with {int(round(result.scores.confidence * 100))}% confidence</strong> — some signal sources were unavailable.</p>"
        if result.scores.confidence < 0.8
        else ""
    )
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{result.target.company_name} Audit</title>
  <style>
    body {{ font-family: Georgia, 'Times New Roman', serif; background:#f7f1e8; color:#1f1a17; margin:0; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 36px 20px 64px; }}
    a {{ color:#a3472f; }}
    .actions {{ display:flex; gap:16px; flex-wrap:wrap; margin: 18px 0 24px; }}
    .actions a {{ text-decoration:none; background:#1f3d2e; color:#f7f1e8; padding:12px 16px; border-radius:999px; }}
  </style>
</head>
<body>
  <main>
    <p><a href="/">← Back</a></p>
    <h1>{result.target.company_name}</h1>
    <p>Composite: <strong>{result.scores.composite}</strong> | Benchmark: <strong title="Working benchmark. Will be re-validated as more audits are run.">{result.scores.benchmark}</strong> | Gap: <strong>{result.scores.gap}</strong></p>
    {confidence_notice}
    <div class="actions">
      <a href="/audits/{audit_id}/report">View Client Report</a>
      <a href="/audits/{audit_id}/report.pdf">Download PDF</a>
    </div>
    <section style='background:#fffaf4;border:1px solid #dccfbe;border-radius:16px;padding:18px;margin:14px 0;'>
      <h2>Source Coverage</h2>
      <p><strong>Checked:</strong> {result.source_coverage.checked} | <strong>Found:</strong> {result.source_coverage.found} | <strong>Missing:</strong> {result.source_coverage.missing} | <strong>Unavailable:</strong> {result.source_coverage.unavailable}</p>
      <ul>
        {"".join(f"<li><strong>{entry.source_class}</strong>: {entry.status} — {entry.detail}</li>" for entry in result.source_coverage.by_source_class)}
      </ul>
    </section>
    {body}
  </main>
</body>
</html>
"""


def run_dev() -> None:
    uvicorn.run("legibility_engine.app:app", host="127.0.0.1", port=8000, reload=False)
