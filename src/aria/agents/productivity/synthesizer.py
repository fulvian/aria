"""Consultancy-brief synthesizer — multi-document executive summaries.

Composes structured brief outlines (TL;DR, Context, Findings, Decisions,
Open Questions, Sources) from multiple ingested documents and optional
wiki context.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aria.agents.productivity.ingest import IngestResult

logger = logging.getLogger(__name__)


@dataclass
class BriefOutline:
    """Structured outline for a consultancy brief."""

    tldr: list[str]
    context: str
    findings: list[dict[str, str]]
    decisions_pending: list[str]
    open_questions: list[str]
    sources: list[str]


def compose_brief(
    files: list[IngestResult],
    wiki_context: dict[str, Any],
    objective: str,
) -> BriefOutline:
    """Compose a structured brief outline from ingested documents + wiki context.

    This is a deterministic, rule-based synthesis function. It extracts
    salient facts, identifies contradictions, and structures them into
    the :class:`BriefOutline` format. The actual prose composition is
    intended for an LLM agent using this outline as a scaffold; this
    function provides the structured data layer.

    Args:
        files: List of :class:`IngestResult` from office-ingest.
        wiki_context: Dict with ``pages`` key containing wiki recall results.
        objective: User's stated objective for the brief.

    Returns:
        A :class:`BriefOutline` with extracted and organized information.
    """
    if not files:
        return BriefOutline(
            tldr=["No documents provided for briefing."],
            context="",
            findings=[],
            decisions_pending=[],
            open_questions=[],
            sources=[],
        )

    # Build sources list
    sources = [_format_source(f) for f in files]

    # Extract context from wiki
    context_parts = _extract_wiki_context(wiki_context)

    # Extract findings from documents (simple heuristic: grab headings + paragraphs)
    findings: list[dict[str, str]] = []
    all_bullets: list[str] = []
    decisions: list[str] = []
    questions: list[str] = []

    for f in files:
        doc_facts, doc_bullets = _extract_facts_from_markdown(f.markdown, f.file_path)
        findings.extend(doc_facts)
        all_bullets.extend(doc_bullets)

        # Extract decisions and questions from markdown content
        decisions.extend(_extract_lines_marked(f.markdown, ["decision", "pending", "approv"]))
        questions.extend(_extract_lines_marked(f.markdown, ["question", "?", "open"]))

    # Detect contradictions in numeric data
    contradictions = _detect_contradictions(findings)
    if contradictions:
        for c in contradictions:
            questions.append(f"Contradictory data detected: {c}")

    # Build TL;DR from key facts (top 5 bullets max)
    tldr = (
        all_bullets[:5]
        if all_bullets
        else [f"{len(files)} document(s) analyzed. See findings for details."]
    )

    # Build context string
    context = _build_context_string(context_parts, files, objective)

    # Remove duplicate findings
    seen_facts: set[str] = set()
    unique_findings: list[dict[str, str]] = []
    for finding in findings:
        fact_key = finding.get("fact", "")[:80]
        if fact_key and fact_key not in seen_facts:
            seen_facts.add(fact_key)
            unique_findings.append(finding)

    return BriefOutline(
        tldr=tldr,
        context=context,
        findings=unique_findings,
        decisions_pending=decisions,
        open_questions=questions,
        sources=sources,
    )


def render_markdown(outline: BriefOutline) -> str:
    """Render a BriefOutline to a formatted markdown string.

    Args:
        outline: The brief outline to render.

    Returns:
        A markdown string with sections: Executive Brief, TL;DR, Context,
        Findings, Decisions Pending, Open Questions, Sources.
    """
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# Executive Brief",
        "",
        f"*Generated: {now}*",
        "",
        "---",
        "",
        "## TL;DR",
        "",
    ]
    for bullet in outline.tldr:
        lines.append(f"- {bullet}")
    lines.append("")

    if outline.context:
        lines.extend(["## Context", "", outline.context, ""])

    if outline.findings:
        lines.append("## Findings")
        lines.append("")
        for finding in outline.findings:
            fact = finding.get("fact", "")
            source = finding.get("source_file", "")
            if source:
                lines.append(f"- {fact} *(source: {source})*")
            else:
                lines.append(f"- {fact}")
        lines.append("")

    if outline.decisions_pending:
        lines.append("## Decisions Pending")
        lines.append("")
        for d in outline.decisions_pending:
            lines.append(f"- {d}")
        lines.append("")

    if outline.open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for q in outline.open_questions:
            lines.append(f"- {q}")
        lines.append("")

    lines.append("## Sources")
    lines.append("")
    for s in outline.sources:
        lines.append(f"- {s}")
    lines.append("")

    return "\n".join(lines)


def _format_source(f: IngestResult) -> str:
    """Format a source citation string for an IngestResult."""
    title_part = f" ({f.title})" if f.title else ""
    return f"{f.file_path}{title_part}"


def _extract_wiki_context(wiki_context: dict) -> list[str]:
    """Extract relevant context strings from wiki recall results."""
    parts: list[str] = []
    pages = wiki_context.get("pages", [])
    for page in pages:
        body = page.get("body_md", "")
        if body:
            # Extract first meaningful line
            for line in body.split("\n"):
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                    parts.append(stripped)
                    break
    return parts


def _extract_facts_from_markdown(
    markdown: str, file_path: str
) -> tuple[list[dict[str, str]], list[str]]:
    """Extract findings and bullet points from markdown content.

    Returns:
        Tuple of (findings list, bullet point list).
    """
    findings: list[dict[str, str]] = []
    bullets: list[str] = []

    lines = markdown.split("\n")
    current_heading: str | None = None

    for line in lines:
        stripped = line.strip()

        # Track heading context
        if stripped.startswith("## "):
            current_heading = stripped[3:].strip()
        elif stripped.startswith("# "):
            current_heading = stripped[2:].strip()

        # Extract list items
        if stripped.startswith(("- ", "* ")):
            item = stripped[2:].strip()
            if item and len(item) > 10:  # Skip very short items
                bullets.append(f"{item} ({Path(file_path).name})")
                findings.append(
                    {
                        "fact": item,
                        "source_file": file_path,
                        "context": current_heading or "",
                    }
                )

        # Extract sentences with numbers (potential key facts)
        elif any(c.isdigit() for c in stripped) and len(stripped) > 20:
            if not stripped.startswith("#") and not stripped.startswith("|"):
                findings.append(
                    {
                        "fact": stripped,
                        "source_file": file_path,
                        "context": current_heading or "",
                    }
                )

    return findings, bullets


def _extract_lines_marked(markdown: str, keywords: list[str]) -> list[str]:
    """Extract lines containing any of the given keywords."""
    results: list[str] = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "|")):
            continue
        if any(kw.lower() in stripped.lower() for kw in keywords):
            results.append(stripped)
    return results


def _detect_contradictions(findings: list[dict[str, str]]) -> list[str]:
    """Simple heuristic contradiction detection on numeric facts.

    Looks for facts mentioning the same metric with different numeric values.
    This is a basic heuristic; complex contradiction detection is left to LLM.
    """
    # Simple implementation: group by context and look for different numbers
    # in the same context with similar wording
    contradictions: list[str] = []
    seen_metrics: dict[str, list[str]] = {}

    for finding in findings:
        fact = finding.get("fact", "")
        context = finding.get("context", "")
        if context:
            key = context.lower().strip()
            if key not in seen_metrics:
                seen_metrics[key] = []
            seen_metrics[key].append(fact)

    # Check for contradictions within same context (simplified)
    for context, facts in seen_metrics.items():
        if len(facts) >= 2:
            # Check if they reference different numbers for what seems same metric
            # Just flag it; full analysis done by LLM
            contradictions.append(f"Multiple values in '{context}' — see findings for details.")

    # Deduplicate
    return list(set(contradictions))


def _build_context_string(
    context_parts: list[str],
    files: list[IngestResult],
    objective: str,
) -> str:
    """Build the context section string."""
    parts: list[str] = []

    if objective:
        parts.append(f"**Objective**: {objective}")
        parts.append("")

    if context_parts:
        parts.append("**Wiki context**:")
        for p in context_parts:
            parts.append(f"- {p}")
        parts.append("")

    parts.append(f"**Documents analyzed**: {len(files)}")

    return "\n".join(parts)


# Import Path for _extract_facts_from_markdown
from pathlib import Path  # noqa: E402
