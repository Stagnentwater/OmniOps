
# 03_GRAPH_SCHEMA.md

# OmniOps Knowledge Graph Schema
Version: 1.0.0
Status: Living Specification

---

# Purpose

This document defines the ontology used by OmniOps.

The Knowledge Graph is the platform's primary representation of explicit industrial knowledge.

The graph stores facts, relationships, timelines and evidence.
The Vector Database stores semantic similarity.

Together they form GraphRAG.

---

# Design Principles

- Every node represents a real-world concept.
- Every relationship must have supporting evidence.
- Every node has a canonical identifier.
- Never duplicate entities.
- Preserve history instead of overwriting facts.
- Preserve provenance and source authority for every fact.
- Resolve conflicts before graph writes, but never delete the losing evidence.

---

# Core Node Types

## Asset

Examples:
- Pump P301
- Boiler B2
- Valve V12
- Compressor C1

Properties:
- asset_id
- asset_type
- name
- manufacturer
- model
- status

---

## Component

Examples:
- Bearing
- Seal
- Motor
- Impeller

Properties:
- component_id
- name
- specification

---

## Document

Examples:
- OEM Manual
- Inspection Report
- SOP
- Incident Report

Properties:
- document_id
- title
- type
- version
- upload_date

---

## Event

Types:
- Inspection
- Maintenance
- Failure
- Shutdown
- Repair
- Replacement

Properties:
- event_id
- timestamp
- severity
- summary

---

## Person

Properties:
- person_id
- name
- role

---

## Location

Examples:
- Plant A
- Area 1
- Line 2

---

## Regulation

Examples:
- OSHA
- ISO
- Internal SOP

---

## Parameter

Examples:
- Pressure
- Temperature
- RPM
- Flow Rate
- Vibration

---

# Relationship Types

| Relationship | Meaning |
|--------------|---------|
| HAS_COMPONENT | Asset contains component |
| CONNECTED_TO | Physical connection |
| LOCATED_IN | Asset location |
| MAINTAINED_BY | Person performed maintenance |
| INSPECTED_BY | Person inspected asset |
| REFERENCES | Document references entity |
| DESCRIBES | Manual describes asset |
| CAUSES | Failure relationship |
| GENERATED_EVENT | Document created event |
| COMPLIES_WITH | Asset/process follows regulation |
| VIOLATES | Compliance issue |
| SIMILAR_TO | Historical similarity |

Every relationship stores:
- source_document
- page_number
- confidence
- source_authority
- created_at

---

# Canonical Asset Resolution

Before creating a node:

1. Search existing assets.
2. Compare aliases.
3. Compare equipment tags.
4. Merge if same asset.
5. Otherwise create new node.

Example:

P301
Pump-301
Pump P301

-> 

Single Asset Node

---

# Timeline Model

Events are never overwritten.

Asset

-> 

Inspection

-> 

Repair

-> 

Failure

-> 

Replacement

-> 

Inspection

This enables historical reasoning.

---

# Graph Update Rules

When new knowledge arrives:

1. Run knowledge resolution before creating or updating graph facts.
2. Create missing nodes.
3. Update existing metadata.
4. Create new relationships.
5. Preserve historical events.
6. Attach evidence.

Never delete historical evidence.

---

# Evidence Model

Every node and relationship must be traceable.

Evidence contains:

- document_id
- ingestion_job_id
- page
- paragraph
- chunk_id
- confidence
- source_authority

LLM responses must reference this evidence.

---

# Graph Queries

Typical traversals:

- Asset -> Components
- Asset -> Events
- Asset -> Documents
- Asset -> Regulations
- Asset -> Similar Failures
- Asset -> Maintenance History

These traversals provide structural context for GraphRAG.

---

# Interaction with Vector Store

Knowledge Graph:
- explicit facts
- topology
- timelines

Vector Store:
- semantic chunks
- embeddings
- fuzzy matching

Current vector database:
- Qdrant

Hybrid retrieval always combines both.

---

# Acceptance Criteria

The graph implementation is complete when:

- Nodes are deduplicated.
- Relationships contain evidence.
- Timeline queries work.
- Neighbor expansion works.
- Graph supports GraphRAG.

---

Dependencies:
- 01_CONTEXT.md
- 02_SYSTEM_ARCHITECTURE.md

Next:
04_INGESTION_PIPELINE.md
