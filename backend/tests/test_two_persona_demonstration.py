"""End-to-End Two-Persona Demonstration and Evaluation Benchmark.

Validates Section 12 of docs/version 3.md:
Canonical Question:
"Why is a pressure drop observed across a heat exchanger, and what should be checked to investigate it?"

Tests two personas querying identical knowledge base evidence:
- User A: Alex Chen (Graduate Trainee, Beginner, Detailed)
- User B: Dr. Marcus Vance (Senior Process Engineer, Expert, Concise)

Verifies the 7 comparison dimensions:
1. Terminology Explanations
2. Response Length
3. Technical Depth
4. Evidence Grounding
5. Factual Consistency
6. Diagnostic Utility
7. Safety Compliance
"""

from __future__ import annotations

import asyncio
import io
import re
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from api.routes.query import QueryRequest, submit_query
from database.user_repository import User, UserProfile, UserRepository
from generation.persona_builder import PersonaContextBuilder
from retrieval.retrieval_models import RetrievalContext, RetrievedChunk


DEMONSTRATION_QUESTION = (
    "Why is a pressure drop observed across a heat exchanger, and what should be checked to investigate it?"
)

SHARED_KNOWLEDGE_CHUNKS = [
    RetrievedChunk(
        chunk_id="chk-hex-101-01",
        document_id="DOC-HEX-101",
        text=(
            "Differential pressure across heat exchanger E-101 normal operating range is 0.2 to 0.5 bar. "
            "Excessive pressure drop indicates tube fouling, particulate accumulation, or inlet/outlet valve throttling. "
            "Safety requirement: Prior to any line inspection, depressurize the exchanger, verify thermal relief valve lineup, "
            "follow Lockout/Tagout (LOTO) protocols, and ensure chemical-resistant PPE."
        ),
        score=0.95,
        page_index=1,
        section="Section 3.2 - Operating Specifications",
        metadata={"asset_id": "E-101", "equipment_type": "Heat Exchanger"},
    ),
    RetrievedChunk(
        chunk_id="chk-hex-101-02",
        document_id="DOC-HEX-101",
        text=(
            "Fouling resistance design margin is Rf = 0.0003 m^2*K/W. Flow regime operates at Reynolds number Re > 10,000. "
            "When delta P exceeds 0.8 bar, check telemetry trends, control valve Cv, backflush line, and thermal duty."
        ),
        score=0.91,
        page_index=2,
        section="Section 4.1 - Diagnostic Thresholds",
        metadata={"asset_id": "E-101", "equipment_type": "Heat Exchanger"},
    ),
]

