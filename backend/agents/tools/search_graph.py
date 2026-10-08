"""SearchKnowledgeGraph tool for querying entities and relationships.

Wraps GraphQueryService search_nodes and expand_subgraph to provide the
agent with structured access to the Neo4j Knowledge Graph, including
equipment nodes, components, operating variables, and topology relationships.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.tool_interface import Tool, ToolDefinition, ToolResult
from graph.query_service import GraphQueryService

logger = logging.getLogger(__name__)


class SearchGraphResult(str):
    """String result preserving structured entities and relationships."""

    entities: list[dict[str, Any]]
    edges: list[dict[str, Any]]

    def __new__(
        cls,
        content: str,
        entities: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> SearchGraphResult:
        obj = super().__new__(cls, content)
        obj.entities = entities or []
        obj.edges = edges or []
        return obj


class SearchKnowledgeGraphTool(Tool):
    """Agent tool for querying the Knowledge Graph."""

    def __init__(
        self,
        graph_service: GraphQueryService,
        default_limit: int = 5,
        default_depth: int = 1,
    ) -> None:
        """Initialize the SearchKnowledgeGraph tool.

        Args:
            graph_service: Configured GraphQueryService instance.
            default_limit: Default number of entities to return from search.
            default_depth: Default expansion depth for subgraphs (1 or 2).
        """
        self._graph_service = graph_service
        self._default_limit = default_limit
        self._default_depth = default_depth

    @property
    def definition(self) -> ToolDefinition:
        """Return the tool schema for LLM tool selection."""
        return ToolDefinition(
            name="search_knowledge_graph",
            description=(
                "Searches the industrial Knowledge Graph for equipment entities, "
                "subsystems, components, instruments, and operating parameters, "
                "as well as their relationships (such as CONNECTED_TO, HAS_COMPONENT, "
                "LOCATED_IN, MAINTAINED_BY, CAUSES). Use this tool to answer questions "
                "about plant topology, component connectivity, system hierarchy, "
                "or equipment relationships."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Keyword, equipment tag, or name to search in the knowledge graph "
                            "(e.g., 'P-101', 'Heat Exchanger', 'Crude Column')."
                        ),
                    },
                    "entity_id": {
                        "type": "string",
                        "description": (
                            "Optional exact canonical entity ID to expand the subgraph around. "
                            "If provided, expands connections and neighbors for that entity."
                        ),
                    },
                    "expand_depth": {
                        "type": "integer",
                        "description": (
                            "Maximum traversal depth for relationships (default: 1, max: 2)."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Maximum number of entities to return (default: 5, max: 15)."
                        ),
                    },
                },
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute knowledge graph search and optional subgraph expansion.

        Args:
            arguments: Dictionary with 'query' and/or 'entity_id', 'expand_depth', 'limit'.

        Returns:
            ToolResult containing formatted entities/relationships or error.
        """
        if not isinstance(arguments, dict):
            return ToolResult(
                tool_name="search_knowledge_graph",
                success=False,
                result=None,
                error="Arguments must be a dictionary.",
            )

        query = arguments.get("query")
        entity_id = arguments.get("entity_id")

        has_query = isinstance(query, str) and bool(query.strip())
        has_entity_id = isinstance(entity_id, str) and bool(entity_id.strip())

        if not has_query and not has_entity_id:
            return ToolResult(
                tool_name="search_knowledge_graph",
                success=False,
                result=None,
                error="At least one of 'query' or 'entity_id' must be provided.",
            )

        # Parse limit
        raw_limit = arguments.get("limit", self._default_limit)
        try:
            limit = int(raw_limit)
            if limit <= 0:
                limit = self._default_limit
            elif limit > 15:
                limit = 15
        except (ValueError, TypeError):
            limit = self._default_limit

        # Parse expand_depth
        raw_depth = arguments.get("expand_depth", self._default_depth)
        try:
            depth = int(raw_depth)
            if depth <= 0:
                depth = self._default_depth
            elif depth > 2:
                depth = 2
        except (ValueError, TypeError):
            depth = self._default_depth

        try:
            matched_entities: list[dict[str, Any]] = []
            collected_edges: list[dict[str, Any]] = []

            # Case 1: Specific entity_id provided for expansion
            if has_entity_id:
                clean_eid = str(entity_id).strip()
                subgraph = await asyncio.to_thread(
                    self._graph_service.expand_subgraph,
                    entity_id=clean_eid,
                    max_depth=depth,
                )
                center = subgraph.get("center")
                if center:
                    matched_entities.append(center)
                matched_entities.extend(
                    n for n in subgraph.get("nodes", [])
                    if n.get("entity_id") != clean_eid
                )
                collected_edges.extend(subgraph.get("edges", []))

            # Case 2: Query provided for search_nodes
            elif has_query:
                clean_query = str(query).strip()
                nodes = await asyncio.to_thread(
                    self._graph_service.search_nodes,
                    query=clean_query,
                    limit=limit,
                )
                matched_entities.extend(nodes)

                # Expand the top matched entity if found to retrieve relationships
                if matched_entities and depth > 0:
                    top_eid = matched_entities[0].get("entity_id")
                    if top_eid:
                        subgraph = await asyncio.to_thread(
                            self._graph_service.expand_subgraph,
                            entity_id=top_eid,
                            max_depth=depth,
                        )
                        # Add newly discovered neighbor nodes
                        existing_eids = {e.get("entity_id") for e in matched_entities}
                        for neighbor in subgraph.get("nodes", []):
                            neid = neighbor.get("entity_id")
                            if neid and neid not in existing_eids:
                                matched_entities.append(neighbor)
                                existing_eids.add(neid)
                        collected_edges.extend(subgraph.get("edges", []))

            # Deduplicate entities
            unique_entities: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            for ent in matched_entities:
                eid = ent.get("entity_id") or ent.get("canonical_name") or str(ent)
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    unique_entities.append(ent)

            if not unique_entities and not collected_edges:
                search_desc = f"entity_id='{entity_id}'" if has_entity_id else f"query='{query}'"
                msg = f"No entities or relationships found in Knowledge Graph for {search_desc}."
                return ToolResult(
                    tool_name="search_knowledge_graph",
                    success=True,
                    result=SearchGraphResult(msg, [], []),
                )

            # Format human-readable output for LLM
            lines = [f"Knowledge Graph results (found {len(unique_entities)} entities, {len(collected_edges)} relationships):"]
            
            if unique_entities:
                lines.append("\nEntities:")
                for i, ent in enumerate(unique_entities[:limit], 1):
                    name = ent.get("canonical_name", "Unknown")
                    etype = ent.get("entity_type", "Entity")
                    eid = ent.get("entity_id", "")
                    doc = ent.get("document_id")
                    
                    header = f"[{i}] {name} (Type: {etype}, ID: {eid})"
                    if doc:
                        header += f" [Doc: {doc}]"
                    lines.append(header)

                    # List other properties if present
                    props = {
                        k: v for k, v in ent.items()
                        if k not in {"entity_id", "canonical_name", "entity_type", "document_id", "occurrences", "confidence"}
                    }
                    if props:
                        lines.append(f"    Properties: {props}")

            if collected_edges:
                lines.append("\nRelationships:")
                for edge in collected_edges:
                    rel_type = edge.get("relationship_type", "RELATED_TO")
                    src = edge.get("source_entity_id", edge.get("source", "Source"))
                    tgt = edge.get("target_entity_id", edge.get("target", "Target"))
                    lines.append(f"  - ({src}) -[:{rel_type}]-> ({tgt})")

            content = "\n".join(lines)
            return ToolResult(
                tool_name="search_knowledge_graph",
                success=True,
                result=SearchGraphResult(content, unique_entities, collected_edges),
            )

        except Exception as e:
            logger.error("SearchKnowledgeGraphTool error: %s", e, exc_info=True)
            return ToolResult(
                tool_name="search_knowledge_graph",
                success=False,
                result=None,
                error=f"Knowledge Graph query failed: {str(e)}",
            )
