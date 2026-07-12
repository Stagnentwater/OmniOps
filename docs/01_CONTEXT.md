# 01_CONTEXT.md
**Project:** OmniOps  
**Version:** 1.1.0  
**Status:** Living Specification

# FOR AI CODING AGENTS

This document is the primary source of truth for the repository. Before generating or modifying any code:

1. Read this document completely.
2. Preserve the architecture described here.
3. Prefer modularity over shortcuts.
4. Never introduce features that contradict the product vision.
5. If uncertain, favor maintainability, traceability, and explainability.

---

# Vision

OmniOps is an **Industrial Intelligence Platform**.

It is **not** a chatbot.

It is a continuously evolving knowledge platform that transforms fragmented industrial information into organizational memory using document intelligence, knowledge graphs, hybrid retrieval, and AI reasoning.

Documents are evidence.

Knowledge is the product.

---

# Mission

Convert heterogeneous industrial data into a living operational brain capable of:

- Understanding documents
- Connecting knowledge
- Preserving expertise
- Answering questions with evidence
- Generating proactive operational insights

---

# Product Philosophy

OmniOps exists because industrial knowledge is fragmented.

Knowledge lives inside:

- OEM manuals
- Inspection reports
- Maintenance logs
- P&IDs
- SOPs
- Regulations
- Emails
- Work orders
- Engineer notes

The platform continuously unifies these into one searchable knowledge system.

---

# Core Principles

1. Knowledge-first architecture.
2. Knowledge Graph is the system of relationships.
3. Vector retrieval provides semantic recall.
4. Every AI answer must be evidence-backed.
5. Every upload should improve the platform.
6. No hallucinated industrial facts.
7. Documents are immutable evidence.
8. The chatbot is only one interface.

---

# Target Users

- Maintenance Engineer
- Field Engineer
- Plant Manager
- Reliability Engineer
- Compliance Officer
- Operations Manager

---

# Core Features

## Universal Ingestion

MVP supported sources:

- Machine-readable PDF
- DOCX
- CSV

Architecturally planned for future phases:

- Scanned PDF OCR
- XLSX
- Images
- P&ID Drawings
- Text
- Email

---

## Knowledge Extraction

Every document should produce:

- Metadata
- Sections
- Semantic chunks
- Entities
- Relationships
- Events
- Asset references
- Citations

---

## Knowledge Graph

The graph represents:

Assets

Components

Procedures

Failures

Inspections

Maintenance

Regulations

Incidents

People

Locations

Relationships

---

## Platform Stack

- FastAPI for the primary API layer
- Neo4j for explicit industrial relationships
- Qdrant for semantic vector retrieval
- PostgreSQL for users, document metadata, ingestion jobs, audit data, and configuration
- Redis + RQ for asynchronous ingestion jobs
- OpenRouter for LLM reasoning only
- StorageService abstraction for original file storage
- BAAI/bge-m3 as the initial recommended open-source embedding model for industrial documentation

---

## Hybrid Retrieval

Always retrieve using:

1. Metadata filters from PostgreSQL
2. Semantic vector search from Qdrant
3. Knowledge graph traversal from Neo4j
4. Context ranking
5. Prompt assembly

Never rely on vector search alone.

---

## AI Features

Shared retrieval engine.

Reasoning modes:

- Copilot
- Maintenance
- Compliance
- Lessons Learned
- Executive Summary
- Alert Generation

Only prompts differ.

---

# High-Level Workflow

Upload

->

Create Ingestion Job

->

Classification

->

Parsing

->

Document Understanding

->

Knowledge Extraction

->

Knowledge Resolution

->

Knowledge Validation

->

Graph Update + Vector Update

->

Hybrid Retrieval

->

Prompt Builder

->

LLM

->

Evidence-backed Response

---

# Functional Requirements

The platform shall:

- ingest documents
- classify documents
- extract structured knowledge
- update the knowledge graph
- generate embeddings
- create background ingestion jobs
- expose ingestion job status
- answer engineering questions
- provide citations
- generate summaries
- generate alerts
- preserve organizational memory

---

# Non-Functional Requirements

- Modular
- Explainable
- Scalable
- Traceable
- Portable
- Deployable
- Idempotent
- Resumable
- Mobile friendly
- Fast retrieval
- Extensible

---

# MVP Constraints

- Authentication and RBAC are not part of the MVP.
- Uploads must be asynchronous and return a job ID immediately.
- Retrieval must reason only over validated knowledge.
- OCR, P&ID parsing, image ingestion, and XLSX parsing are future-scope features unless explicitly scheduled.

---

# Deployment Principles

- Development starts locally using Docker.
- The local stack must support FastAPI, Neo4j, PostgreSQL, Redis, and Qdrant.
- The architecture must remain cloud-portable.
- Original file storage must go through StorageService, never direct filesystem access from unrelated modules.

---

# Repository Philosophy

Separate concerns.

frontend/

backend/

docs/

shared/

Never mix business logic with UI.

Never place graph logic inside API routes.

---

# Backend Modules

api/

ingestion/

graph/

retrieval/

llm/

agents/

database/

services/

storage/

workers/

utils/

---

# Frontend Modules

pages/

components/

hooks/

services/

layouts/

graph/

chat/

---

# Coding Standards

- Python typing everywhere
- Pydantic models
- Async where appropriate
- Small reusable functions
- Clear naming
- No duplicated logic
- Meaningful logging
- Unit-testable services

---

# Naming Conventions

Classes: PascalCase

Functions: snake_case

Variables: snake_case

Constants: UPPER_CASE

React Components: PascalCase

---

# AI Philosophy

The LLM is NOT the source of truth.

Truth comes from:

- Knowledge Graph
- Vector Retrieval
- Metadata
- Source Documents

The LLM reasons over retrieved evidence.

---

# UI Philosophy

Professional.

Industrial.

Minimal.

Evidence-first.

The dashboard should answer:

What changed?

What needs attention?

Why?

---

# Definition of Done

A feature is complete only if:

- Backend implemented
- Frontend integrated
- Tested
- Documented
- Reusable
- Architecture compliant

---

# Roadmap

Phase 1

Foundation

Phase 2

Ingestion

Phase 3

Knowledge Graph

Phase 4

Hybrid Retrieval

Phase 5

AI Copilot

Phase 6

Insight Engine

Phase 7

Polish

---

# Coding Agent Notes

Never simplify the architecture into "upload -> vector DB -> chatbot".

Always preserve:

Document -> Knowledge -> Graph -> Retrieval -> Context -> LLM.

When uncertain, prioritize correctness over speed.

This document intentionally focuses on product philosophy. Technical details belong in:

02_SYSTEM_ARCHITECTURE.md

03_GRAPH_SCHEMA.md

04_INGESTION_PIPELINE.md

05_RETRIEVAL_ENGINE.md

Additional specification files should be added only after they are explicitly approved.
