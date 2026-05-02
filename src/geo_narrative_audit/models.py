from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


class AuditInput(BaseModel):
    company_name: str
    website_url: HttpUrl
    about_page_url: HttpUrl | None = None
    company_linkedin_post_texts: list[str] = Field(default_factory=list)
    company_substack_article_texts: list[str] = Field(default_factory=list)
    company_medium_article_texts: list[str] = Field(default_factory=list)
    company_youtube_video_texts: list[str] = Field(default_factory=list)
    spokesperson_name: str | None = None
    spokesperson_linkedin_post_texts: list[str] = Field(default_factory=list)
    spokesperson_substack_article_texts: list[str] = Field(default_factory=list)
    spokesperson_medium_article_texts: list[str] = Field(default_factory=list)
    spokesperson_youtube_video_texts: list[str] = Field(default_factory=list)


class ChannelSurface(BaseModel):
    key: str
    label: str
    role: Literal["company", "spokesperson"]
    platform: str
    url: str
    surface_type: Literal["profile", "content", "website"]
    fetched: bool
    blocked: bool = False
    blocked_reason: str | None = None
    message: str
    raw_excerpt: str | None = None
    title: str | None = None
    meta_description: str | None = None
    word_count: int = 0


class ScoreCard(BaseModel):
    overall_geo_readiness: float
    narrative_consistency: float
    website_geo_readiness: float
    spokesperson_alignment: float


class ActionItem(BaseModel):
    title: str
    why_it_matters: str
    what_to_do: str


class AuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    company_name: str
    inputs: AuditInput
    channels: list[ChannelSurface]
    scores: ScoreCard
    diagnosis: str
    retrieval_impact: str
    narrative_spine: list[str]
    where_the_story_breaks: list[str]
    website_findings: list[str]
    rationale: list[str]
    what_to_fix_first: list[ActionItem]
