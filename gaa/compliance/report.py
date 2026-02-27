"""
Compliance Report Generation

Generates audit-ready documentation combining
safety cases, traceability, and EDR data.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from .safety_case import SafetyCase
from .traceability import TraceabilityMatrix
from .edr import EDRExport


@dataclass
class ReportSection:
    """Section of compliance report."""

    section_id: str
    title: str
    content: str = ""
    subsections: List['ReportSection'] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content": self.content,
            "subsections": [s.to_dict() for s in self.subsections],
            "data": self.data,
        }

    def to_markdown(self, level: int = 1) -> str:
        """Convert to markdown format."""
        md = "#" * level + " " + self.title + "\n\n"
        if self.content:
            md += self.content + "\n\n"

        if self.data:
            md += "```json\n"
            md += json.dumps(self.data, indent=2)
            md += "\n```\n\n"

        for sub in self.subsections:
            md += sub.to_markdown(level + 1)

        return md


class ComplianceReport:
    """
    Complete compliance report generator.

    Combines safety case, traceability matrix, and EDR data
    into a comprehensive audit-ready document.
    """

    def __init__(
        self,
        report_id: str,
        title: str,
        project: str = ""
    ):
        self.report_id = report_id
        self.title = title
        self.project = project
        self.created = datetime.utcnow().timestamp()
        self.version = "1.0.0"

        self.sections: List[ReportSection] = []
        self.safety_case: Optional[SafetyCase] = None
        self.traceability: Optional[TraceabilityMatrix] = None
        self.edr_exports: List[EDRExport] = []

    def set_safety_case(self, safety_case: SafetyCase) -> None:
        """Set the safety case to include."""
        self.safety_case = safety_case

    def set_traceability(self, matrix: TraceabilityMatrix) -> None:
        """Set the traceability matrix to include."""
        self.traceability = matrix

    def add_edr_export(self, export: EDRExport) -> None:
        """Add an EDR export to the report."""
        self.edr_exports.append(export)

    def add_section(self, section: ReportSection) -> None:
        """Add a custom section."""
        self.sections.append(section)

    def generate_executive_summary(self) -> ReportSection:
        """Generate executive summary section."""
        content = f"""
This compliance report documents the safety assurance of the Geometric Audit
Architecture (GAA) system for project {self.project}.

Report ID: {self.report_id}
Generated: {datetime.fromtimestamp(self.created).isoformat()}
Version: {self.version}
"""

        data = {
            "report_id": self.report_id,
            "project": self.project,
            "generated": self.created,
        }

        if self.safety_case:
            data["safety_case_coverage"] = self.safety_case.compute_coverage()

        if self.traceability:
            data["requirements_coverage"] = self.traceability.compute_coverage()

        return ReportSection(
            section_id="1",
            title="Executive Summary",
            content=content.strip(),
            data=data,
        )

    def generate_safety_case_section(self) -> Optional[ReportSection]:
        """Generate safety case section."""
        if not self.safety_case:
            return None

        section = ReportSection(
            section_id="2",
            title="Safety Case",
            content=f"Safety case: {self.safety_case.title}",
            data=self.safety_case.to_dict(),
        )

        # Add subsections for claims
        for i, claim_id in enumerate(self.safety_case.top_level_claims):
            claim = self.safety_case.claims.get(claim_id)
            if claim:
                subsection = ReportSection(
                    section_id=f"2.{i+1}",
                    title=f"Claim: {claim.statement}",
                    content=claim.description,
                    data=claim.to_dict(),
                )
                section.subsections.append(subsection)

        return section

    def generate_traceability_section(self) -> Optional[ReportSection]:
        """Generate traceability section."""
        if not self.traceability:
            return None

        coverage = self.traceability.compute_coverage()

        section = ReportSection(
            section_id="3",
            title="Requirements Traceability",
            content=f"""
Requirements coverage analysis:
- Implementation coverage: {coverage['implementation_coverage']:.1%}
- Test coverage: {coverage['test_coverage']:.1%}
- Verification coverage: {coverage['verification_coverage']:.1%}
""",
            data=self.traceability.to_dict(),
        )

        # Add gap analysis subsection
        gaps = {
            "unimplemented": self.traceability.get_unimplemented_requirements(),
            "untested": self.traceability.get_untested_requirements(),
        }

        if any(gaps.values()):
            gap_section = ReportSection(
                section_id="3.1",
                title="Gap Analysis",
                content="The following gaps were identified:",
                data=gaps,
            )
            section.subsections.append(gap_section)

        return section

    def generate_edr_section(self) -> Optional[ReportSection]:
        """Generate EDR data section."""
        if not self.edr_exports:
            return None

        section = ReportSection(
            section_id="4",
            title="Event Data Records",
            content=f"{len(self.edr_exports)} event(s) recorded.",
        )

        for i, export in enumerate(self.edr_exports):
            subsection = ReportSection(
                section_id=f"4.{i+1}",
                title=f"Event: {export.trigger_event}",
                content=f"Trigger time: {datetime.fromtimestamp(export.trigger_time).isoformat()}",
                data=export.to_dict(),
            )
            section.subsections.append(subsection)

        return section

    def generate(self) -> List[ReportSection]:
        """Generate complete report."""
        self.sections = []

        # Executive summary
        self.sections.append(self.generate_executive_summary())

        # Safety case
        safety_section = self.generate_safety_case_section()
        if safety_section:
            self.sections.append(safety_section)

        # Traceability
        trace_section = self.generate_traceability_section()
        if trace_section:
            self.sections.append(trace_section)

        # EDR data
        edr_section = self.generate_edr_section()
        if edr_section:
            self.sections.append(edr_section)

        return self.sections

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "title": self.title,
            "project": self.project,
            "version": self.version,
            "created": self.created,
            "sections": [s.to_dict() for s in self.sections],
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        """Generate markdown report."""
        md = f"# {self.title}\n\n"
        md += f"**Report ID:** {self.report_id}\n"
        md += f"**Project:** {self.project}\n"
        md += f"**Version:** {self.version}\n"
        md += f"**Generated:** {datetime.fromtimestamp(self.created).isoformat()}\n\n"
        md += "---\n\n"

        for section in self.sections:
            md += section.to_markdown()

        return md
