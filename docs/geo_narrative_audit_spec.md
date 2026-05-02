# GEO Narrative Audit

## Product Direction

This product is no longer trying to infer whether a brand is authoritative across the whole public web.
It is now focused on a narrower, more defensible question:

**Are the brand's owned and spokesperson-controlled channels coherent, structured, and retrieval-friendly enough for GEO and AI discovery?**

The audit is intentionally scoped to sources the analyst inputs directly.
If a channel is not supplied, the system does not search for it and does not score from it.

## Core Promise

The tool helps SJK Labs diagnose:

- whether the brand says the same clear thing across channels
- whether the website is structurally strong enough for AI retrieval
- whether the spokesperson reinforces or dilutes the company narrative
- whether the current content architecture is strong enough to support later authority-building

The commercial ladder is:

1. run the owned-channel GEO audit
2. identify narrative fragmentation and retrieval weaknesses
3. sell narrative strategy / messaging architecture work
4. sell channel rewrites and structural GEO improvements
5. sell authority-building and PR distribution work later

## Inputs

Every audit starts from manually entered channels.

### Required

- company name
- website

### Optional company channels

- company LinkedIn
- company Substack
- company Medium
- company YouTube

### Optional spokesperson profile

V1 supports a single spokesperson profile, usually the founder or principal voice.

- spokesperson name
- spokesperson LinkedIn
- spokesperson Substack
- spokesperson Medium
- spokesperson YouTube

Future versions can support multiple spokesperson profiles, but v1 should optimize for one primary public voice.

## Sources Included

Only these analyst-supplied surfaces are in scope:

- website
- company LinkedIn
- spokesperson LinkedIn
- company Substack
- spokesperson Substack
- company Medium
- spokesperson Medium
- company YouTube
- spokesperson YouTube

The website remains the core GEO surface and is always included.

## Sources Excluded For This Version

These are deliberately out of scope for the owned-channel GEO audit:

- media mention discovery
- tier-1 / tier-2 press scoring
- review scraping
- complaint/dispute scanning
- broad public-web search for corroboration
- authority estimation from third-party mentions

Those belong in a later authority-building layer, not in this product's first job.

## Audit Questions

The audit should answer five questions:

1. **Narrative clarity**
   Is the core proposition understandable, specific, and memorable?

2. **Narrative consistency across channels**
   Are the same claims, frames, and descriptors repeated across the website and declared channels?

3. **Spokesperson alignment**
   Does the spokesperson reinforce the same company narrative, or introduce drift?

4. **Website GEO readiness**
   Is the site structured in a way that helps AI systems retrieve and restate the brand accurately?

5. **Content architecture risk**
   Is the current content ecosystem coherent enough to support future GEO/authority work?

## Output Shape

The audit remains analyst-facing.

It should surface:

- detected core narrative
- repeated language / signature phrases
- channel-by-channel message alignment
- contradictions and drift
- website structure risks for GEO
- spokesperson alignment or dilution
- recommended strategic next move

## Recommended Scoring Direction

The inherited five-proxy framework is no longer the best fit.
Near-term implementation should still preserve backward-compatible output shapes where useful, but the product itself should move toward a simpler owned-channel model:

- Website GEO Readiness
- Narrative Consistency
- Spokesperson Alignment
- Content Proof / Claim Support

This can be introduced incrementally while the existing audit record shape remains stable.

## Implementation Notes

- Input-only means input-only.
- No channel discovery via search should be required for this mode.
- If a channel is not supplied, the tool should say it was not analyzed.
- Missing channels reduce coverage; they should not be guessed.
- Under-counting is preferable to invented coherence.

## Immediate Refactor Goal

First pass:

- add explicit company and spokesperson channel inputs
- collect text only from those channels
- stop treating search discovery as the primary source of truth
- run default audits from owned-channel proxies only

Later passes:

- richer website GEO structure heuristics
- better channel comparison prompts
- channel-level reporting
- multiple spokesperson support
