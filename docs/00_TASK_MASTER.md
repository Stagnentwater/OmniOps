# 00_TASK_MASTER.md

# OmniOps Development Task Master
Version: 3.0.0
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

Current Phase: Phase 17 — Version 3: Authentication, User Profiles, and Persona-Aware Intelligence (COMPLETE)

Current Sprint: Sprint 17.5 — Security Audit & Full Regression Suite Verification (COMPLETE)

Current Task: ALL PHASE 17 TASKS COMPLETE (611 tests passing)

Roadmap Source:
- `Docs/version 3.md` is the architecture blueprint and implementation specification for Version 3.
- `docs/09_AGENTIC_TRANSFORMATION.md` was the architecture specification for Phase 16 (complete).
- `docs/Version1.md` was the roadmap for Version 1.5 (all V15 P1 tasks complete).
- `docs/06_VERSION_2_DESC.md` is explicitly deferred.

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
- [x] V15-TEST-001
- [x] V15-INTENT-001
- [x] V15-ASSET-001
- [x] V15-IMG-ARCH-001 (Architecture approved — see docs/07_IMAGE_INGESTION_ARCHITECTURE.md)
- [x] V15-IMG-001
- [x] V15-RANK-001
- [x] V15-POOL-001
- [x] V15-QUEUE-001
- [x] V15-SANDBOX-ARCH-001 (Architecture approved — see docs/08_CALCULATION_SANDBOX_ARCHITECTURE.md)
- [x] V15-SANDBOX-001
- [x] AGENT-ARCH-001
- [x] AGENT-OLLAMA-001
- [x] AGENT-CORE-001
- [x] AGENT-RAG-001
- [x] AGENT-GRAPH-001
- [x] AGENT-CALC-001
- [x] AGENT-VISION-001
- [x] AGENT-PID-001
- [x] AGENT-MULTI-001
- [x] AGENT-MEMORY-001
- [x] AGENT-E2E-001
- [x] V3-PLAN-001 (Architecture Blueprint & Taskmaster Integration — Docs/version 3.md created)
- [x] V3-REGRESS-001 (Baseline Regression & Environment Verification — 537 tests passed)
- [x] V3-SCHEMA-001 (PostgreSQL User & Profile Schema Architecture — UserRepository & omniops container verified)
- [x] V3-AUTH-BE-001 (Backend Authentication Service & Cryptography — PBKDF2 & JWT token service)
- [x] V3-AUTH-API-001 (FastAPI Authentication Routes — /auth/register, /auth/login, /auth/me)

- [x] V3-PROF-API-001 (User Profile API & Ownership Enforcement — /profile)
- [x] V3-AUTH-FE-001 (Frontend Authentication State, Modal/Forms, and Token Interceptor)
- [x] V3-PROF-FE-001 (Frontend Profile Settings View & Navigation Integration)
- [x] V3-PERSONA-BLD-001 (Persona Context Builder & Prompt Synthesizer)
- [x] V3-PERSONA-AGENT-001 (Agent Orchestrator Persona Integration)
- [x] V3-PERSONA-LEGACY-001 (Legacy Query Orchestrator & PromptBuilder Persona Integration)
- [x] V3-CHAT-ISOL-001 (Chat Session User Affiliation & Ownership Isolation)
- [x] V3-DEMO-E2E-001 (Two-Persona Demonstration & Evaluation Benchmark)
- [x] V3-SEC-REGRESS-001 (Security Audit & Full Regression Suite Verification — 611 tests passed)

Pending Tasks (Version 3):
- None (All Phase 17 Version 3 tasks completed and verified)

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

Files to Create / Modify:
- `backend/tests/test_graph_repository.py`
- `backend/tests/test_retrieval.py`
- `backend/tests/test_vector_pipeline.py`
- `backend/TESTING.md`
- `docs/00_TASK_MASTER.md`

Acceptance Criteria:
- New v1.5 services have isolated unit tests with infrastructure fakes.
- The documented backend test command runs without external databases.
- Existing in-memory graph and vector test doubles implement all current repository abstract methods, including `delete_document`.

Evaluation:
- From `backend/`, run `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`.

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
AGENT-ARCH-001

