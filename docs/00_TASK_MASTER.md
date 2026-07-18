# 00_TASK_MASTER.md

# OmniOps Development Task Master
Version: 1.1.0
Status: Living Development Plan

> This document is the execution roadmap for OmniOps.
> Every task should be completed, tested, committed, and verified before moving to the next.

---

# Development Rules

- Complete only ONE task at a time.
- Never skip dependencies.
- Every task must pass its evaluation.
- Commit after every successful task.
- Do not implement extra features outside the current task.

---

# Current Status

Current Phase: Completed MVP Integration

Current Sprint: None

Current Task: Final Review

Completed Tasks:
- [x] FOUND-001
- [x] FOUND-002
- [x] FOUND-003
- [x] FOUND-004
- [x] FOUND-005
- [x] FOUND-006
- [x] FOUND-007
- [x] ING-001
- [x] ING-002
- [x] ING-003
- [x] ING-004
- [x] ING-005
- [x] NORM-001
- [x] NORM-002
- [x] NORM-003
- [x] NORM-004
- [x] NORM-005
- [x] NORM-006
- [x] ENT-001
- [x] ENT-002
- [x] ENT-003
- [x] ENT-004
- [x] ENT-005
- [x] ENT-006
- [x] ENT-007
- [x] ENT-008
- [x] ENT-009
- [x] REL-001
- [x] REL-002
- [x] REL-003
- [x] REL-004
- [x] REL-005
- [x] REL-006
- [x] REL-007
- [x] REL-008
- [x] GRAPH-001
- [x] GRAPH-002
- [x] GRAPH-003
- [x] GRAPH-004
- [x] GRAPH-005
- [x] GRAPH-006
- [x] VEC-001
- [x] VEC-002
- [x] VEC-003
- [x] VEC-004
- [x] RET-001
- [x] GEN-001
- [x] INT-001

Blocked Tasks:
- None

---

# Task Template

## TASK-ID

**Title**

**Objective**

**Prerequisites**

**Input**

**Expected Output**

**Files to Create / Modify**

**Implementation Notes**

**Acceptance Criteria**

**Evaluation**

**Suggested Commit Message**

**Next Task**

---

# PHASE 0 - Foundation

## FOUND-001
Title: Create repository structure

Goal:
Create the complete project folder structure.

Success:
- backend/
- frontend/
- docs/
- docker/
- tests/

Evaluation:
Repository contains all required folders.

Commit:
feat: initialize repository structure

Next:
FOUND-002

---

## FOUND-002
Title: Setup Python backend

Goal:
Create FastAPI project with virtual environment.

Success:
- FastAPI starts successfully.
- Health endpoint returns HTTP 200.

Evaluation:
Run:
uvicorn main:app --reload

Visit:
/health

Expected:
{"status":"ok"}

Commit:
feat: initialize FastAPI backend

Next:
FOUND-003

---

## FOUND-003
Title: Docker Compose

Goal:
Create docker-compose with:
- FastAPI
- RQ worker
- PostgreSQL
- Neo4j
- Redis
- Qdrant

Evaluation:
docker compose up

Expected:
All services healthy and the worker connects to Redis successfully.

Commit:
chore: add docker compose

Next:
FOUND-004

---

## FOUND-004
Title:
Configuration Manager

Goal:
Centralize all configuration into one config module.

Configuration must support:
- FastAPI
- Neo4j
- Qdrant
- PostgreSQL
- Redis
- OpenRouter
- storage backend selection
- embedding model selection

Evaluation:
Environment variables load correctly in both the API and worker processes.

Commit:
feat: configuration module

Next:
FOUND-005

---

## FOUND-005
Title:
Background Job System

Goal:
Initialize Redis + RQ for ingestion jobs.

Success:
- Upload flow can enqueue a background job.
- Worker can execute a sample job.
- Retry settings are configurable.

Evaluation:
Enqueue a test job and confirm successful worker execution.

Commit:
feat(queue): initialize Redis and RQ

Next:
FOUND-006

---

## FOUND-006
Title:
Storage Service Abstraction

Goal:
Create a StorageService interface with a local filesystem implementation.

Success:
- Original documents are stored through the abstraction.
- No other module depends directly on filesystem paths.
- Future object storage backends can be added without changing ingestion logic.

Evaluation:
Store and retrieve a sample file using the StorageService.

Commit:
feat(storage): add storage abstraction

Next:
FOUND-007

---

## FOUND-007
Title:
Ingestion Job Lifecycle

Goal:
Define and persist ingestion job states in PostgreSQL.

Statuses:
- PENDING
- PROCESSING
- GRAPH_COMPLETE
- VECTOR_COMPLETE
- COMPLETED
- FAILED

Evaluation:
Sample jobs transition through the expected states and remain queryable.

Commit:
feat(ingestion): add job lifecycle tracking

Next:
ING-001

---

# PHASE 1 - Document Ingestion

MVP scope in this phase:
- Machine-readable PDF
- DOCX
- CSV

Out of MVP unless time permits:
- Scanned PDF OCR
- XLSX
- Images
- P&ID

## ING-001

Title:
Machine-readable PDF Parser

Goal:
Extract text and metadata from native PDFs.

Input:
PDF

Output:
DocumentContent object

Implementation:
- PyMuPDF
- Preserve page numbers
- Preserve metadata
- No OCR

Acceptance:
- Text extracted
- Metadata extracted
- Page count correct

Evaluation:
Test with five PDFs.

Commit:
feat(parser): PDF parser

Next:
ING-002

---

## ING-002

Title:
DOCX Parser

