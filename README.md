# GEO Narrative Audit

Internal audit tool for evaluating whether a brand's **owned channels** are coherent and structured enough for GEO and AI retrieval.

This repo has been intentionally simplified away from broad public-web authority scoring.
The current product direction is:

- the analyst inputs the official channels
- the tool analyzes only those declared channels
- the tool checks narrative consistency, spokesperson alignment, and website GEO readiness
- the output supports a strategy sale:
  - fix the narrative
  - align the channels
  - then build authority later

The working spec for this direction lives in [docs/geo_narrative_audit_spec.md](/Users/sarahkemp/Documents/New%20project/legibility-engine/docs/geo_narrative_audit_spec.md).

## Current Audit Scope

The app now defaults to **owned-surface analysis only**.

Default audit run:

- `Provenance`
- `Consistency`
- `Behavioural Reliability`
  - currently focused on owned-surface proof and claim support

Parked for now:

- `Corroboration`
- `Authority Hierarchy`

Those modules remain in the codebase, but they are not part of the default audit flow while the product is being reshaped around manual channel inputs.

## Inputs

### Required

- company name
- primary website URL

### Optional company channels

- company LinkedIn URL
- company Substack URL
- company Medium URL
- company YouTube URL

### Optional spokesperson channels

V1 uses one primary spokesperson profile.

- spokesperson name
- spokesperson LinkedIn URL
- spokesperson Substack URL
- spokesperson Medium URL
- spokesperson YouTube URL

Legacy founder fields are still present for backward compatibility with older audits.

## What The Tool Pulls From

For the GEO Narrative Audit direction, the tool should analyze only:

- website
- company LinkedIn
- company Substack
- company Medium
- company YouTube
- spokesperson LinkedIn
- spokesperson Substack
- spokesperson Medium
- spokesperson YouTube

If a channel is not supplied, the tool should not guess it and should not search for it.

## Environment

Set what you need:

- `ANTHROPIC_API_KEY`
- `LEGIBILITY_TIMEOUT_SECONDS`
- `LEGIBILITY_USER_AGENT`
- `LEGIBILITY_AUDITS_DIR`
- `LEGIBILITY_CACHE_DIR`

Optional legacy keys still supported while the older modules remain in the repo:

- `BING_SEARCH_API_KEY`
- `OPENPAGERANK_API_KEY`

## Quick Start

```bash
cd /Users/sarahkemp/Documents/New\ project/legibility-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
legibility audit "SJK Labs" "https://sjklabs.co" --audit-type founder_led
```

With declared channels:

```bash
legibility audit "SJK Labs" "https://sjklabs.co" \
  --company-linkedin-url https://www.linkedin.com/company/sjk-labs/ \
  --company-substack-url https://sjklabs.substack.com \
  --spokesperson-name "Sarah Kemp" \
  --spokesperson-linkedin-url https://www.linkedin.com/in/sarahjkemp/ \
  --spokesperson-medium-url https://medium.com/@sarahkemp
```

## Private Web UI

```bash
cd /Users/sarahkemp/Documents/New\ project/legibility-engine
.venv/bin/legibility-web
```

Then open `http://127.0.0.1:8000`.

The dashboard now includes explicit company and spokesperson channel inputs so the audit can use declared surfaces instead of trying to discover them.

## Notes

- This is an analyst tool, not a client-facing report generator.
- The website remains the most important GEO surface in the audit.
- Under-counting is preferable to inventing coherence or authority.
- Multiple spokesperson profiles are a likely v2 feature; v1 is optimized for a single lead public voice.