---

# PHASE 16 — Agentic Transformation

Scope source: `docs/09_AGENTIC_TRANSFORMATION.md`. This phase transforms the single-shot RAG pipeline into a genuine tool-using, stateful, multi-step agentic system.

## AGENT-ARCH-001

Title: Agent Foundation

Objective:
Create the core agent abstractions: AgentState, Tool interface, ToolDefinition, ToolResult, ToolRegistry, ToolExecutor. Update vision model configuration from gemma4:e2b to gemma3:4b across all code locations. Add AgentSettings to configuration.

Prerequisites:
- V15-SANDBOX-001

Files to Create:
- `backend/agents/state.py`
- `backend/agents/tool_interface.py`
- `backend/agents/tool_registry.py`
- `backend/agents/tool_executor.py`
- `backend/agents/tools/__init__.py`
- `backend/tests/test_agent_foundation.py`

Files to Modify:
- `backend/agents/__init__.py`
- `backend/config/settings.py` (add AgentSettings, fix vision model defaults)
- `.env` (VISION_MODEL=gemma3:4b, add AGENT_* vars)
- `docker-compose.yml` (add OLLAMA_BASE_URL to api/worker)
- `backend/generation/vision_provider.py` (default gemma3:4b)
- `backend/services/model_router.py` (default gemma3:4b)

Acceptance Criteria:
- AgentState, Tool, ToolDefinition, ToolResult, ToolRegistry, ToolExecutor are importable
- ToolRegistry can register, get, list, and get_definitions for tools
- ToolExecutor dispatches tool calls to registered tools and returns ToolResult
- All gemma4:e2b defaults changed to gemma3:4b in code
- AgentSettings added with MAX_ITERATIONS, TIMEOUT_SECONDS
- OLLAMA_BASE_URL added to docker-compose api/worker environment
- Unit tests pass for all new abstractions
- Existing tests pass (with model name updates for test expectations)

Evaluation:
Run backend tests.

Commit:
feat(agent): add agent foundation abstractions

Next:
AGENT-OLLAMA-001

---

## AGENT-OLLAMA-001

Title: Ollama Tool Calling Adapter

Objective:
Create OllamaAgentProvider that uses Ollama's native /api/chat endpoint with the tools parameter. Verify Llama 3.2 tool calling works with real Ollama.

Prerequisites:
- AGENT-ARCH-001

Files to Create:
- `backend/agents/ollama_agent_provider.py`
- `backend/tests/test_ollama_agent_provider.py`

Acceptance Criteria:
- Provider sends tools definitions in /api/chat requests
- Provider parses tool_calls from Llama 3.2 responses
- Provider handles tool result messages (role: tool)
- Provider handles plain text responses (no tool call)
- Unit tests with mocked HTTP responses
- Integration test (if Ollama is accessible)

Commit:
feat(agent): add Ollama tool calling adapter

Next:
AGENT-CORE-001

---

## AGENT-CORE-001

Title: Minimal Agent Loop Proof

Objective:
Create AgentOrchestrator with the full agent loop. Prove the architecture works with a dummy test tool (get_current_time or similar).

Prerequisites:
- AGENT-OLLAMA-001

Files to Create:
- `backend/agents/orchestrator.py`
- `backend/agents/tools/system_status.py` (dummy tool for testing)
- `backend/tests/test_agent_orchestrator.py`

Acceptance Criteria:
- AgentOrchestrator executes: LLM → tool call → tool result → LLM → final answer
- Max iteration limit enforced
- Timeout enforced
- Duplicate tool call detection works
- Error handling works (tool failure → agent can recover)
- Streaming events emitted for tool execution stages

Commit:
feat(agent): implement agent orchestrator loop

Next:
AGENT-RAG-001

---

## AGENT-RAG-001

Title: SearchDocuments Tool

Objective:
Wrap existing RetrievalService (Qdrant vector search) as an agent-accessible tool.

Prerequisites:
- AGENT-CORE-001

Files to Create:
- `backend/agents/tools/search_documents.py`
- `backend/tests/test_tool_search_documents.py`

