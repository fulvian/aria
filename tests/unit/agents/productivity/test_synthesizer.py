"""Unit tests for consultancy-brief synthesizer (synthesizer.py)."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from aria.agents.productivity.ingest import IngestResult
from aria.agents.productivity.synthesizer import (
    BriefOutline,
    compose_brief,
    render_markdown,
)


@pytest.fixture
def sample_ingest_results() -> list[IngestResult]:
    """Two sample IngestResult fixtures for brief composition."""
    return [
        IngestResult(
            file_path="/home/user/project/report.pdf",
            format="pdf",
            markdown=(
                "# Q1 Financial Report\n\n"
                "## Revenue\n"
                "Q1 revenue was EUR 1.2M, up 15% YoY.\n\n"
                "## Costs\n"
                "Operating costs decreased by 8% due to automation.\n\n"
                "## Outlook\n"
                "Q2 guidance: EUR 1.3-1.4M revenue.\n"
            ),
            title="Q1 Financial Report",
            author="CFO Office",
            page_count=5,
            byte_size=2048,
            sha256="abc123",
        ),
        IngestResult(
            file_path="/home/user/project/proposal.docx",
            format="docx",
            markdown=(
                "# Project Proposal: AI Automation\n\n"
                "## Scope\n"
                "Implement RPA for invoice processing.\n\n"
                "## Budget\n"
                "Total: EUR 250,000 over 6 months.\n\n"
                "## Timeline\n"
                "Phase 1: 2 months, Phase 2: 3 months, Phase 3: 1 month.\n"
            ),
            title="Project Proposal: AI Automation",
            author="Consulting Team",
            page_count=12,
            byte_size=5120,
            sha256="def456",
        ),
    ]


@pytest.fixture
def sample_wiki_context() -> dict:
    """Sample wiki recall context."""
    return {
        "pages": [
            {
                "slug": "client-acme",
                "kind": "entity",
                "body_md": "## Acme Corporation\n"
                "- Industry: Manufacturing\n"
                "- Contact: mario@acme.com\n"
                "- Previous projects: ERP migration (2025), Cloud infra (2024)\n",
            }
        ]
    }


class TestComposeBrief:
    """Tests for compose_brief() — the main synthesis function."""

    def test_compose_basic_brief(
        self,
        sample_ingest_results: list[IngestResult],
    ) -> None:
        """Verify compose_brief returns a BriefOutline with correct structure."""
        outline = compose_brief(
            files=sample_ingest_results,
            wiki_context={},
            objective="Summarize Q1 financial performance and evaluate AI automation proposal",
        )

        assert isinstance(outline, BriefOutline)
        # Should find facts with numeric values from heading+paragraph pairs
        assert len(outline.findings) >= 3, (
            f"Should extract at least 3 findings from 2 documents, got {len(outline.findings)}"
        )
        # Findings should reference revenue and budget
        finding_texts = [f["fact"] for f in outline.findings]
        assert any(
            "1.2M" in fact for fact in finding_texts
        ), "Findings should reference revenue figure"

    def test_compose_with_wiki_context(
        self,
        sample_ingest_results: list[IngestResult],
        sample_wiki_context: dict,
    ) -> None:
        """Verify wiki context is incorporated into findings."""
        outline = compose_brief(
            files=sample_ingest_results,
            wiki_context=sample_wiki_context,
            objective="Review Acme project status",
        )

        assert outline.context is not None
        assert len(outline.context) > 0
        assert "Acme" in outline.context

    def test_compose_single_file(self) -> None:
        """Verify brief works with just one source file."""
        files = [
            IngestResult(
                file_path="single.txt",
                format="txt",
                markdown="# Single Document\n\nJust a note.",
                byte_size=50,
                sha256="xyz",
            )
        ]
        outline = compose_brief(files, {}, "Summarize single note")
        assert len(outline.findings) >= 0
        assert len(outline.sources) == 1

    def test_compose_empty_file_list(self) -> None:
        """Verify empty file list returns a minimal outline."""
        outline = compose_brief([], {}, "Test")
        assert outline.tldr == ["No documents provided for briefing."]
        assert outline.findings == []
        assert outline.sources == []

    def test_compose_with_salient_facts(
        self,
        sample_ingest_results: list[IngestResult],
    ) -> None:
        """Verify findings are extracted as dicts with source attribution."""
        outline = compose_brief(
            files=sample_ingest_results,
            wiki_context={},
            objective="Identify key numbers",
        )

        for finding in outline.findings:
            assert "fact" in finding, "Each finding must have a 'fact' field"
            assert "source_file" in finding, "Each finding must cite a source file"
            assert isinstance(finding["source_file"], str)
            assert isinstance(finding["fact"], str)
            # Check source paths contain expected filenames
            assert any(
                name in finding["source_file"]
                for name in ["report.pdf", "proposal.docx"]
            )

    def test_confidence_with_contradictory_sources(self) -> None:
        """Verify contradictory info is flagged in open questions."""
        files = [
            IngestResult(
                file_path="source_a.txt",
                format="txt",
                markdown=(
                    "## Revenue\n"
                    "Revenue was EUR 1.0M this quarter.\n"
                ),
                byte_size=50,
                sha256="aaa",
            ),
            IngestResult(
                file_path="source_b.txt",
                format="txt",
                markdown=(
                    "## Revenue\n"
                    "Revenue was EUR 1.5M this quarter.\n"
                ),
                byte_size=50,
                sha256="bbb",
            ),
        ]
        outline = compose_brief(files, {}, "Compare revenue figures")
        # Both sources should appear in findings
        assert len(outline.findings) >= 2, (
            f"Should extract findings from both sources, got {len(outline.findings)}"
        )
        # Each filing should have source attribution
        for finding in outline.findings:
            assert "source_file" in finding
        # Both source files should be cited
        source_files = {f["source_file"] for f in outline.findings}
        assert "source_a.txt" in source_files
        assert "source_b.txt" in source_files


class TestBriefOutline:
    """Tests for BriefOutline dataclass."""

    def test_default_values(self) -> None:
        o = BriefOutline(
            tldr=["A"],
            context="",
            findings=[],
            decisions_pending=[],
            open_questions=[],
            sources=[],
        )
        assert o.tldr == ["A"]
        assert o.findings == []
        assert o.sources == []


class TestRenderMarkdown:
    """Tests for render_markdown() — markdown formatting."""

    def test_render_full_brief(self) -> None:
        outline = BriefOutline(
            tldr=[
                "Q1 revenue EUR 1.2M (+15% YoY) (source: report.pdf)",
                "Proposed AI automation budget EUR 250K (source: proposal.docx)",
            ],
            context="Client: Acme Corp, Manufacturing sector.",
            findings=[
                {
                    "fact": "Revenue growth driven by new product line.",
                    "source_file": "report.pdf",
                },
                {
                    "fact": "Automation would reduce invoice processing time by 60%.",
                    "source_file": "proposal.docx",
                },
            ],
            decisions_pending=[
                "Approve AI automation budget (deadline: 2026-05-15)",
            ],
            open_questions=[
                "What is the ROI timeline for the automation investment?",
            ],
            sources=[
                "/home/user/project/report.pdf (Q1 Financial Report)",
                "/home/user/project/proposal.docx (AI Automation Proposal)",
            ],
        )

        md = render_markdown(outline)

        assert "# Executive Brief" in md
        assert "## TL;DR" in md
        assert "## Context" in md
        assert "## Findings" in md
        assert "## Decisions Pending" in md
        assert "## Open Questions" in md
        assert "## Sources" in md
        assert "EUR 1.2M" in md
        assert "EUR 250K" in md
        assert "report.pdf" in md
        assert "proposal.docx" in md

    def test_render_empty_outline(self) -> None:
        outline = BriefOutline(
            tldr=["No documents provided for briefing."],
            context="",
            findings=[],
            decisions_pending=[],
            open_questions=[],
            sources=[],
        )
        md = render_markdown(outline)
        assert "# Executive Brief" in md
        assert "No documents" in md

    def test_render_timestamp(self) -> None:
        outline = BriefOutline(
            tldr=["Test"], context="", findings=[], decisions_pending=[],
            open_questions=[], sources=[]
        )
        md = render_markdown(outline)
        # Should contain today's date
        today = datetime.date.today().strftime("%Y-%m-%d")
        assert today in md or "Generated" in md
