"""Unit tests for IntentInterpreter and ParsedIntent (V4 Feature A)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from agents.intent_interpreter import (
    DeliverableFormat,
    IntentInterpreter,
    ParsedIntent,
    TaskType,
)


class TestIntentInterpreter(unittest.TestCase):
    """Test suite for LLM-driven intent interpretation and deterministic fallbacks."""

    def setUp(self) -> None:
        self.interpreter = IntentInterpreter(llm_provider=None)

    def test_permit_intent_varied_phrasing(self) -> None:
        """Verify varied wording for work permits maps accurately to PERMIT_GENERATION."""
        queries = [
            "Prepare a permit for maintenance on this pump P-101",
            "We need to isolate this equipment before inspection. Draft the required documentation for P-204.",
            "Generate a document that our safety officer can review before maintenance begins on E-102.",
            "Draft a hot work permit for welding on tank TK-500",
            "Please create a confined space permit for vessel V-301 entry",
        ]

        for q in queries:
            with self.subTest(query=q):
                intent = self.interpreter.interpret(q)
                self.assertEqual(intent.task_type, TaskType.PERMIT_GENERATION)
                self.assertTrue(intent.safety_critical)
                self.assertIn("search_documents", intent.required_tools)
                self.assertTrue(len(intent.target_equipment) > 0)
                self.assertTrue(len(intent.recommended_steps) >= 3)

    def test_permit_missing_equipment_detected(self) -> None:
        """Verify requesting a permit without specifying equipment flags missing information."""
        intent = self.interpreter.interpret("Prepare a work permit for maintenance tomorrow.")
        self.assertEqual(intent.task_type, TaskType.PERMIT_GENERATION)
        self.assertIn("target_equipment_tag", intent.missing_information)

    def test_document_generation_formats(self) -> None:
        """Verify document generation accurately identifies output deliverable formats."""
        # Word
        intent_docx = self.interpreter.interpret("Draft a word document report summarizing refinery maintenance.")
        self.assertEqual(intent_docx.task_type, TaskType.DOCUMENT_GENERATION)
        self.assertEqual(intent_docx.target_deliverable, DeliverableFormat.DOCX)

        # PDF
        intent_pdf = self.interpreter.interpret("Export a PDF report of inspection findings for P-101.")
        self.assertEqual(intent_pdf.task_type, TaskType.DOCUMENT_GENERATION)
        self.assertEqual(intent_pdf.target_deliverable, DeliverableFormat.PDF)

        # PPTX
        intent_pptx = self.interpreter.interpret("Create a presentation slide deck for the turnaround meeting.")
        self.assertEqual(intent_pptx.task_type, TaskType.DOCUMENT_GENERATION)
        self.assertEqual(intent_pptx.target_deliverable, DeliverableFormat.PPTX)

    def test_calculation_intent(self) -> None:
        """Verify mathematical and engineering calculation queries map to CALCULATION."""
        intent = self.interpreter.interpret("Calculate the pressure drop across valve V-102 with flow 45 m3/h")
        self.assertEqual(intent.task_type, TaskType.CALCULATION)
        self.assertIn("calculate", intent.required_tools)
        self.assertIn("V-102", intent.target_equipment)

    def test_image_analysis_intent(self) -> None:
        """Verify P&ID and diagram queries map to IMAGE_ANALYSIS."""
        intent = self.interpreter.interpret("Inspect this P&ID diagram and identify all bypass lines.")
        self.assertEqual(intent.task_type, TaskType.IMAGE_ANALYSIS)
        self.assertIn("analyze_pid", intent.required_tools)

    def test_system_status_intent(self) -> None:
        """Verify health check query maps to SYSTEM_STATUS."""
        intent = self.interpreter.interpret("What is the current system status?")
        self.assertEqual(intent.task_type, TaskType.SYSTEM_STATUS)
        self.assertIn("system_status", intent.required_tools)

    def test_empty_query_fallback(self) -> None:
        """Verify empty query returns safe fallback with zero confidence."""
        intent = self.interpreter.interpret("")
        self.assertEqual(intent.task_type, TaskType.QUESTION_ANSWER)
        self.assertEqual(intent.confidence, 0.0)

    def test_llm_provider_success(self) -> None:
        """Verify provider invocation parses JSON and maps to ParsedIntent."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "task_type": "permit_generation",
            "target_deliverable": "docx",
            "primary_objective": "Draft Hot Work Permit for HEX-101",
            "target_equipment": ["HEX-101"],
            "required_tools": ["search_documents", "search_knowledge_graph"],
            "missing_information": [],
            "safety_critical": True,
            "constraints": ["Hot work safety standards require fire watch"],
            "confidence": 0.96,
            "recommended_steps": ["Check atmospheric LEL", "Verify fire watch"],
        })
        mock_provider.chat.return_value = mock_response

        interpreter = IntentInterpreter(llm_provider=mock_provider)
        intent = interpreter.interpret("We need to weld near HEX-101.")

        self.assertEqual(intent.task_type, TaskType.PERMIT_GENERATION)
        self.assertEqual(intent.target_deliverable, DeliverableFormat.DOCX)
        self.assertEqual(intent.target_equipment, ["HEX-101"])
        self.assertTrue(intent.safety_critical)
        self.assertEqual(intent.confidence, 0.96)
        self.assertIn("Check atmospheric LEL", intent.recommended_steps)

    def test_llm_provider_markdown_fence_handling(self) -> None:
        """Verify LLM output wrapped in markdown code fences is cleanly parsed."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            "```json\n"
            "{\n"
            '  "task_type": "document_generation",\n'
            '  "target_deliverable": "pdf",\n'
            '  "primary_objective": "Generate PDF compliance report",\n'
            '  "target_equipment": ["P-101A"],\n'
            '  "required_tools": ["search_documents"],\n'
            '  "missing_information": [],\n'
            '  "safety_critical": false,\n'
            '  "constraints": [],\n'
            '  "confidence": 0.94,\n'
            '  "recommended_steps": ["Gather data", "Build PDF"]\n'
            "}\n"
            "```"
        )
        mock_provider.chat.return_value = mock_response

        interpreter = IntentInterpreter(llm_provider=mock_provider)
        intent = interpreter.interpret("Create an audit report.")

        self.assertEqual(intent.task_type, TaskType.DOCUMENT_GENERATION)
        self.assertEqual(intent.target_deliverable, DeliverableFormat.PDF)

    def test_llm_provider_failure_falls_back_deterministically(self) -> None:
        """Verify that provider failure falls back safely to deterministic interpretation without raising."""
        mock_provider = MagicMock()
        mock_provider.chat.side_effect = RuntimeError("Ollama connection refused")

        interpreter = IntentInterpreter(llm_provider=mock_provider)
        intent = interpreter.interpret("Prepare a hot work permit for welding on tank TK-500")

        # Did not raise; returned valid deterministic intent
        self.assertEqual(intent.task_type, TaskType.PERMIT_GENERATION)
        self.assertEqual(intent.target_equipment, ["TK-500"])
        self.assertTrue(intent.safety_critical)

    def test_parsed_intent_to_dict(self) -> None:
        """Verify ParsedIntent.to_dict() serializes all fields for API metadata."""
        intent = ParsedIntent(
            task_type=TaskType.PERMIT_GENERATION,
            target_deliverable=DeliverableFormat.DOCX,
            primary_objective="Draft LOTO permit",
            target_equipment=["P-101"],
            required_tools=["search_documents"],
            missing_information=["breaker_id"],
            safety_critical=True,
            constraints=["LOTO required"],
            confidence=0.95,
            recommended_steps=["Isolate breaker"],
        )
        d = intent.to_dict()
        self.assertEqual(d["task_type"], "permit_generation")
        self.assertEqual(d["target_deliverable"], "docx")
        self.assertEqual(d["target_equipment"], ["P-101"])
        self.assertEqual(d["missing_information"], ["breaker_id"])
        self.assertTrue(d["safety_critical"])

    def test_conversational_phrasing_document_generation(self) -> None:
        """Verify varied natural language expressions for document creation map to DOCUMENT_GENERATION."""
        queries = [
            "document generation is needed for this equipment",
            "we need a document generated summarizing pump maintenance",
            "generate handover notes for the incoming shift",
            "compile handover notes for the next shift",
            "create an sop document for isolation",
        ]
        for q in queries:
            with self.subTest(query=q):
                intent = self.interpreter.interpret(q)
                self.assertEqual(intent.task_type, TaskType.DOCUMENT_GENERATION)

    def test_llm_provider_receives_conversation_history(self) -> None:
        """Verify recent conversation history is passed into the LLM system prompt context."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "task_type": "document_generation",
            "target_deliverable": "docx",
            "primary_objective": "Generate handover notes based on previous inspection",
            "target_equipment": ["P-101A"],
            "required_tools": ["search_documents"],
            "missing_information": [],
            "safety_critical": False,
            "constraints": [],
            "confidence": 0.95,
            "recommended_steps": ["Compile findings", "Format docx"],
        })
        mock_provider.chat.return_value = mock_response

        interpreter = IntentInterpreter(llm_provider=mock_provider)
        history = [
            {"role": "user", "content": "What are the vibration levels on pump P-101A?"},
            {"role": "assistant", "content": "Vibration levels on P-101A are 4.2 mm/s RMS, exceeding baseline."},
        ]
        intent = interpreter.interpret("Document generation is needed for this", conversation_history=history)

        self.assertEqual(intent.task_type, TaskType.DOCUMENT_GENERATION)
        # Verify provider was called with context containing the prior turns
        call_kwargs = mock_provider.chat.call_args.kwargs
        call_messages = call_kwargs.get("messages") if "messages" in call_kwargs else mock_provider.chat.call_args[0][0]
        all_contents = " ".join(m["content"] for m in call_messages)
        self.assertIn("P-101A", all_contents)
        self.assertIn("Document generation is needed", all_contents)


if __name__ == "__main__":
    unittest.main()