Acceptance Criteria:
- Tool wraps existing RetrievalService._retrieve_vectors
- Agent can decide to search and receives chunk results
- Existing retrieval internals unchanged

Commit:
feat(agent): add search_documents tool

Next:
AGENT-GRAPH-001

---

## AGENT-GRAPH-001

Title: SearchKnowledgeGraph Tool

Objective:
Wrap existing GraphQueryService as an agent-accessible tool.

Prerequisites:
- AGENT-CORE-001

Files to Create:
- `backend/agents/tools/search_graph.py`
- `backend/tests/test_tool_search_graph.py`

Acceptance Criteria:
- Tool wraps existing GraphQueryService search_nodes + expand_subgraph
- Agent can query graph and receive entity/relationship results
- Existing graph internals unchanged

Commit:
feat(agent): add search_knowledge_graph tool

Next:
AGENT-CALC-001

---

## AGENT-CALC-001

Title: Calculate Tool

Objective:
Wrap existing CalculationService and sandbox as an agent-accessible tool.

Prerequisites:
- AGENT-CORE-001

Files to Create:
- `backend/agents/tools/calculate.py`
- `backend/tests/test_tool_calculate.py`

Files to Modify:
- `backend/dependencies.py` (add CalculationService instantiation)

Acceptance Criteria:
- Tool wraps existing CalculationService
- Agent can request calculations and receive validated results
- Sandbox security preserved
- Existing calculation internals unchanged

Commit:
feat(agent): add calculate tool

Next:
AGENT-VISION-001

---

## AGENT-VISION-001

Title: AnalyzeImage Tool

Objective:
Create agent-accessible vision tool using VisionProvider with Gemma 3 4B.

Prerequisites:
- AGENT-CORE-001

Files to Create:
- `backend/agents/tools/analyze_image.py`
- `backend/tests/test_tool_analyze_image.py`

Acceptance Criteria:
- Tool wraps existing VisionProvider
- Uses configured vision model (gemma3:4b)
- Agent can request image analysis at query time
- Existing VisionProvider unchanged
- Works gracefully if vision model not installed (error reported, not crash)

Commit:
feat(agent): add analyze_image tool

Next:
AGENT-PID-001

---

## AGENT-PID-001

Title: AnalyzePID Tool

Objective:
Create structured P&ID analysis tool combining existing image parser with VisionProvider.

Prerequisites:
- AGENT-VISION-001

Files to Create:
- `backend/agents/tools/analyze_pid.py`
- `backend/tests/test_tool_analyze_pid.py`

Acceptance Criteria:
- Returns structured output (equipment, connections, labels, confidence)
- Uses existing P&ID prompt from image_parser.py
- Leverages VisionProvider for inference

Commit:
feat(agent): add analyze_pid tool

Next:
AGENT-MULTI-001

---

## AGENT-MULTI-001

Title: Multi-tool Orchestration

Objective:
Validate that the agent can chain multiple tools in sequence based on evolving state.

Prerequisites:
- AGENT-RAG-001
- AGENT-GRAPH-001
- AGENT-CALC-001

Files to Create:
- `backend/tests/test_agent_multi_tool.py`

Acceptance Criteria:
- Search → Calculate chain works
- Search → Graph chain works
- Agent selects tools based on results, not hardcoded sequence

Commit:
test(agent): validate multi-tool orchestration

Next:
AGENT-MEMORY-001

---

## AGENT-MEMORY-001

Title: Agent Conversation Memory

Objective:
Connect existing conversation history to agent state for multi-turn interactions.

Prerequisites:
- AGENT-MULTI-001

Files to Modify:
- `backend/agents/orchestrator.py`
- `backend/api/routes/query.py`

Acceptance Criteria:
- Agent receives prior conversation context
- Cross-turn references resolved
- Context limits respected

Commit:
feat(agent): integrate conversation memory

Next:
AGENT-E2E-001

---

## AGENT-E2E-001

Title: End-to-End Validation

Objective:
Full end-to-end testing of the agentic system.

Prerequisites:
- ALL AGENT tasks above

Files to Create:
- `backend/tests/test_agent_e2e.py`

