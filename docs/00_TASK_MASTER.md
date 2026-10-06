# 00_TASK_MASTER.md

# OmniOps Development Task Master
Version: 1.5.0
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

Current Phase: Version 1.5 — Intelligence and Reliability

Current Sprint: Version 1.5 P1 — Automated Quality Gate

Current Task: V15-TEST-001

Roadmap Source:
- `docs/Version1.md` is the current roadmap source for the next implementation phase.
- `docs/06_VERSION_2_DESC.md` is explicitly deferred. It must not be used to select or redefine Version 1.5 tasks.

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
- [x] V15-CONV-001

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

# PHASE 15 - Version 1.5 Intelligence and Reliability

Scope source: `docs/Version1.md` section 5 and the v1.5 roadmap. This phase extends the existing knowledge-first architecture; it does not begin Version 2 visual-platform work.

## V15-CONV-001

Title: Conversation Remembrance

Objective:
Provide bounded, ordered prior-turn context to a query within an existing chat session, without treating chat history as evidence or changing citation provenance.

Prerequisites:
- Existing `chat_sessions` and `chat_messages` persistence
- Existing retrieval, generation, and citation-validation pipeline

Files to Create / Modify:
- `backend/config/settings.py`
- `backend/database/chat_repository.py`
- `backend/dependencies.py`
- `backend/query/orchestrator.py`
- `backend/api/routes/query.py`
- `backend/generation/generation_models.py`
- `backend/generation/prompt_builder.py`
- `backend/generation/service.py`
- `backend/generation/openrouter_provider.py`
- `backend/generation/ollama_provider.py`
- `backend/tests/test_generation.py`
- `backend/tests/test_query_orchestrator.py`

Implementation Notes:
- Retrieve only a bounded window of preceding messages, in chronological order, and exclude the newly persisted user message.
- Make the history limit configuration-driven.
- Label history as non-authoritative conversational context. It may resolve references, but factual claims must remain grounded in the current retrieved evidence and use current `[Context #N]` citations.
- Keep history out of the citation mapping and preserve the existing synchronous and SSE API contracts.

Acceptance Criteria:
- A streaming query with a session includes prior conversation turns in the LLM prompt.
- The current user question is not duplicated as a prior turn.
- No history message can create or alter a citation mapping.
- A query without a session behaves as before.
- Unit tests cover ordering, bounds, prompt separation, and orchestration.

Evaluation:
- Run the focused generation and query-orchestrator unit tests.
- Run the existing backend test suite to detect regressions. Its baseline currently has 34 unrelated errors because in-memory graph and vector test doubles do not implement the existing `delete_document` abstract-interface method; repair is tracked in V15-TEST-001.

Suggested Commit Message:
feat(chat): add bounded conversation remembrance

Next:
V15-TEST-001

---

## V15-TEST-001

Title: Version 1.5 Automated Quality Gate

Objective:
Establish repeatable unit coverage for the v1.5 services and make the backend test command part of the implementation workflow.

Prerequisites:
- V15-CONV-001

Acceptance Criteria:
- New v1.5 services have isolated unit tests with infrastructure fakes.
- The documented backend test command runs without external databases.
- Existing in-memory graph and vector test doubles implement all current repository abstract methods, including `delete_document`.

Next:
V15-INTENT-001

---

## V15-INTENT-001

Title: Query Intent Detection

Objective:
Classify supported industrial query intents before retrieval, following `05_RETRIEVAL_ENGINE.md` Stage 1.

Prerequisites:
- V15-TEST-001

Acceptance Criteria:
- Intent is represented in the retrieval context.
- Classification is testable and does not let the LLM query storage directly.

Next:
V15-ASSET-001

---

## V15-ASSET-001

Title: Asset Detection

Objective:
Resolve query-referenced assets through the graph before graph expansion, following `05_RETRIEVAL_ENGINE.md` Stage 2.

Prerequisites:
- V15-INTENT-001

Acceptance Criteria:
- Known assets are detected with deterministic, traceable candidates.
- Unknown or ambiguous assets preserve the existing safe retrieval fallback.

Next:
V15-IMG-ARCH-001

---

## V15-IMG-ARCH-001

Title: Image Ingestion Architecture Approval

Objective:
Resolve the image-ingestion architecture before implementation because the Version 1 proposal introduces OpenCV and vision-model processing not yet locked by the core architecture.

Prerequisites:
- V15-ASSET-001

Status:
- Requires explicit architecture approval before code is written.

Decision Required:
- Vision provider/model, image preprocessing scope, P&ID symbol-recognition approach, supported image formats, safety/cost controls, and the canonical `DocumentContent` representation for image evidence.

Next:
V15-IMG-001, after approval

---

## V15-IMG-001

Title: Image-to-Knowledge Ingestion MVP

Objective:
Add approved image parsing to the existing ingestion pipeline and preserve original-image storage and provenance.

Prerequisites:
- V15-IMG-ARCH-001 approved

Acceptance Criteria:
- Image evidence follows the standard ingestion lifecycle and is traceable through citations.
- Existing PDF, DOCX, CSV, and XLSX ingestion remains unchanged.

Next:
V15-RANK-001

---

## V15-RANK-001

Title: Evidence Ranking

Objective:
Implement the explicit cross-source ranking stage defined in `05_RETRIEVAL_ENGINE.md` Stage 6.

Prerequisites:
- V15-ASSET-001

Acceptance Criteria:
- Ranking uses documented, explainable retrieval signals and does not alter citation provenance.
- Ranking behavior is covered by deterministic tests.

Next:
V15-POOL-001

---

## V15-POOL-001

Title: Connection Lifecycle Management

Objective:
Move database-client lifecycle management to application startup/shutdown while retaining dependency injection and compatibility with the current deployment model.

Prerequisites:
- V15-TEST-001

Acceptance Criteria:
- Clients are reused safely and released during shutdown.
- Health, ingestion, retrieval, and query behavior remain regression-tested.

Next:
V15-QUEUE-001

---

## V15-QUEUE-001

Title: RQ Ingestion Execution Review

Objective:
Restore Redis/RQ-backed ingestion where supported, retaining the documented Windows-compatible behavior for local development.

Prerequisites:
- V15-POOL-001

Acceptance Criteria:
- Deployment mode uses idempotent, retryable RQ jobs.
- Local Windows development retains a documented, tested compatible execution path.

Next:
V15-SANDBOX-ARCH-001

---

## V15-SANDBOX-ARCH-001

Title: Calculation Sandbox Security Approval

Objective:
Resolve the execution-isolation design before writing calculation code, because the Version 1 proposal introduces untrusted code execution and new security dependencies.

Prerequisites:
- V15-RANK-001

Status:
- Requires explicit architecture and security approval before code is written.

Decision Required:
- Isolation runtime, operating-system limits, dependency allowlist, network/filesystem controls, audit trail, and failure behavior.

Next:
V15-SANDBOX-001, after approval

---

## V15-SANDBOX-001

Title: Deterministic Calculation Service

Objective:
Implement the approved calculation path and pass computed, auditable results into the generation context.

Prerequisites:
- V15-SANDBOX-ARCH-001 approved

Next:
Future Version 1.5 maintenance work or explicitly approved Version 3 drafting work

---

# Rule

Never move to the next task until the current task:
- Builds successfully
- Passes evaluation
- Is committed to Git
- Is documented if needed
