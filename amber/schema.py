"""Shared data format for every specialist. One tool's output feeds another's input unchanged."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"
HANDOFF_BELOW = 0.70  # findings under this confidence go to a person


class Verdict(str, Enum):
    complies = "complies"
    deviates = "deviates"
    missing = "missing"
    unclear = "unclear"


class Citation(BaseModel):
    """Where a fact came from. Only kept if `quote` was found on `page` of `doc_id`."""
    doc_id: str
    page: int = Field(ge=1, description="1-based PDF page")
    locator: str = Field("", description="paragraph number, table row, cell, etc.")
    quote: str
    match: str = Field("exact", description="exact | normalized | fuzzy: how the quote was found")
    ocr: bool = False


class Finding(BaseModel):
    id: str
    claim: str
    status: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = []
    needs_human: bool = False
    why: str = ""
    data: dict[str, Any] = {}


class Handoff(BaseModel):
    finding_id: str
    reason: str


class ModelUsage(BaseModel):
    name: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    calls: int = 0


class RunInfo(BaseModel):
    models: list[ModelUsage] = []
    latency_ms: int = 0

    @property
    def cost_usd(self) -> float:
        return round(sum(m.cost_usd for m in self.models), 6)


class ToolResult(BaseModel):
    tool: str
    version: str = SCHEMA_VERSION
    result: dict[str, Any] = {}
    findings: list[Finding] = []
    needs_human: list[Handoff] = []
    run: RunInfo = RunInfo()

    def finalize(self) -> "ToolResult":
        """Route every low-confidence or uncited finding to a person."""
        self.needs_human = []
        for f in self.findings:
            if f.status != Verdict.missing and not f.citations:
                f.needs_human = True
                f.why = (f.why + " | no verified source").strip(" |")
            if f.confidence < HANDOFF_BELOW or f.status == Verdict.unclear:
                f.needs_human = True
            if f.needs_human:
                self.needs_human.append(Handoff(finding_id=f.id, reason=f.why or "low confidence"))
        return self
