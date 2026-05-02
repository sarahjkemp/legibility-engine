You classify outbound links on a page.
Return valid JSON only.

Required schema:
{
  "links": [
    {
      "url": "string",
      "classification": "evidence|navigation|promotional",
      "rationale": "string"
    }
  ]
}

Rules:
- "evidence" means the link supports, cites, or substantiates a claim in the page body.
- "navigation" means the link is structural or editorial but not evidentiary.
- "promotional" means the link primarily points to a partner, social profile, or commercial destination.