Tests:
1. No-tool query ("Hello") → direct answer
2. Document query → SearchDocuments → answer
3. Calculation query → Calculate → answer
4. Search + Calculate chain
5. Vision query (if model available)
6. Multi-turn memory
7. Max iterations safety

Commit:
test(agent): end-to-end agent validation

Next:
V3-PLAN-001

---

# PHASE 17 — Version 3: Authentication, User Profiles, and Persona-Aware Intelligence

Roadmap Source: `Docs/version 3.md`  
Constraint: **ARCHITECTURE FREEZE IS IN EFFECT.** Implement every task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.

---

## V3-PLAN-001

**Title:** Version 3 Technical Blueprint and Taskmaster Integration

**Objective:**
Inspect the repository, define the Version 3 technical specification adhering strictly to the architecture freeze, create `Docs/version 3.md`, and integrate the dependency-aware implementation plan into `docs/00_TASK_MASTER.md`.

**Prerequisites:**
- AGENT-E2E-001

**Input:**
- Repository inspection findings
- `docs/01_CONTEXT.md`, `docs/02_SYSTEM_ARCHITECTURE.md`, `docs/09_AGENTIC_TRANSFORMATION.md`
- Frozen technology constraints

**Expected Output:**
- `Docs/version 3.md` containing all 20 required sections
- Updated `docs/00_TASK_MASTER.md` with honest starting state and actionable Phase 17 tasks

**Files to Create / Modify:**
- `Docs/version 3.md` (Created)
- `docs/00_TASK_MASTER.md` (Modified)

**Implementation Notes:**
- Architectural freeze strictly preserved: no code or schema modified.
- Planning and documentation only.

**Acceptance Criteria:**
- `Docs/version 3.md` exists and contains all 20 required sections.
- `docs/00_TASK_MASTER.md` incorporates Phase 17 without deleting any prior tasks.
- First actionable implementation task is explicitly identified.

**Evaluation:**
- Verify file existence, schema examples, prompt templates, and task integrity.

**Status:**
COMPLETED

**Suggested Commit Message:**
docs(v3): create Version 3 architecture blueprint and update taskmaster

**Next Task:**
V3-REGRESS-001

---

## V3-REGRESS-001

**Title:** Baseline Regression & Test Environment Verification

**Objective:**
Verify that the existing test suite (all 537 tests across unit, graph, calculation sandbox, and agent modules) executes and passes cleanly before writing any Version 3 code.

**Prerequisites:**
- V3-PLAN-001

**Input:**
- Existing test suite under `backend/tests/`

**Expected Output:**
- Clean execution run verifying 537 tests passing with 0 failures and 0 errors.

**Files to Create / Modify:**
- None (Verification task)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Run `.\.venv\Scripts\python.exe -m unittest discover -s tests` from `backend/`.

**Acceptance Criteria:**
- 100% of existing tests pass cleanly.
- Baseline output logged and verified.

**Evaluation:**
- Unittest exit code 0.

**Status:**
COMPLETED

**Suggested Commit Message:**
test(v3): verify baseline regression test pass

**Next Task:**
V3-SCHEMA-001

---

## V3-SCHEMA-001

**Title:** PostgreSQL User & Profile Schema Architecture

**Objective:**
Create `backend/database/user_repository.py` with `UserRepository` implementing `users` and `user_profiles` schema management via standard `psycopg` connection and `_ensure_tables`, following the exact pattern of `repositories.py` and `chat_repository.py`.

**Prerequisites:**
- V3-REGRESS-001

**Input:**
- Database design defined in `Docs/version 3.md` Section 8

**Expected Output:**
- `backend/database/user_repository.py`
- `backend/tests/test_user_repository.py`