Goal:
Extract paragraphs, headings, and tables.

Evaluation:
Word document parsed successfully.

Commit:
feat(parser): DOCX parser

Next:
ING-003

---

## ING-003

Title:
CSV Parser

Goal:
Load CSV into structured records.

Evaluation:
No parsing errors.

Commit:
feat(parser): CSV parser

Next:
ING-004

---

## ING-004

Title:
Metadata Extractor

Goal:
Generate unified metadata for every ingested document.

Fields:
- document_id
- filename
- type
- upload_time
- page_count
- file_hash
- storage_uri
- ingestion_job_id

Evaluation:
Metadata stored successfully.

Commit:
feat(ingestion): metadata extraction

Next:
ING-005

---

## ING-005

Title:
Knowledge Resolution

Goal:
Resolve duplicates, aliases, conflicting facts, source authority, confidence scoring, and provenance before storage.

Acceptance:
- Canonical entities selected deterministically
- Conflicts preserved with traceable provenance
- Confidence scores attached to resolved facts

Evaluation:
Sample duplicate assets resolve consistently without losing evidence.

Commit:
feat(ingestion): add knowledge resolution layer

Next:
PHASE 2

---

# Stretch Backlog - Non-MVP Parsers

## STRETCH-ING-001
Title: Scanned PDF OCR

Goal:
Extract text from scanned PDFs.

---

## STRETCH-ING-002
Title: Excel Parser

Goal:
Read worksheets into structured rows.

---

## STRETCH-ING-003
Title: Image OCR

Goal:
Extract text from PNG and JPG files.

---

## STRETCH-ING-004
Title: P&ID Parser

Goal:
Convert engineering drawing symbols and labels into graph-ready entities and relationships.

---

# PHASE 2 - Normalization

Tasks:
- NORM-001 Clean whitespace
- NORM-002 Normalize encoding
- NORM-003 Page segmentation
- NORM-004 Table extraction
- NORM-005 Image extraction
- NORM-006 Intelligent chunking

Evaluation:
Clean structured document produced.

---

# PHASE 3 - Entity Extraction

Tasks:
- ENT-001 Equipment
- ENT-002 Components
- ENT-003 People
- ENT-004 Locations
- ENT-005 Dates
- ENT-006 Maintenance intervals
- ENT-007 Failure types
- ENT-008 Regulations
- ENT-009 Work orders

Evaluation:
Known entities correctly extracted.

---

# PHASE 4 - Relationship Extraction

Tasks:
- REL-001 HAS_COMPONENT
- REL-002 CONNECTED_TO
- REL-003 MAINTAINED_BY
- REL-004 LOCATED_IN
- REL-005 INSPECTED_BY
- REL-006 CAUSES
- REL-007 REFERENCES
- REL-008 SIMILAR_TO

Evaluation:
Graph relationships created correctly.

---

# PHASE 5 - Knowledge Graph

Tasks:
- GRAPH-001 Neo4j connection
- GRAPH-002 Create nodes
- GRAPH-003 Create edges
- GRAPH-004 Deduplicate assets
- GRAPH-005 Query service
- GRAPH-006 Graph expansion

Evaluation:
Asset neighborhood returned correctly.

---

# PHASE 6 - Vector Pipeline

Tasks:
- VEC-001 Embedding service
- VEC-002 Store vectors in Qdrant
- VEC-003 Semantic search
- VEC-004 Ranking

Evaluation:
Relevant chunks returned.

---

# PHASE 7 - Retrieval

Tasks:
- RET-001 Metadata search
- RET-002 Vector search
- RET-003 Graph search
- RET-004 Merge context
- RET-005 Rank context
- RET-006 Build final prompt context

Evaluation:
Single context object assembled.

---

# PHASE 8 - Prompt Builder

Tasks:
- PROMPT-001 System prompt
- PROMPT-002 Citation formatter
- PROMPT-003 Evidence formatter
- PROMPT-004 Prompt assembler

Evaluation:
Prompt contains context + evidence.

---

# PHASE 9 - LLM

Tasks:
- LLM-001 OpenRouter client
- LLM-002 Streaming
- LLM-003 JSON responses
- LLM-004 Retry handling

Evaluation:
Question answered successfully.

---

# PHASE 10 - GraphRAG

Tasks:
- GRAG-001 Graph retrieval
- GRAG-002 Hybrid retrieval
- GRAG-003 Context builder
- GRAG-004 Answer generation

Evaluation:
Answer includes citations.

---

# PHASE 11 - Insight Engine

Tasks:
- INS-001 Executive summary
- INS-002 Maintenance alerts
- INS-003 Compliance alerts
- INS-004 Lessons learned
- INS-005 Asset health summary

Evaluation:
Insights generated after ingestion.

---

# PHASE 12 - APIs

Tasks:
- API-001 Upload
- API-002 Ingestion Job Status
- API-003 Search
- API-004 Chat
- API-005 Assets
- API-006 Graph
- API-007 Insights

---

# PHASE 13 - Frontend

Tasks:
- UI-001 Dashboard
- UI-002 Upload
- UI-003 Documents
- UI-004 Copilot
- UI-005 Knowledge Graph
- UI-006 Asset Explorer
- UI-007 Insights

---

# PHASE 14 - Deployment

Tasks:
- DEP-001 Docker stack
- DEP-002 Production configuration
- DEP-003 CI/CD
- DEP-004 Cloud-portable deployment

---

# Rule

Never move to the next task until the current task:
- Builds successfully
- Passes evaluation
- Is committed to Git
- Is documented if needed
