from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl

from .config import EngineSettings, load_audit_config
from .models import AuditTarget
from .orchestrator import run_audit
from .storage import find_audit_by_id, list_audit_results, save_audit_result


class CreateAuditRequest(BaseModel):
    company_name: str
    primary_url: HttpUrl
    audit_type: str = "default"
    companies_house_id: str | None = None


settings = EngineSettings()
app = FastAPI(title="Legibility Engine")


def _audits_dir() -> Path:
    return Path(settings.audits_dir)


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
    button {{ background: var(--accent); color: white; border: none; margin-top: 16px; cursor: pointer; }}
    button:hover {{ opacity: 0.94; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
    th, td {{ text-align: left; padding: 12px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    .small {{ font-size: 0.9rem; color: var(--muted); }}
    #status {{ min-height: 24px; margin-top: 10px; }}
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
        <label>Companies House ID (optional)</label>
        <input id="companies_house_id" placeholder="Optional" />
        <button onclick="runAudit()">Run audit</button>
        <div id="status" class="small"></div>
      </section>
      <section class="panel">
        <h2>Recent Audits</h2>
        <table>
          <thead><tr><th>Company</th><th>Type</th><th>Score</th><th>Gap</th><th></th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
    </div>
  </main>
  <script>
    async function runAudit() {{
      const payload = {{
        company_name: document.getElementById('company_name').value,
        primary_url: document.getElementById('primary_url').value,
        audit_type: document.getElementById('audit_type').value,
        companies_house_id: document.getElementById('companies_house_id').value || null
      }};
      const status = document.getElementById('status');
      status.textContent = 'Running audit... this can take a little while.';
      const resp = await fetch('/api/audits', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});
      const data = await resp.json();
      if (!resp.ok) {{
        status.textContent = data.detail || 'Audit failed.';
        return;
      }}
      status.innerHTML = `Audit complete. <a href="/audits/${{data.audit_id}}">Open result</a>`;
      window.location.reload();
    }}
  </script>
</body>
</html>
"""


@app.post("/api/audits")
async def create_audit(request: CreateAuditRequest) -> dict:
    target = AuditTarget(
        company_name=request.company_name,
        primary_url=request.primary_url,
        audit_type=request.audit_type,
        companies_house_id=request.companies_house_id,
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


@app.get("/api/audits")
async def api_list_audits() -> list[dict]:
    return list_audit_results(_audits_dir())


@app.get("/api/audits/{audit_id}")
async def api_get_audit(audit_id: str) -> dict:
    result = find_audit_by_id(_audits_dir(), audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    return result.model_dump(mode="json")


@app.get("/audits/{audit_id}", response_class=HTMLResponse)
async def audit_detail(audit_id: str) -> str:
    result = find_audit_by_id(_audits_dir(), audit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit not found")
    proxy_html = []
    for proxy in result.proxy_results:
        findings = "".join(f"<li><strong>{item.severity}</strong>: {item.headline} — {item.detail}</li>" for item in proxy.findings) or "<li>No findings</li>"
        subs = "".join(f"<li>{key}: {value}</li>" for key, value in proxy.sub_scores.items())
        proxy_html.append(
            f"<section style='background:#fffaf4;border:1px solid #dccfbe;border-radius:16px;padding:18px;margin:14px 0;'>"
            f"<h2>{proxy.proxy_name}</h2>"
            f"<p><strong>Score:</strong> {proxy.score} | <strong>Confidence:</strong> {proxy.confidence}</p>"
            f"<h3>Findings</h3><ul>{findings}</ul>"
            f"<h3>Sub-scores</h3><ul>{subs}</ul>"
            f"</section>"
        )
    body = "\n".join(proxy_html)
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
  </style>
</head>
<body>
  <main>
    <p><a href="/">← Back</a></p>
    <h1>{result.target.company_name}</h1>
    <p>Composite: <strong>{result.scores.composite}</strong> | Benchmark: <strong>{result.scores.benchmark}</strong> | Gap: <strong>{result.scores.gap}</strong></p>
    {body}
  </main>
</body>
</html>
"""


def run_dev() -> None:
    uvicorn.run("legibility_engine.app:app", host="127.0.0.1", port=8000, reload=False)
