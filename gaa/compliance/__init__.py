"""
Compliance Layer - Safety Cases and EDR Patterns

Implements compliance frameworks for autonomous systems:
- UL 4600 safety case structure
- ISO 26262 traceability
- EDR (Event Data Recorder) pattern for geometric data

Key Components:
- SafetyCase: Claim-Argument-Evidence structure
- EDRCapture: Essential geometric data recording
- TraceabilityMatrix: Requirements linkage
- ComplianceReport: Audit-ready documentation

Based on:
- UL 4600 "Standard for Evaluation of Autonomous Products"
- ISO 26262 "Functional Safety for Road Vehicles"
- EU EDR Regulation (2019/2144)
"""

from .safety_case import SafetyCase, Claim, Argument, Evidence
from .edr import EDRCapture, EDRFrame, EDRExport
from .traceability import TraceabilityMatrix, Requirement, Implementation
from .report import ComplianceReport, ReportSection

__all__ = [
    "SafetyCase",
    "Claim",
    "Argument",
    "Evidence",
    "EDRCapture",
    "EDRFrame",
    "EDRExport",
    "TraceabilityMatrix",
    "Requirement",
    "Implementation",
    "ComplianceReport",
    "ReportSection",
]
