"""Unit and integration tests for Agent Orchestrator persona integration."""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from agents.orchestrator import AgentOrchestrator, AgentResult
from database.user_repository import User, UserProfile, UserRepository
from api.routes.query import QueryRequest, submit_query
from generation.persona_builder import PersonaContextBuilder


class TestAgentPersonaIntegration(unittest.TestCase):
    """Test persona prompt injection in AgentOrchestrator and Query API."""

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_registry = MagicMock()
        self.mock_executor = MagicMock()

    def test_orchestrator_run_with_persona_instructions(self):
        orchestrator = AgentOrchestrator(
            llm_provider=self.mock_llm,
            tool_registry=self.mock_registry,
            tool_executor=self.mock_executor,
            system_prompt="Base System Prompt.",
        )

        persona_directives = (
            "--- USER EXPERTISE & PERSONA DIRECTIVES ---\n"
            "User Role: Graduate Trainee\n"
            "Experience Level: BEGINNER\n"
            "COMMUNICATION RULES:\n"
            "Explain foundational concepts clearly."
        )

        # Mock LLM to return immediate answer on first turn
        from agents.ollama_agent_provider import OllamaChatResponse
        self.mock_llm.chat.return_value = OllamaChatResponse(
            content="Heat exchangers transfer heat between two fluids.",
            tool_calls=[],
        )

        result = orchestrator.run(
            query="Explain heat exchangers",
            persona_instructions=persona_directives,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.answer, "Heat exchangers transfer heat between two fluids.")

        # Verify LLM was called with system message containing persona directives
        self.mock_llm.chat.assert_called_once()
        call_kwargs = self.mock_llm.chat.call_args[1]
        messages = call_kwargs["messages"]
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("Base System Prompt.", system_msg["content"])
        self.assertIn("User Role: Graduate Trainee", system_msg["content"])
        self.assertIn("Experience Level: BEGINNER", system_msg["content"])
        self.assertIn("Explain foundational concepts clearly.", system_msg["content"])

    def test_orchestrator_run_without_persona_instructions(self):
        orchestrator = AgentOrchestrator(
            llm_provider=self.mock_llm,
            tool_registry=self.mock_registry,
            tool_executor=self.mock_executor,
            system_prompt="Base System Prompt Only.",
        )

        from agents.ollama_agent_provider import OllamaChatResponse
        self.mock_llm.chat.return_value = OllamaChatResponse(
            content="Standard reply.",
            tool_calls=[],
        )

        result = orchestrator.run(
            query="Hello",
            persona_instructions=None,
        )

        self.mock_llm.chat.assert_called_once()
        messages = self.mock_llm.chat.call_args[1]["messages"]
        system_msg = messages[0]
        self.assertEqual(system_msg["content"], "Base System Prompt Only.")

    def test_submit_query_injects_beginner_persona(self):
        mock_agent_orch = MagicMock(spec=AgentOrchestrator)
        mock_agent_orch.run.return_value = AgentResult(
            answer="Beginner explanation with foundational checks.",
            tool_calls_made=[],
            iterations=1,
            execution_time_seconds=0.1,
            citations=[],
        )
        mock_legacy_orch = MagicMock()

        user = User(
            user_id="usr_trainee",
            email="trainee@plant.internal",
            password_hash="hash",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        profile = UserProfile(
            user_id="usr_trainee",
            name="Alex Chen",
            designation="Graduate Trainee",
            skill_set=["Basic Fluid Dynamics"],
            refinery_experience_level="beginner",
            preferred_explanation_depth="detailed",
        )

        mock_user_repo = MagicMock(spec=UserRepository)
        mock_user_repo.get_profile.return_value = profile

        request = QueryRequest(query="Why is there a pressure drop across E-101?")

        response = asyncio.run(
            submit_query(
                request=request,
                current_user=user,
                agent_orchestrator=mock_agent_orch,
                legacy_orchestrator=mock_legacy_orch,
                user_repo=mock_user_repo,
            )
        )

        self.assertEqual(response.answer, "Beginner explanation with foundational checks.")
        mock_agent_orch.run.assert_called_once()
        call_kwargs = mock_agent_orch.run.call_args[1]
        passed_persona = call_kwargs["persona_instructions"]
        self.assertIn("Experience Level: BEGINNER", passed_persona)
        self.assertIn("User Role: Graduate Trainee", passed_persona)
        self.assertIn("Explain foundational concepts and operational principles clearly", passed_persona)
        self.assertIn("MANDATORY SAFETY CONSTRAINT", passed_persona)

    def test_submit_query_injects_expert_persona_and_updates_live(self):
        mock_agent_orch = MagicMock(spec=AgentOrchestrator)
        mock_agent_orch.run.return_value = AgentResult(
            answer="Expert analysis with DP curve calculation.",
            tool_calls_made=[],
            iterations=1,
            execution_time_seconds=0.1,
            citations=[],
        )
        mock_legacy_orch = MagicMock()

        user = User(
            user_id="usr_expert",
            email="expert@plant.internal",
            password_hash="hash",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        expert_profile = UserProfile(
            user_id="usr_expert",
            name="Dr. Rostova",
            designation="Senior Process Safety Specialist",
            skill_set=["Thermodynamics", "DP Curves"],
            refinery_experience_level="expert",
            preferred_explanation_depth="concise",
        )

        mock_user_repo = MagicMock(spec=UserRepository)
        mock_user_repo.get_profile.return_value = expert_profile

        request = QueryRequest(query="Investigate heat exchanger pressure drop.")

        response = asyncio.run(
            submit_query(
                request=request,
                current_user=user,
                agent_orchestrator=mock_agent_orch,
                legacy_orchestrator=mock_legacy_orch,
                user_repo=mock_user_repo,
            )
        )

        call_kwargs = mock_agent_orch.run.call_args[1]
        passed_persona = call_kwargs["persona_instructions"]
        self.assertIn("Experience Level: EXPERT", passed_persona)
        self.assertIn("User Role: Senior Process Safety Specialist", passed_persona)
        self.assertIn("differential pressure curves, Reynolds numbers, fouling factors", passed_persona)
        self.assertIn("Omit introductory definitions", passed_persona)

        # Dynamic update test: User switches profile to Intermediate
        updated_profile = UserProfile(
            user_id="usr_expert",
            name="Dr. Rostova",
            designation="Plant Manager",
            skill_set=["Operations"],
            refinery_experience_level="intermediate",
            preferred_explanation_depth="moderate",
        )
        mock_user_repo.get_profile.return_value = updated_profile

        asyncio.run(
            submit_query(
                request=request,
                current_user=user,
                agent_orchestrator=mock_agent_orch,
                legacy_orchestrator=mock_legacy_orch,
                user_repo=mock_user_repo,
            )
        )

        call_kwargs_2 = mock_agent_orch.run.call_args[1]
        passed_persona_2 = call_kwargs_2["persona_instructions"]
        self.assertIn("Experience Level: INTERMEDIATE", passed_persona_2)
        self.assertIn("User Role: Plant Manager", passed_persona_2)


if __name__ == "__main__":
    unittest.main()