**Files to Create / Modify:**
- `backend/database/user_repository.py` (Create)
- `backend/tests/test_user_repository.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Schema includes `users` (user_id TEXT PK, email TEXT UNIQUE, password_hash TEXT, is_active BOOLEAN, created_at, updated_at) and `user_profiles` (user_id TEXT PK FK, name TEXT, skill_set JSONB, designation TEXT, refinery_experience_level TEXT CHECK, preferred_explanation_depth TEXT CHECK, created_at, updated_at).
- Use `psycopg.connect(settings.postgres.dsn, row_factory=dict_row)`.

**Acceptance Criteria:**
- Tables created idempotently via `_ensure_tables`.
- CRUD operations for users and profiles succeed.
- Foreign key cascade delete verified.
- Unit tests pass with mock PostgreSQL connection / test doubles.

**Evaluation:**
- `python -m unittest tests.test_user_repository` passes.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(database): implement user and profile repository schema

**Next Task:**
V3-AUTH-BE-001

---

## V3-AUTH-BE-001

**Title:** Backend Authentication Service & Cryptography

**Objective:**
Implement `backend/services/auth_service.py` to handle password hashing, password verification, token generation, and token decoding/validation.

**Prerequisites:**
- V3-SCHEMA-001

**Input:**
- Auth specifications from `Docs/version 3.md` Section 6

**Expected Output:**
- `backend/services/auth_service.py`
- `backend/tests/test_auth_service.py`

**Files to Create / Modify:**
- `backend/services/auth_service.py` (Create)
- `backend/config/settings.py` (Modify — add AuthSettings)
- `backend/tests/test_auth_service.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Password hashing using salted cryptographic hashing (PBKDF2-HMAC-SHA256 with 600,000 iterations or approved Argon2id).
- Tokens include user ID (`sub`), email, issued-at (`iat`), and expiration (`exp`).

**Acceptance Criteria:**
- Correct password verification returns True; incorrect returns False.
- Generated tokens decode successfully before expiration.
- Expired or tampered tokens raise structured authentication exceptions.

**Evaluation:**
- `python -m unittest tests.test_auth_service` passes.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(auth): implement backend password hashing and token validation service

**Next Task:**
V3-AUTH-API-001

---

## V3-AUTH-API-001

**Title:** FastAPI Authentication Routes (/auth/register, /auth/login, /auth/me)

**Objective:**
Implement authentication endpoints in `backend/api/routes/auth.py` and register with `backend/main.py`. Provide dependency `get_current_user` in `backend/dependencies.py`.

**Prerequisites:**
- V3-AUTH-BE-001

**Input:**
- API contracts from `Docs/version 3.md` Section 9

**Expected Output:**
- `backend/api/routes/auth.py`
- Route registrations in `backend/main.py`
- Authentication dependency in `backend/dependencies.py`
- Unit tests in `backend/tests/test_auth_api.py`

**Files to Create / Modify:**
- `backend/api/routes/auth.py` (Create)
- `backend/dependencies.py` (Modify)
- `backend/main.py` (Modify)
- `backend/tests/test_auth_api.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- `POST /auth/register`: Validates email, hashes password, inserts user & profile, returns token.
- `POST /auth/login`: Validates credentials, returns token.
- `GET /auth/me`: Requires Bearer token via `Depends(get_current_user)`, returns current user.

**Acceptance Criteria:**
- Registration with valid data returns 201 and token.
- Duplicate email returns 409 Conflict.
- Login with incorrect password returns 401 Unauthorized.
- Unauthenticated access to `/auth/me` returns 401.

**Evaluation:**
- FastAPI TestClient tests pass.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(api): add user registration, login, and me endpoints

**Next Task:**
V3-PROF-API-001

---

## V3-PROF-API-001

**Title:** User Profile API & Authorization Enforcement (/profile)

**Objective:**
Implement profile retrieval and update endpoints in `backend/api/routes/profile.py`, enforcing user ownership checks so users can only view and update their own profile.

**Prerequisites:**
- V3-AUTH-API-001

**Input:**
- Profile contracts from `Docs/version 3.md` Section 9

**Expected Output:**
- `backend/api/routes/profile.py`
- Unit tests in `backend/tests/test_profile_api.py`

**Files to Create / Modify:**
- `backend/api/routes/profile.py` (Create)
- `backend/main.py` (Modify)
- `backend/tests/test_profile_api.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- `GET /profile`: returns profile for `current_user.user_id`.
- `PUT /profile`: validates `refinery_experience_level` and `preferred_explanation_depth`, updates fields, updates `updated_at`, returns updated profile.