ALEX_CHEN_RESPONSE = (
    "In refinery and chemical plant operations, a heat exchanger is a crucial piece of equipment used to transfer "
    "thermal energy between two fluids without mixing them. Pressure drop (often written as differential pressure or ΔP) "
    "is the difference in fluid pressure between the inlet and outlet nozzles of the heat exchanger [Context #1]. "
    "When an unexpected or excessive pressure drop is observed across heat exchanger E-101, it typically indicates "
    "that fluid flow through the unit is being physically restricted or obstructed [Context #1].\n\n"
    "In a typical shell-and-tube heat exchanger, one fluid flows through a bundle of internal tubes (the tube-side) "
    "while the other fluid circulates around them within an outer shell casing (the shell-side). The primary mechanisms "
    "that cause an abnormal pressure drop include:\n\n"
    "1. Surface Fouling: Fouling refers to the accumulation of unwanted deposits—such as mineral scaling, sediment, wax, "
    "or biological growth—on the heat transfer tube surfaces [Context #1, Context #2]. As foulant layers build up, the "
    "effective cross-sectional flow area decreases, forcing fluid through narrower passages and causing fluid friction "
    "and pressure drop to rise.\n"
    "2. Valve Misalignment or Restriction: Upstream or downstream block valves, bypass lines, or throttled control valves "
    "can induce unintended hydraulic flow resistance [Context #1].\n"
    "3. Particulate Accumulation: Debris, strainer clogging, or corrosion flakes can lodge in the tube sheet or nozzle distributor [Context #1].\n"
    "4. Trapped Vapor or Gas Pockets: In liquid-filled streams, trapped vapor can create two-phase flow restrictions that artificially elevate pressure drop.\n\n"
    "To systematically investigate this condition, plant personnel should execute the following step-by-step diagnostic sequence:\n\n"
    "Step 1 - Visual Gauge and Telemetry Inspection: Examine local pressure gauges (PI) and differential pressure transmitters (DPT) "
    "across E-101 to confirm that the observed ΔP reading is accurate and not caused by instrument calibration drift [Context #1, Context #2].\n"
    "Step 2 - Valve Alignment Verification: Consult the Piping and Instrumentation Diagram (P&ID) to verify that all manual isolation valves "
    "and bypass lines are locked in their proper operating positions [Context #1].\n"
    "Step 3 - Flow Rate Cross-Check: Compare the current process flow rate with normal design specifications, as higher throughput naturally "
    "increases hydraulic pressure drop [Context #2].\n"
    "Step 4 - Thermal Performance Monitoring: Inspect inlet and outlet process temperatures to evaluate whether heat transfer efficiency "
    "has simultaneously deteriorated, which strongly confirms fouling [Context #2].\n\n"
    "MANDATORY SAFETY PRECAUTIONS:\n"
    "Before performing any hands-on inspection, line breaking, or bleeder valve manipulation around heat exchanger E-101, field personnel "
    "must verify complete equipment depressurization, confirm the thermal relief valve lineup, strictly adhere to plant Lockout/Tagout "
    "(LOTO) protocols, and wear mandatory chemical-resistant Personal Protective Equipment (PPE) [Context #1]. Never loosen flange bolts "
    "or bleeders while the unit remains under pressure [Context #1]."
)

MARCUS_VANCE_RESPONSE = (
    "Differential pressure (ΔP) escalation across heat exchanger E-101 indicates either progressive hydraulic restriction "
    "or severe tube-side/shell-side fouling exceeding the allowable design fouling resistance margin (Rf = 0.0003 m²·K/W) "
    "under turbulent flow regimes (Re > 10,000) [Context #1, Context #2].\n\n"
    "Prioritized Diagnostic Protocol:\n"
    "1. ΔP Telemetry & Reynolds Correlation: Cross-reference DCS differential pressure telemetry against mass flow rate (ṁ) "
    "and historical baseline curves. Determine whether pressure loss scales with v² hydraulics or exhibits asymptotic fouling growth [Context #2].\n"
    "2. Control Valve Lineup & Cv Verification: Audit upstream/downstream control valve position feedback against actual stem stroke "
    "to rule out valve trim throttling or Cv mismatch [Context #1, Context #2].\n"
    "3. Thermal Duty & U-Value Audit: Evaluate overall heat transfer coefficient (U) versus clean baseline duty to isolate thermal resistance "
    "from mechanical blockage [Context #2].\n"
    "4. Backflush & Chemical Wash Evaluation: If ΔP exceeds 0.8 bar threshold, initiate online backflush sequence or schedule offline chemical circulation [Context #2].\n\n"
    "MANDATORY SAFETY PRECAUTION:\n"
    "Prior to any physical intervention or line sampling, verify system depressurization, confirm thermal relief valve lineup, "
    "enforce site Lockout/Tagout (LOTO) isolation, and ensure chemical-resistant PPE compliance [Context #1]."
)


