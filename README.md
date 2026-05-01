# Legibility Engine

Lean v1 engine for The Legibility Gap.

This scaffold is intentionally evidence-first:

- collectors gather raw source material
- proxies score only from collected evidence
- LLM use is limited to structured extraction and judgment
- outputs are analyst-facing, not client-facing

## What ships in this scaffold

- core audit models
- config-driven scoring and benchmarks
- provenance proxy with direct site checks
- lite consistency, corroboration, authority, and behavioural proxies
- Anthropic wrapper for structured JSON tasks
- CLI runner that emits audit JSON
- minimal FastAPI app for private internal use

## Environment

Set any of the following as needed:

- `ANTHROPIC_API_KEY`
- `LEGIBILITY_TIMEOUT_SECONDS`
- `LEGIBILITY_USER_AGENT`

You can start from `.env.example`.

## Quick start

```bash
cd /Users/sarahkemp/Documents/New\ project/legibility-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
legibility audit "SJK Labs" "https://sjklabs.co" --audit-type founder_led
```

## Private web UI

After installing dependencies:

```bash
cd /Users/sarahkemp/Documents/New\ project/legibility-engine
.venv/bin/legibility-web
```

Then open `http://127.0.0.1:8000`.

## Deploy

Private v1 can be deployed as a single FastAPI web service.

- Railway: [railway.json](/Users/sarahkemp/Documents/New%20project/legibility-engine/railway.json) is included.
- Render: [render.yaml](/Users/sarahkemp/Documents/New%20project/legibility-engine/render.yaml) is included.
- Generic process managers: [Procfile](/Users/sarahkemp/Documents/New%20project/legibility-engine/Procfile) is included.

Required environment variable:

- `ANTHROPIC_API_KEY`

Optional:

- `LEGIBILITY_TIMEOUT_SECONDS`
- `LEGIBILITY_USER_AGENT`
- `LEGIBILITY_AUDITS_DIR`

## Notes

- The target runtime is Python 3.11+, even though this machine currently reports Python 3.9.6.
- `Companies House` and richer search/news integrations are left as upgrade points.
- The v1 lite proxies are designed to fail soft and surface confidence clearly.
- Local verification here is limited because this machine currently lacks `python3.11` and `pytest`.