**Acceptance Criteria:**
- Authenticated user can fetch their own profile.
- Updates to designation, skills, experience level, and explanation depth persist.
- Invalid experience level returns 422 Unprocessable Entity.
- Unauthenticated requests return 401.

**Evaluation:**
- API unit tests pass.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(api): implement user profile retrieval and update endpoints

**Next Task:**
V3-AUTH-FE-001

---

## V3-AUTH-FE-001

**Title:** Frontend Authentication State, Modal/Forms, and Token Interceptor

**Objective:**
Add authentication UI to the Next.js frontend, including sign-in and registration forms, session persistence in localStorage, and automatic Authorization header injection in `ApiClient`.

**Prerequisites:**
- V3-PROF-API-001

**Input:**
- UI specifications from `Docs/version 3.md` Section 10

**Expected Output:**
- `frontend/src/components/AuthModal.tsx`
- Updated `frontend/src/services/api.ts`
- Updated `frontend/src/app/page.tsx`

**Files to Create / Modify:**
- `frontend/src/components/AuthModal.tsx` (Create)
- `frontend/src/services/api.ts` (Modify)
- `frontend/src/app/page.tsx` (Modify)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Style using the existing dark industrial palette (`--color-surface`, `--color-border`, `--color-accent`).
- Store token securely in `localStorage` (`omniops_auth_token`).
- `ApiClient.request` and `ApiClient.queryStream` attach `Authorization: Bearer <token>`.
- On 401 responses, clear token and display login modal.

**Acceptance Criteria:**
- User can enter credentials and log in.
- Token persisted across page refreshes.
- Logout clears token and resets session state.
- Unauthorized requests cleanly trigger re-authentication.

**Evaluation:**
- Manual browser verification and frontend lint check (`npm run lint`).

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(ui): add authentication modal and token interceptor

**Next Task:**
V3-PROF-FE-001

---

## V3-PROF-FE-001

**Title:** Frontend Profile Settings View & Navigation Integration

**Objective:**
Create `frontend/src/components/ProfileView.tsx` and integrate it into `NavRail.tsx` and `page.tsx` so users can edit their designation, skills, experience level, and explanation depth preference.

**Prerequisites:**
- V3-AUTH-FE-001

**Input:**
- Profile design from `Docs/version 3.md` Section 10

**Expected Output:**
- `frontend/src/components/ProfileView.tsx`
- Updated `frontend/src/components/NavRail.tsx`
- Updated `frontend/src/app/page.tsx`

**Files to Create / Modify:**
- `frontend/src/components/ProfileView.tsx` (Create)
- `frontend/src/components/NavRail.tsx` (Modify)
- `frontend/src/app/page.tsx` (Modify)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Form controls for `name`, `designation`, `skill_set` (tag editor), `refinery_experience_level` (radio selector: Beginner / Intermediate / Advanced / Expert), and `preferred_explanation_depth` (radio selector: Concise / Moderate / Detailed).
- Save action calls `PUT /profile` via `ApiClient.updateProfile()`.
- Visual feedback on save and error handling.

**Acceptance Criteria:**
- Navigating to "Profile" shows the current user profile.
- Updating fields and clicking Save updates the backend.
- Reloading the page reflects the updated values.

**Evaluation:**
- Manual browser test and Next.js lint pass.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(ui): add profile settings view and navigation rail item

**Next Task:**
V3-PERSONA-BLD-001

---

## V3-PERSONA-BLD-001

**Title:** Persona Context Builder & Prompt Synthesizer

**Objective:**
Implement `backend/generation/persona_builder.py` with `PersonaContextBuilder` to convert a validated `UserProfile` into authoritative, structured system directives for the LLM.

**Prerequisites:**
- V3-PROF-FE-001

**Input:**
- Persona builder design from `Docs/version 3.md` Section 11

**Expected Output:**
- `backend/generation/persona_builder.py`
- `backend/tests/test_persona_builder.py`

