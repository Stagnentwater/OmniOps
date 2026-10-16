"""Unit tests for Conversation-Scoped Image Context Persistence (V4 Feature B)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from database.chat_repository import ChatMessage, ChatRepository
from services.conversation_image_service import (
    ConversationImageService,
    ImageContextRecord,
)
from api.routes.query import _enrich_image_context_from_agent


class TestConversationImageContext(unittest.TestCase):
    """Test suite for conversation-scoped image persistence and isolation."""

    def test_image_context_record_serialization(self) -> None:
        """Verify ImageContextRecord round-trip serialization."""
        record = ImageContextRecord(
            document_id="doc-abc123",
            filename="PID-101-Crude-Tower.png",
            storage_path="/data/storage/doc-abc123.png",
            classification="P&ID_DIAGRAM",
            extracted_summary="Crude tower column with reflux loop",
            detected_equipment=["C-101", "P-101A", "MOV-102"],
            detected_connections=["P-101A -> C-101 feed", "V-102 bypass"],
        )

        d = record.to_dict()
        self.assertEqual(d["document_id"], "doc-abc123")
        self.assertEqual(d["filename"], "PID-101-Crude-Tower.png")
        self.assertEqual(d["detected_equipment"], ["C-101", "P-101A", "MOV-102"])

        restored = ImageContextRecord.from_dict(d)
        self.assertEqual(restored.document_id, record.document_id)
        self.assertEqual(restored.filename, record.filename)
        self.assertEqual(restored.detected_equipment, record.detected_equipment)
        self.assertEqual(restored.detected_connections, record.detected_connections)

    def test_get_active_image_context_resolves_most_recent(self) -> None:
        """Verify resolving image context returns the most recent image record."""
        mock_repo = MagicMock(spec=ChatRepository)

        # Mock two messages: first has image context, second is text follow-up
        msg1 = ChatMessage(
            message_id="m1",
            session_id="session-1",
            role="assistant",
            content="I inspected P&ID diagram PID-101.",
            citations=[],
            created_at=None,
            metadata={
                "image_context": {
                    "document_id": "doc-111",
                    "filename": "PID-101.png",
                    "storage_path": "/storage/PID-101.png",
                    "classification": "P&ID_DIAGRAM",
                    "extracted_summary": "Distillation loop",
                    "detected_equipment": ["C-101", "P-101A"],
                    "detected_connections": [],
                }
            },
        )
        msg2 = ChatMessage(
            message_id="m2",
            session_id="session-1",
            role="user",
            content="What is the suction valve for P-101A?",
            citations=[],
            created_at=None,
            metadata={},
        )

        mock_repo.get_recent_messages.return_value = [msg1, msg2]

        service = ConversationImageService(chat_repository=mock_repo)
        resolved = service.get_active_image_context("session-1")

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.document_id, "doc-111")
        self.assertEqual(resolved.filename, "PID-101.png")
        self.assertIn("P-101A", resolved.detected_equipment)

    def test_session_isolation_no_leakage(self) -> None:
        """Verify image context from Session A is never returned for Session B."""
        mock_repo = MagicMock(spec=ChatRepository)
        # Session B has no messages with image context
        mock_repo.get_recent_messages.return_value = [
            ChatMessage(
                message_id="m3",
                session_id="session-B",
                role="user",
                content="Hello there",
                citations=[],
                created_at=None,
                metadata={},
            )
        ]

        service = ConversationImageService(chat_repository=mock_repo)
        resolved = service.get_active_image_context("session-B")

        self.assertIsNone(resolved)
        mock_repo.get_recent_messages.assert_called_with(session_id="session-B", limit=10)

    def test_build_prompt_context_includes_equipment_and_storage(self) -> None:
        """Verify prompt directive contains equipment tags and storage path for agent."""
        service = ConversationImageService()
        record = ImageContextRecord(
            document_id="doc-xyz",
            filename="furnace_schematic.png",
            storage_path="/data/storage/furnace.png",
            classification="P&ID_DIAGRAM",
            extracted_summary="Crude heater F-101",
            detected_equipment=["F-101", "TI-201", "PI-202"],
            detected_connections=["F-101 flue gas to stack"],
        )

        prompt_block = service.build_prompt_context(record)
        self.assertIn("furnace_schematic.png", prompt_block)
        self.assertIn("/data/storage/furnace.png", prompt_block)
        self.assertIn("F-101", prompt_block)
        self.assertIn("TI-201", prompt_block)
        self.assertIn("flue gas to stack", prompt_block)

    def test_enrich_image_context_from_agent(self) -> None:
        """Verify enrichment adds equipment tags discovered in agent answer."""
        existing_ctx = ImageContextRecord(
            document_id="doc-001",
            filename="pid.png",
            storage_path="/path/pid.png",
            detected_equipment=["P-101A"],
        )

        agent_result = MagicMock()
        agent_result.answer = "Upon closer inspection of the diagram, valve MOV-104 and pump P-101B are also visible."

        enriched = _enrich_image_context_from_agent(existing_ctx, agent_result)
        self.assertIsNotNone(enriched)
        self.assertIn("P-101A", enriched.detected_equipment)
        self.assertIn("MOV-104", enriched.detected_equipment)
        self.assertIn("P-101B", enriched.detected_equipment)


if __name__ == "__main__":
    unittest.main()
