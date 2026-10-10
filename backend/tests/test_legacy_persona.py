"""Unit and integration tests for Legacy QueryOrchestrator and PromptBuilder persona integration."""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from database.user_repository import User, UserProfile, UserRepository
from generation.generation_models import GeneratedAnswer, GenerationResult, RawGeneration, PromptPackage
from generation.prompt_builder import PromptBuilder
from generation.service import GenerationService
from query.orchestrator import QueryOrchestrator
from retrieval.retrieval_models import RetrievalContext, RetrievedChunk
from api.routes.query import QueryRequest, submit_query


class TestLegacyPersonaIntegration(unittest.TestCase):
    """Test persona prompt injection in PromptBuilder and legacy QueryOrchestrator."""

    def test_prompt_builder_with_persona_instructions(self):
        builder = PromptBuilder(system_prompt_template="Base System Prompt.")
        context = RetrievalContext(
            query="Explain heat exchanger fouling",
            chunks=[
                RetrievedChunk(
                    chunk_id="chk-1",
                    document_id="manual.pdf",
                    text="Fouling decreases the overall heat transfer coefficient.",
                    score=0.9,
                    page_index=1,
                    section="Section 4.1",
                    metadata={},
                )
            ],
            entities=[],
            relationships=[],
        )

        persona = (
            "--- USER EXPERTISE & PERSONA DIRECTIVES ---\n"
            "User Role: Graduate Trainee\n"
            "Experience Level: BEGINNER\n"
            "COMMUNICATION RULES:\n"
            "Explain foundational concepts clearly."
        )

        package, context_mapping = builder.build(
            context,
            persona_instructions=persona,
        )

        self.assertIn("Base System Prompt.", package.system_prompt)
        self.assertIn("User Role: Graduate Trainee", package.system_prompt)
        self.assertIn("Experience Level: BEGINNER", package.system_prompt)
        self.assertIn("Explain foundational concepts clearly.", package.system_prompt)

        # Ensure context mapping and citations remain intact
        self.assertEqual(len(context_mapping), 1)
        self.assertEqual(context_mapping[1].chunk_id, "chk-1")
        self.assertIn("--- Context #1 ---", package.formatted_context)

    def test_prompt_builder_without_persona_instructions(self):
        builder = PromptBuilder(system_prompt_template="Base System Prompt Only.")
        context = RetrievalContext(
            query="Hello",
            chunks=[],
            entities=[],
            relationships=[],
        )

        package, context_mapping = builder.build(context, persona_instructions=None)
        self.assertEqual(package.system_prompt, "Base System Prompt Only.")

    def test_generation_service_passes_persona_to_prompt_builder(self):
        mock_llm = MagicMock()
        mock_builder = MagicMock(spec=PromptBuilder)
        mock_builder.build.return_value = (
            PromptPackage(
                system_prompt="Custom System Prompt",
                user_prompt="Query",
                formatted_context="",
                metadata={},
            ),
            {},
        )
        mock_validator = MagicMock()
        mock_validator.validate.return_value = GeneratedAnswer(
            answer_text="Validated text", citations=()
        )

        service = GenerationService(
            llm_provider=mock_llm,
            prompt_builder=mock_builder,
            validator=mock_validator,
        )

        context = RetrievalContext(query="test", chunks=[], entities=[], relationships=[])
        persona = "Persona Directives"

        service.generate_answer(
            context=context,
            persona_instructions=persona,
        )

        mock_builder.build.assert_called_once_with(
            context,
            conversation_history=(),
            persona_instructions=persona,
        )

    def test_query_orchestrator_passes_persona_to_generation_service(self):
        mock_retrieval = MagicMock()
        mock_retrieval.retrieve.return_value = RetrievalContext(
            query="test", chunks=[], entities=[], relationships=[]
        )
        mock_generation = MagicMock()
        mock_generation.generate_answer.return_value = GenerationResult(
            answer=GeneratedAnswer(answer_text="Answer with persona", citations=()),
            raw=RawGeneration(raw_response="Answer", metadata={}),
        )

        orchestrator = QueryOrchestrator(
            retrieval_service=mock_retrieval,
            generation_service=mock_generation,
        )

        persona = "Expert Persona Directives"
        result = orchestrator.answer_query(
            query="test",
            persona_instructions=persona,
        )

        self.assertEqual(result.answer.answer_text, "Answer with persona")
        mock_generation.generate_answer.assert_called_once_with(
            mock_retrieval.retrieve.return_value,
            conversation_history=(),
            persona_instructions=persona,
        )

    def test_submit_query_legacy_fallback_injects_persona(self):
        mock_agent_orch = MagicMock()
        mock_legacy_orch = MagicMock(spec=QueryOrchestrator)
        mock_legacy_orch.answer_query.return_value = GenerationResult(
            answer=GeneratedAnswer(answer_text="Legacy persona answer", citations=()),
            raw=RawGeneration(raw_response="Legacy persona answer", metadata={}),
        )

        user = User(
            user_id="usr_01",
            email="eng@plant.internal",
            password_hash="hash",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        profile = UserProfile(
            user_id="usr_01",
            name="Bob",
            designation="Field Engineer",
            refinery_experience_level="intermediate",
            preferred_explanation_depth="moderate",
        )

        mock_user_repo = MagicMock(spec=UserRepository)
        mock_user_repo.get_profile.return_value = profile

        request = QueryRequest(query="Check pressure", use_agent=False)

        response = asyncio.run(
            submit_query(
                request=request,
                current_user=user,
                agent_orchestrator=mock_agent_orch,
                legacy_orchestrator=mock_legacy_orch,
                user_repo=mock_user_repo,
            )
        )

        self.assertEqual(response.answer, "Legacy persona answer")
        mock_legacy_orch.answer_query.assert_called_once()
        call_kwargs = mock_legacy_orch.answer_query.call_args[1]
        passed_persona = call_kwargs["persona_instructions"]
        self.assertIn("Experience Level: INTERMEDIATE", passed_persona)
        self.assertIn("User Role: Field Engineer", passed_persona)


if __name__ == "__main__":
    unittest.main()