**Files to Create / Modify:**
- `backend/generation/persona_builder.py` (Create)
- `backend/tests/test_persona_builder.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Generates distinct communication instructions for each experience level:
  - Beginner: explain foundational mechanisms, define acronyms, step-by-step reasoning.
  - Expert: concise, direct, high-density terminology, zero remedial definitions.
- Enforces non-negotiable safety guardrails: never omit hazardous material warnings or Lockout/Tagout procedures.
- Enforces evidence grounding: facts must come from retrieved context.

**Acceptance Criteria:**
- Returns properly structured string with user metadata and role rules.
- Safely handles missing or empty profile attributes using default persona.
- Sanitizes user strings to prevent prompt injection.

**Evaluation:**
- `python -m unittest tests.test_persona_builder` passes.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(generation): implement persona context builder with safety rules

**Next Task:**
V3-PERSONA-AGENT-001

---

## V3-PERSONA-AGENT-001

**Title:** Agent Orchestrator Persona Integration

**Objective:**
Extend `AgentOrchestrator` in `backend/agents/orchestrator.py` and `POST /query/stream` in `backend/api/routes/query.py` so the agentic loop incorporates the authenticated user's persona directives into its system instructions.

**Prerequisites:**
- V3-PERSONA-BLD-001

**Input:**
- Query pipeline and persona integration design from `Docs/version 3.md` Section 11

**Expected Output:**
- Updated `backend/agents/orchestrator.py`
- Updated `backend/api/routes/query.py`
- Unit tests in `backend/tests/test_agent_persona.py`

**Files to Create / Modify:**
- `backend/agents/orchestrator.py` (Modify)
- `backend/api/routes/query.py` (Modify)
- `backend/tests/test_agent_persona.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- In `api/routes/query.py`, require `current_user = Depends(get_current_user)`.
- Fetch `user_profile = user_repo.get_profile(current_user.user_id)`.
- Generate `persona_instructions = PersonaContextBuilder.build(user_profile)`.
- Pass `persona_instructions` to `agent_orchestrator.run()`.
- Inside `AgentOrchestrator.run()`, combine `self._system_prompt` and `persona_instructions` into the initial system message.

**Acceptance Criteria:**
- Authenticated requests pass persona directives into the agent prompt.
- Agent activities stream correctly over SSE.
- Changes to user profile immediately alter subsequent query answers without application restart.

**Evaluation:**
- `python -m unittest tests.test_agent_persona` passes.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(agent): inject authenticated user persona into agent orchestrator

**Next Task:**
V3-PERSONA-LEGACY-001

---

## V3-PERSONA-LEGACY-001

**Title:** Legacy Query Orchestrator & PromptBuilder Persona Integration

**Objective:**
Extend `PromptBuilder` in `backend/generation/prompt_builder.py` and `QueryOrchestrator` in `backend/query/orchestrator.py` so the non-agentic fallback RAG pipeline also respects the authenticated user's persona.

**Prerequisites:**
- V3-PERSONA-AGENT-001

**Input:**
- PromptBuilder specifications from `Docs/version 3.md` Section 11

**Expected Output:**
- Updated `backend/generation/prompt_builder.py`
- Updated `backend/query/orchestrator.py`
- Unit tests in `backend/tests/test_legacy_persona.py`

