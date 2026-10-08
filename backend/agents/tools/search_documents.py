"""SearchDocuments tool for semantic retrieval over indexed documents.

Wraps RetrievalService._retrieve_vectors to provide the agent with
vector-based document search across operating manuals, standard operating
procedures (SOPs), maintenance logs, and technical specifications.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.tool_interface import Tool, ToolDefinition, ToolResult
from retrieval.retrieval_models import RetrievedChunk
from retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class SearchDocumentsResult(str):
    """String result that also preserves the raw RetrievedChunk objects."""

    chunks: list[RetrievedChunk]

    def __new__(cls, content: str, chunks: list[RetrievedChunk]) -> SearchDocumentsResult:
        obj = super().__new__(cls, content)
        obj.chunks = chunks
        return obj


class SearchDocumentsTool(Tool):
    """Agent tool for semantic document search via vector embeddings."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        default_limit: int = 5,
    ) -> None:
        """Initialize the SearchDocuments tool.

        Args:
            retrieval_service: Configured RetrievalService instance.
            default_limit: Default number of chunks to retrieve if not specified.
        """
        self._retrieval_service = retrieval_service
        self._default_limit = default_limit

    @property
    def definition(self) -> ToolDefinition:
        """Return the tool schema for LLM tool selection."""
        return ToolDefinition(
            name="search_documents",
            description=(
                "Searches indexed industrial documentation, operating manuals, "
                "standard operating procedures (SOPs), maintenance records, and "
                "technical specifications for relevant text chunks using semantic vector search. "
                "Use this tool when you need information from documents to answer "
                "technical, operational, procedural, or troubleshooting questions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The search query or keywords describing the document content needed."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Maximum number of document chunks to return (default: 5, max: 20)."
                        ),
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute semantic search over indexed documents.

        Args:
            arguments: Dictionary with 'query' and optional 'limit'.

        Returns:
            ToolResult containing search results or error details.
        """
        if not isinstance(arguments, dict):
            return ToolResult(
                tool_name="search_documents",
                success=False,
                result=None,
                error="Arguments must be a dictionary.",
            )

        query = arguments.get("query")
        if not query or not isinstance(query, str) or not query.strip():
            return ToolResult(
                tool_name="search_documents",
                success=False,
                result=None,
                error="Parameter 'query' is required and must be a non-empty string.",
            )

        query = query.strip()
        raw_limit = arguments.get("limit", self._default_limit)
        try:
            limit = int(raw_limit)
            if limit <= 0:
                limit = self._default_limit
            elif limit > 20:
                limit = 20
        except (ValueError, TypeError):
            limit = self._default_limit

        try:
            # _retrieve_vectors is synchronous CPU/network I/O; run in threadpool
            chunks: list[RetrievedChunk] = await asyncio.to_thread(
                self._retrieval_service._retrieve_vectors,
                query=query,
                limit=limit,
            )

            if not chunks:
                msg = f"No document chunks found matching query: '{query}'."
                return ToolResult(
                    tool_name="search_documents",
                    success=True,
                    result=SearchDocumentsResult(msg, []),
                )

            # Format chunks into a readable string for the LLM
            lines = [f"Found {len(chunks)} relevant document chunk(s) for '{query}':"]
            for i, chunk in enumerate(chunks, 1):
                header_parts = [f"[{i}] Document: {chunk.document_id}"]
                if chunk.page_index is not None:
                    header_parts.append(f"Page: {chunk.page_index}")
                if chunk.section:
                    header_parts.append(f"Section: {chunk.section}")
                header_parts.append(f"Score: {chunk.score:.4f}")
                lines.append(" | ".join(header_parts))
                lines.append(chunk.text.strip())

            content = "\n\n".join(lines)
            return ToolResult(
                tool_name="search_documents",
                success=True,
                result=SearchDocumentsResult(content, chunks),
            )

        except Exception as e:
            logger.error("SearchDocumentsTool error during retrieval: %s", e, exc_info=True)
            return ToolResult(
                tool_name="search_documents",
                success=False,
                result=None,
                error=f"Vector retrieval failed: {str(e)}",
            )