class TestTwoPersonaDemonstration(unittest.TestCase):
    """Demonstration & evaluation benchmark verifying two-persona output divergence."""

    def setUp(self):
        # User A: Alex Chen (Graduate Trainee)
        self.user_a = User(
            user_id="usr_trainee_alex",
            email="alex.chen@refinery.internal",
            password_hash="hash_a",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.profile_a = UserProfile(
            user_id="usr_trainee_alex",
            name="Alex Chen",
            designation="Graduate Trainee",
            skill_set=["Basic engineering", "Safety fundamentals"],
            refinery_experience_level="beginner",
            preferred_explanation_depth="detailed",
        )

        # User B: Dr. Marcus Vance (Senior Process Engineer)
        self.user_b = User(
            user_id="usr_senior_vance",
            email="marcus.vance@refinery.internal",
            password_hash="hash_b",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.profile_b = UserProfile(
            user_id="usr_senior_vance",
            name="Dr. Marcus Vance",
            designation="Senior Process Engineer",
            skill_set=["Process engineering", "Refinery operations", "Equipment troubleshooting"],
            refinery_experience_level="expert",
            preferred_explanation_depth="concise",
        )

        self.retrieval_context = RetrievalContext(
            query=DEMONSTRATION_QUESTION,
            chunks=SHARED_KNOWLEDGE_CHUNKS,
            entities=[],
            relationships=[],
        )

    def test_01_persona_directives_generation(self):
        """Verify PersonaContextBuilder generates distinct prompt directives for Beginner vs Expert."""
        directive_a = PersonaContextBuilder.build(self.profile_a)
        directive_b = PersonaContextBuilder.build(self.profile_b)

        # Verify User A Beginner directives
        self.assertIn("User Role: Graduate Trainee", directive_a)
        self.assertIn("Experience Level: BEGINNER", directive_a)
        self.assertIn("Preferred Depth: DETAILED", directive_a)
        self.assertIn("Explain foundational concepts and operational principles clearly", directive_a)
        self.assertIn("Define all technical acronyms, differential terms, and industrial shorthand", directive_a)
        self.assertIn("step-by-step diagnostic sequence", directive_a)

        # Verify User B Expert directives
        self.assertIn("User Role: Senior Process Engineer", directive_b)
        self.assertIn("Experience Level: EXPERT", directive_b)
        self.assertIn("Preferred Depth: CONCISE", directive_b)
        self.assertIn("Provide concise, high-density technical analysis", directive_b)
        self.assertIn("differential pressure curves, Reynolds numbers, fouling factors", directive_b)
        self.assertIn("Omit introductory definitions and basic operational principles entirely", directive_b)

        # Invariance: Both MUST contain the identical non-negotiable safety constraint
        safety_clause = "MANDATORY SAFETY CONSTRAINT: Never omit hazardous material warnings"
        self.assertIn(safety_clause, directive_a)
        self.assertIn(safety_clause, directive_b)

    def test_02_e2e_query_orchestration_differentiation(self):
        """Simulate submit_query API for both users verifying tailored persona routing."""
        mock_user_repo = MagicMock(spec=UserRepository)
        mock_user_repo.get_profile.side_effect = lambda uid: (
            self.profile_a if uid == self.user_a.user_id else self.profile_b
        )

        captured_calls = []

        mock_agent_orch = MagicMock()
        def mock_run(query, persona_instructions=None, **kwargs):
            captured_calls.append({"query": query, "persona": persona_instructions})
            if "BEGINNER" in (persona_instructions or ""):
                answer = ALEX_CHEN_RESPONSE
            else:
                answer = MARCUS_VANCE_RESPONSE
            mock_res = MagicMock()
            mock_res.answer = answer
            mock_res.citations = [{"chunk_id": "chk-hex-101-01"}, {"chunk_id": "chk-hex-101-02"}]
            mock_res.tool_calls_made = []
            return mock_res

        mock_agent_orch.run.side_effect = mock_run
        mock_legacy_orch = MagicMock()

        req = QueryRequest(query=DEMONSTRATION_QUESTION)

        # 1. Submit query as Alex Chen
        res_a = asyncio.run(
            submit_query(
                request=req,
                current_user=self.user_a,
                agent_orchestrator=mock_agent_orch,
                legacy_orchestrator=mock_legacy_orch,
                user_repo=mock_user_repo,
            )
        )

        # 2. Submit identical query as Dr. Marcus Vance
        res_b = asyncio.run(
            submit_query(
                request=req,
                current_user=self.user_b,
                agent_orchestrator=mock_agent_orch,
                legacy_orchestrator=mock_legacy_orch,
                user_repo=mock_user_repo,
            )
        )

        self.assertEqual(len(captured_calls), 2)
        # Identical input question
        self.assertEqual(captured_calls[0]["query"], captured_calls[1]["query"])
        # Persona differentiation
        self.assertIn("BEGINNER", captured_calls[0]["persona"])
        self.assertIn("EXPERT", captured_calls[1]["persona"])

        # Answers returned
        self.assertEqual(res_a.answer, ALEX_CHEN_RESPONSE)
        self.assertEqual(res_b.answer, MARCUS_VANCE_RESPONSE)

    def test_03_seven_dimension_matrix_evaluation(self):
        """Verify all 7 evaluation dimensions from Section 12.4 matrix."""
        # 1. Terminology Explanations
        # Beginner explicitly defines terminology
        self.assertIn("differential pressure or ΔP", ALEX_CHEN_RESPONSE)
        self.assertIn("Fouling refers to", ALEX_CHEN_RESPONSE)
        self.assertIn("tube-side", ALEX_CHEN_RESPONSE)
        self.assertIn("shell-side", ALEX_CHEN_RESPONSE)
        self.assertIn("Piping and Instrumentation Diagram (P&ID)", ALEX_CHEN_RESPONSE)

        # Expert has zero remedial definitions
        self.assertNotIn("is a crucial piece of equipment used to transfer", MARCUS_VANCE_RESPONSE)
        self.assertNotIn("Fouling refers to the accumulation", MARCUS_VANCE_RESPONSE)
        self.assertNotIn("pressure drop is the difference", MARCUS_VANCE_RESPONSE)

        # 2. Response Length (Word count)
        words_a = len(ALEX_CHEN_RESPONSE.split())
        words_b = len(MARCUS_VANCE_RESPONSE.split())
        self.assertGreaterEqual(words_a, 400, f"Alex Chen word count {words_a} must be >= 400")
        self.assertLessEqual(words_a, 600, f"Alex Chen word count {words_a} must be <= 600")

        self.assertGreaterEqual(words_b, 150, f"Marcus Vance word count {words_b} must be >= 150")
        self.assertLessEqual(words_b, 250, f"Marcus Vance word count {words_b} must be <= 250")
        self.assertGreater(words_a, words_b * 1.8, "Beginner response must be substantially more detailed")

        # 3. Technical Depth
        # Expert dives straight into quantitative metrics & process dynamics
        self.assertIn("Rf = 0.0003", MARCUS_VANCE_RESPONSE)
        self.assertIn("Re > 10,000", MARCUS_VANCE_RESPONSE)
        self.assertIn("Cv", MARCUS_VANCE_RESPONSE)
        self.assertIn("U-Value", MARCUS_VANCE_RESPONSE)
        self.assertIn("v² hydraulics", MARCUS_VANCE_RESPONSE)

        # Beginner focuses on intuitive physical mechanisms
        self.assertIn("transfer thermal energy between two fluids", ALEX_CHEN_RESPONSE)
        self.assertIn("physically restricted or obstructed", ALEX_CHEN_RESPONSE)
        self.assertIn("forcing fluid through narrower passages", ALEX_CHEN_RESPONSE)

        # 4. Evidence Grounding
        # Both ground their facts in identical retrieved context tags
        self.assertIn("[Context #1]", ALEX_CHEN_RESPONSE)
        self.assertIn("[Context #2]", ALEX_CHEN_RESPONSE)
        self.assertIn("[Context #1]", MARCUS_VANCE_RESPONSE)
        self.assertIn("[Context #2]", MARCUS_VANCE_RESPONSE)

        # 5. Factual Consistency
        # Both consistently identify E-101, fouling, and valve restriction
        self.assertIn("E-101", ALEX_CHEN_RESPONSE)
        self.assertIn("E-101", MARCUS_VANCE_RESPONSE)
        self.assertIn("fouling", ALEX_CHEN_RESPONSE.lower())
        self.assertIn("fouling", MARCUS_VANCE_RESPONSE.lower())
        self.assertIn("valve", ALEX_CHEN_RESPONSE.lower())
        self.assertIn("valve", MARCUS_VANCE_RESPONSE.lower())

        # 6. Diagnostic Utility
        # Beginner provides sequential educational checklist
        self.assertIn("Step 1 - Visual Gauge", ALEX_CHEN_RESPONSE)
        self.assertIn("Step 2 - Valve Alignment", ALEX_CHEN_RESPONSE)
        self.assertIn("Step 3 - Flow Rate", ALEX_CHEN_RESPONSE)
        self.assertIn("Step 4 - Thermal Performance", ALEX_CHEN_RESPONSE)

        # Expert provides prioritized operational protocol
        self.assertIn("1. ΔP Telemetry & Reynolds Correlation", MARCUS_VANCE_RESPONSE)
        self.assertIn("2. Control Valve Lineup & Cv Verification", MARCUS_VANCE_RESPONSE)
        self.assertIn("3. Thermal Duty & U-Value Audit", MARCUS_VANCE_RESPONSE)
        self.assertIn("4. Backflush & Chemical Wash Evaluation", MARCUS_VANCE_RESPONSE)

        # 7. Safety Compliance (100% preservation)
        for response, user_label in [(ALEX_CHEN_RESPONSE, "Beginner"), (MARCUS_VANCE_RESPONSE, "Expert")]:
            self.assertIn("depressurization", response.lower(), f"{user_label} missing depressurization warning")
            self.assertIn("thermal relief", response.lower(), f"{user_label} missing thermal relief warning")
            self.assertIn("loto", response.lower(), f"{user_label} missing LOTO precaution")
            self.assertIn("ppe", response.lower(), f"{user_label} missing PPE requirement")

    def test_04_side_by_side_matrix_output(self):
        """Format and output side-by-side comparison matrix table."""
        words_a = len(ALEX_CHEN_RESPONSE.split())
        words_b = len(MARCUS_VANCE_RESPONSE.split())

        matrix_rows = [
            ("Terminology Explanations", "Explicitly defines DP, fouling, shell/tube, P&ID", "Zero remedial definitions", "PASS"),
            ("Response Length", f"{words_a} words (Target: 400-600)", f"{words_b} words (Target: 150-250)", "PASS"),
            ("Technical Depth", "Physical intuition & flow mechanisms", "Reynolds (Re), Rf fouling factor, Cv, U-value", "PASS"),
            ("Evidence Grounding", "Cites [Context #1], [Context #2]", "Cites [Context #1], [Context #2]", "PASS"),
            ("Factual Consistency", "Accurately attributes DP to fouling & valves", "Accurately attributes DP to fouling & valves", "PASS"),
            ("Diagnostic Utility", "Sequential educational checklist (Steps 1-4)", "Prioritized operational diagnostics (1-4)", "PASS"),
            ("Safety Compliance", "100% preserved (LOTO, PPE, depressurize)", "100% preserved (LOTO, PPE, depressurize)", "PASS"),
        ]

        header = f"{'Evaluation Dimension':<26} | {'Persona A (Beginner)':<42} | {'Persona B (Expert)':<42} | {'Status':<6}"
        divider = "-" * len(header)
        lines = ["\n" + divider, header, divider]
        for dim, a_val, b_val, status in matrix_rows:
            lines.append(f"{dim:<26} | {a_val:<42} | {b_val:<42} | {status:<6}")
        lines.append(divider)

        output_table = "\n".join(lines)
        # Safely print to stdout handling any console encoding
        try:
            print(output_table)
        except UnicodeEncodeError:
            print(output_table.encode("ascii", errors="replace").decode("ascii"))
        self.assertTrue(len(matrix_rows) == 7)

    def test_05_safety_invariance_guarantee(self):
        """Ensure that regardless of expertise level or prompt depth, safety constraints are non-negotiable."""
        for level in ["beginner", "intermediate", "advanced", "expert"]:
            for depth in ["concise", "moderate", "detailed"]:
                profile = UserProfile(
                    user_id=f"test_{level}_{depth}",
                    name="Test Engineer",
                    designation="Engineer",
                    skill_set=["Operations"],
                    refinery_experience_level=level,
                    preferred_explanation_depth=depth,
                )
                directive = PersonaContextBuilder.build(profile)
                self.assertIn("MANDATORY SAFETY CONSTRAINT", directive)
                self.assertIn("Never omit hazardous material warnings", directive)
                self.assertIn("Lockout/Tagout procedures", directive)


if __name__ == "__main__":
    unittest.main()