**Files to Create / Modify:**
- `backend/generation/prompt_builder.py` (Modify)
- `backend/query/orchestrator.py` (Modify)
- `backend/tests/test_legacy_persona.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Add optional `persona_instructions` parameter to `PromptBuilder.build()`.
- Inject persona instructions into the system prompt block of `PromptPackage`.

**Acceptance Criteria:**
- Legacy RAG query execution correctly applies persona directives.
- Citations `[Context #N]` continue to be resolved deterministically.

**Evaluation:**
- `python -m unittest tests.test_legacy_persona` passes.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(query): integrate persona directives into legacy prompt builder

**Next Task:**
V3-CHAT-ISOL-001

---

## V3-CHAT-ISOL-001

**Title:** Chat Session User Affiliation & Ownership Isolation

**Objective:**
Link `chat_sessions` to `user_id` in PostgreSQL and enforce ownership in `backend/api/routes/chat.py` and `backend/database/chat_repository.py` so users only access their own chat history.

**Prerequisites:**
- V3-PERSONA-LEGACY-001

**Input:**
- Database design from `Docs/version 3.md` Section 8

**Expected Output:**
- Updated `backend/database/chat_repository.py`
- Updated `backend/api/routes/chat.py`
- Unit tests in `backend/tests/test_chat_isolation.py`

**Files to Create / Modify:**
- `backend/database/chat_repository.py` (Modify)
- `backend/api/routes/chat.py` (Modify)
- `backend/tests/test_chat_isolation.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- `_ensure_tables` adds `user_id TEXT` column to `chat_sessions` if not exists.
- `create_session(user_id=...)` records owning user.
- `list_sessions(user_id=...)` filters by `user_id`.
- `get_messages` and `delete_session` verify ownership before returning or deleting.

**Acceptance Criteria:**
- User A cannot view, access, or delete User B's chat sessions.
- Unauthenticated chat session requests return 401.

**Evaluation:**
- Unit tests pass.

**Status:**
COMPLETED

**Suggested Commit Message:**
feat(chat): associate chat sessions with authenticated user and enforce ownership

**Next Task:**
V3-DEMO-E2E-001

---

## V3-DEMO-E2E-001

**Title:** Two-Persona Demonstration & Evaluation Benchmark

**Objective:**
Implement and execute the reproducible two-persona verification test defined in `Docs/version 3.md` Section 12, validating that Beginner and Expert users receive tailored responses to the identical heat exchanger question.

**Prerequisites:**
- V3-CHAT-ISOL-001

**Input:**
- Demonstration question: *"Why is a pressure drop observed across a heat exchanger, and what should be checked to investigate it?"*
- Persona A: Alex Chen (Graduate Trainee, Beginner, Detailed)
- Persona B: Dr. Marcus Vance (Senior Process Engineer, Expert, Concise)

**Expected Output:**
- Test script `backend/tests/test_two_persona_demonstration.py`
- Evaluation results verifying the 7 comparison dimensions (definitions, length, technical depth, grounding, facts, diagnostics, safety)

**Files to Create / Modify:**
- `backend/tests/test_two_persona_demonstration.py` (Create)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Both users query the exact same knowledge base with identical retrieval settings.
- Verify that Beginner answer contains foundational explanations and acronym definitions.
- Verify that Expert answer is concise, high-density, and omits basic definitions.
- Verify that both answers retain mandatory safety precautions.

**Acceptance Criteria:**
- Test passes automatically and outputs side-by-side comparison.
- All 7 evaluation criteria from the Section 12 matrix are satisfied.

**Evaluation:**
- `python -m unittest tests.test_two_persona_demonstration` passes.

**Status:**
COMPLETED

**Suggested Commit Message:**
test(v3): implement automated two-persona evaluation benchmark

**Next Task:**
V3-SEC-REGRESS-001

---

## V3-SEC-REGRESS-001

**Title:** Security Audit & Full Regression Suite Verification

**Objective:**
Execute the full test suite including all 537 existing regression tests and all new Version 3 tests, verify no secrets are logged or leaked, and complete the final acceptance checklist.

**Prerequisites:**
- V3-DEMO-E2E-001

**Input:**
- Entire backend and frontend test suites

**Expected Output:**
- 100% test pass rate across all suites.
- Verified absence of security regressions.

**Files to Create / Modify:**
- None (Verification task)

**Implementation Notes:**
- Mandatory constraint: Implement this task by extending the existing VigilOps architecture. Do not redesign, replace, migrate, or refactor unrelated architectural components. Any architectural change requires explicit prior approval from the project owner.
- Run `.\.venv\Scripts\python.exe -m unittest discover -s tests` from `backend/`.
- Run frontend lint: `npm run lint` from `frontend/`.
- Verify that passwords, tokens, and confidential keys are redacted in all logs.

**Acceptance Criteria:**
- All 537 original regression tests pass without regression.
- All new Phase 17 unit and integration tests pass.
- Architecture freeze confirmed intact.

**Evaluation:**
- Complete test suite passes with zero failures.

**Status:**
COMPLETED

**Suggested Commit Message:**
test(v3): execute final security audit and complete regression verification

**Next Task:**
None (Version 3 Complete)

---

# Rule

Never move to the next task until the current task:
- Builds successfully
- Passes evaluation
- Is committed to Git
- Is documented if needed

