"""Unit tests for the Generation Layer."""

import unittest

from retrieval.retrieval_models import RetrievalContext, RetrievedChunk
from generation.generation_models import PromptPackage, RawGeneration
from generation.prompt_builder import PromptBuilder
from generation.llm_provider import LLMProvider
from generation.validator import AnswerValidator
from generation.service import GenerationService


class FakeLLMProvider(LLMProvider):
    """Mock LLM provider that returns predetermined strings."""
    def __init__(self, mock_response: str):
        self.mock_response = mock_response

    def generate(self, prompt_package: PromptPackage) -> RawGeneration:
        return RawGeneration(
            raw_response=self.mock_response,
            metadata={"model": "fake-model-1", "tokens": 42}
        )


class TestPromptBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = PromptBuilder()
        self.context = RetrievalContext(
            query="Find pump",
            chunks=(
                RetrievedChunk(
                    chunk_id="chunk-uuid-1",
                    document_id="doc-1",
                    text="The main pump is here.",
                    score=0.9,
                    page_index=1,
                    section="Intro",
                    metadata={}
                ),
                RetrievedChunk(
                    chunk_id="chunk-uuid-2",
                    document_id="doc-2",
                    text="Backup pump is elsewhere.",
                    score=0.8,
                    page_index=2,
                    section=None,
                    metadata={}
                )
            ),
            entities=(),
            relationships=()
        )

    def test_build_masks_identifiers(self):
        package, mapping = self.builder.build(self.context)
        
        # Internal UUIDs should not be in the formatted string
        self.assertNotIn("chunk-uuid-1", package.formatted_context)
        self.assertNotIn("chunk-uuid-2", package.formatted_context)
        
        # But temporary identifiers should be
        self.assertIn("Context #1", package.formatted_context)
        self.assertIn("Context #2", package.formatted_context)
        
        # Metadata check
        self.assertEqual(package.metadata["num_contexts"], 2)
        
        # Mapping should link correctly
        self.assertEqual(mapping[1].chunk_id, "chunk-uuid-1")
        self.assertEqual(mapping[2].chunk_id, "chunk-uuid-2")


class TestAnswerValidator(unittest.TestCase):
    def setUp(self):
        self.validator = AnswerValidator()
        self.mapping = {
            1: RetrievedChunk(
                chunk_id="chunk-uuid-1",
                document_id="doc-1",
                text="Text 1",
                score=0.9,
                page_index=1,
                section="Intro",
                metadata={}
            ),
            2: RetrievedChunk(
                chunk_id="chunk-uuid-2",
                document_id="doc-2",
                text="Text 2",
                score=0.8,
                page_index=5,
                section=None,
                metadata={}
            )
        }

    def test_valid_citations(self):
        raw = RawGeneration(raw_response="The answer is 42. [Context #1]", metadata={})
        result = self.validator.validate(raw, self.mapping)
        
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0].chunk_id, "chunk-uuid-1")
        self.assertEqual(result.citations[0].document_id, "doc-1")
        self.assertEqual(result.citations[0].page_index, 1)

    def test_hallucinated_citations_ignored(self):
        raw = RawGeneration(raw_response="Bad reference [Context #99]", metadata={})
        result = self.validator.validate(raw, self.mapping)
        
        self.assertEqual(len(result.citations), 0)

    def test_duplicate_citations_deduplicated(self):
        raw = RawGeneration(raw_response="Sentence one [Context #2]. Sentence two [Context #2].", metadata={})
        result = self.validator.validate(raw, self.mapping)
        
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0].chunk_id, "chunk-uuid-2")


class TestGenerationService(unittest.TestCase):
    def test_orchestration_flow(self):
        context = RetrievalContext(
            query="test",
            chunks=(
                RetrievedChunk("c-1", "d-1", "text1", 0.9, 1, None, {}),
            ),
            entities=(),
            relationships=()
        )
        
        fake_llm = FakeLLMProvider("Here is the answer. [Context #1]")
        service = GenerationService(llm_provider=fake_llm)
        
        result = service.generate_answer(context)
        
        # Verify raw metadata preserved
        self.assertEqual(result.raw.metadata["model"], "fake-model-1")
        
        # Verify validated answer
        self.assertEqual(len(result.answer.citations), 1)
        self.assertEqual(result.answer.citations[0].chunk_id, "c-1")
        self.assertEqual(result.answer.answer_text, "Here is the answer. [Context #1]")

if __name__ == "__main__":
    unittest.main()
