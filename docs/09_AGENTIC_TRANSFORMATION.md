# Agentic Transformation — Architecture Document

> **Version:** 1.0.0
> **Status:** Living Architecture Specification
> **Created:** 2026-10-08
> **Phase:** Pre-implementation (inspection complete)

---

## 1. Objective

Transform OmniOps from a **single-shot RAG pipeline** into a **genuine tool-using, stateful, multi-step agentic system**.

The current system executes:

```text
Retrieve → Format → LLM → Validate → Return
```

The target system executes:

```text
User → Agent Orchestrator → Llama 3.2
  → DECIDE tool
  → CALL tool
  → EXECUTE
  → RETURN result
  → UPDATE agent state
  → REASON again
  → NEXT tool or FINAL answer
```

The LLM decides what happens next. Not the hardcoded pipeline.

---

## 2. Starting Architecture (Current State)

### Query Pipeline (traced from source)

```text
POST /query/stream                          [api/routes/query.py:62]
    │
    ▼
QueryOrchestrator.answer_query()            [query/orchestrator.py:34]
    │
    ├── RetrievalService.retrieve()         [retrieval/service.py:47]
    │     ├── IntentDetector.detect()       deterministic, regex
    │     ├── AssetDetector.detect()        deterministic, graph
    │     ├── Qdrant vector search          ThreadPoolExecutor
    │     ├── Neo4j graph search            ThreadPoolExecutor
    │     └── EvidenceRanker.rank()         deterministic
    │
    ├── ChatRepository.get_recent_messages() [database/chat_repository.py]
    │
    ├── PromptBuilder.build()               [generation/prompt_builder.py:29]
    │
    ├── OpenRouterLLMProvider.generate()    [generation/openrouter_provider.py:55]
    │     └── SINGLE HTTP POST, no tools param
    │
    └── AnswerValidator.validate()          [generation/validator.py:25]
```

### Critical Gaps

- **No LangGraph** — not installed, not referenced
- **No tool registry** — no @tool, no ToolNode
- **No function calling** — LLM payload has no tools parameter
- **No agent loop** — LLM called exactly once per query
- **No agent state** — no accumulator for tool results
- **No re-reasoning** — no loop sends results back to LLM
- **agents/** directory contains only .gitkeep
- **llm/** directory contains only .gitkeep
- **workers/** directory contains only .gitkeep

---

## 3. Target Architecture

```text
                          USER
                            │
                            ▼
                   ┌────────────────┐
                   │   FastAPI API  │
                   └───────┬────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  AgentOrchestrator  │
                │  (agent loop)       │
                └────────┬────────────┘
                         │
                    ┌────┴────┐
                    ▼         ▼
              ┌──────────┐ ┌──────────────┐
              │ Llama3.2 │ │ ToolExecutor │
              │ Reasoner │ │ (dispatch)   │
              └────┬─────┘ └──────┬───────┘
                   │              │
              Tool Call     ┌─────┴──────┐
                   │        │ToolRegistry│
       ┌───────┬───┴──┬────┤            │
       ▼       ▼      ▼    └────────────┘
   ┌───────┐ ┌─────┐ ┌──────┐ ┌────────┐ ┌───────┐
   │Search │ │Graph│ │Calc  │ │Analyze │ │P&ID   │
   │Docs   │ │Query│ │ulate │ │Image   │ │Analyze│
   └───┬───┘ └──┬──┘ └──┬───┘ └───┬────┘ └───┬───┘
       │        │       │         │           │
       └────────┴───────┴─────────┴───────────┘
                         │
                    Tool Result
                         │
                    AgentState update
                         │
                    Llama re-reason
                         │
              Another tool OR Final Answer
```

---

## 4. Model Architecture

| Role | Model | Runtime | Status |
|------|-------|---------|--------|
| Reasoning / Planning / Tool Selection | llama3.2 | Ollama | VERIFIED installed |
| Vision / Image Analysis | gemma3:4b | Ollama | NOT INSTALLED — must ollama pull gemma3:4b |
| Embeddings | all-MiniLM-L6-v2 | SentenceTransformer (in-process) | VERIFIED configured |

### gemma4:e2b References (must change to gemma3:4b)

| Location | Current Value |
|---|---|
| config/settings.py:115 (VisionSettings) | gemma4:e2b |
| config/settings.py:128 (ModelRegistry) | gemma4:e2b |
| .env:68 | gemma4:e2b |
| generation/vision_provider.py:42 | gemma4:e2b |
| services/model_router.py:35 | gemma4:e2b |
| docs/07_IMAGE_INGESTION_ARCHITECTURE.md | multiple refs |
| docs/08_CALCULATION_SANDBOX_ARCHITECTURE.md:100 | gemma4:e2b |
| tests/test_image_pipeline.py | 15+ refs |

---

## 5. Infrastructure Topology

### Verified Topology

```text
Windows Host
 ├── Ollama (native Windows process)
 │    └── localhost:11434
 │    └── Models: llama3.2 (installed)
 │
 └── Docker Desktop
      ├── omniops-api
      ├── omniops-worker
      ├── omniops-postgres
      ├── omniops-neo4j
      ├── omniops-redis
      ├── omniops-qdrant
      └── omniops-frontend
```

### Docker to Ollama Connectivity

```text
Container → host.docker.internal:11434
```

**Evidence:**
- docker-compose.yml:49: OPENROUTER_BASE_URL = http://host.docker.internal:11434/v1
- Ollama runs natively on Windows host (verified via ollama list)

### Vision Model Connectivity Gap

Current .env sets OLLAMA_BASE_URL=http://localhost:11434 which works for local dev but NOT from Docker.
docker-compose.yml does NOT set OLLAMA_BASE_URL for containers.

**Action:** Add OLLAMA_BASE_URL=http://host.docker.internal:11434 to docker-compose api/worker env.

---

## 6. Ollama Tool Calling API

### VERIFIED: Llama 3.2 supports native tool calling

**Endpoint:** POST /api/chat

**Request:**
```json
{
  "model": "llama3.2",
  "messages": [...],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "tool_name",
        "description": "...",
        "parameters": { "type": "object", "properties": {...} }
      }
    }
  ],
  "stream": false
}
```

**Response with tool call:**
```json
{
  "message": {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      { "function": { "name": "...", "arguments": {...} } }
    ]
  }
}
```

**Tool result submission:** Send role=tool message with result content.

### Adapter Required

Current providers do NOT support tool calling:
- OllamaLLMProvider uses /api/generate (no tools)
- OpenRouterLLMProvider uses /v1/chat/completions (no tools param sent)

**New component:** OllamaAgentProvider using /api/chat with tools parameter.

---

## 7. Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent framework | Custom agent loop (no LangGraph) | Avoids unnecessary dependency; Ollama native tool calling sufficient |
| Tool calling API | Ollama /api/chat with tools param | Native Llama 3.2 support; verified |
| Agent state | Custom AgentState dataclass | Lightweight, no dependencies |
| Tool interface | Abstract Tool base class | Standard pattern, composable |
| Tool registry | Dictionary-based ToolRegistry | Simple, testable |
| Vision model | gemma3:4b (dev) | 4GB VRAM constraint |
| Model concurrency | Sequential | 4GB VRAM; Ollama manages lifecycle |
| LLM provider | New OllamaAgentProvider alongside existing | Existing providers preserved |

---

## 8. Agent State Design

```python
@dataclass
class AgentState:
    conversation_id: str
    user_query: str
    messages: list[dict]          # Full message history for LLM
    tool_calls: list[dict]        # History of tool invocations
    tool_results: list[ToolResult]
    iteration_count: int
    max_iterations: int           # default: 8
    started_at: float
    timeout_seconds: float        # default: 120
    final_answer: str | None
    error: str | None
```

---

## 9. Agent Loop Design

```text
initialize state
while iteration < max_iterations:
    call Llama with tools
    if final answer → return
    if tool_calls → execute each → update state → continue
    if error → handle gracefully
safety: max iterations reached → fallback
```

### Safety Controls

| Control | Default | Env Var |
|---|---|---|
| Max iterations | 8 | AGENT_MAX_ITERATIONS |
| Timeout | 120s | AGENT_TIMEOUT_SECONDS |
| Duplicate tool detection | Enabled | — |
| Tool error tolerance | 2 consecutive → fallback | — |

---

## 10. Connector Map

| Capability | Service | Agent Connector | Status |
|---|---|---|---|
| Vector Search | Qdrant | `SearchDocumentsTool` | CONNECTED |
| Graph Search | Neo4j | Not connected | DISCONNECTED |
| Python Sandbox | calculation/ | Not connected | DISCONNECTED |
| Vision Provider | generation/ | Not connected | DISCONNECTED |
| P&ID Parser | parser/ | Not connected | DISCONNECTED |
| Conversation | database/ | Auto (hardcoded) | HARDCODED |
| Tool Registry | agents/tool_registry.py | ToolRegistry | COMPLETE |
| Agent State | agents/state.py | AgentState | COMPLETE |
| Agent Loop | agents/orchestrator.py | AgentOrchestrator | COMPLETE |

---

## 11. Roadmap

| Task ID | Title | Dependencies | Status |
|---|---|---|---|
| AGENT-ARCH-001 | Agent Foundation | None | COMPLETE |
| AGENT-OLLAMA-001 | Ollama Tool Calling Adapter | AGENT-ARCH-001 | COMPLETE |
| AGENT-CORE-001 | Minimal Agent Loop Proof | AGENT-OLLAMA-001 | COMPLETE |
| AGENT-RAG-001 | SearchDocuments Tool | AGENT-CORE-001 | COMPLETE |
| AGENT-GRAPH-001 | SearchKnowledgeGraph Tool | AGENT-CORE-001 | NEXT |
| AGENT-CALC-001 | Calculate Tool | AGENT-CORE-001 | NOT STARTED |
| AGENT-VISION-001 | AnalyzeImage Tool | AGENT-CORE-001 | NOT STARTED |
| AGENT-PID-001 | AnalyzePID Tool | AGENT-VISION-001 | NOT STARTED |
| AGENT-MULTI-001 | Multi-tool Orchestration | AGENT-RAG-001, AGENT-CALC-001 | NOT STARTED |
| AGENT-MEMORY-001 | Agent Memory | AGENT-MULTI-001 | NOT STARTED |
| AGENT-E2E-001 | End-to-End Validation | ALL above | NOT STARTED |

---

## 12. Hardware Limitations

| Constraint | Value | Impact |
|---|---|---|
| GPU | RTX 3050 Laptop | 4GB VRAM |
| VRAM | 4 GB | Cannot run llama3.2 + gemma3:4b simultaneously |
| RAM | 24 GB | Adequate |
| Ollama model management | Automatic load/unload | Sequential tool execution preferred |

---

## 13. Continuation Instructions

A future coding agent must:
1. Read this document first
2. Check task status in 00_TASK_MASTER.md
3. Never bypass ToolExecutor
4. Never bypass ToolRegistry
5. Never remove existing tests
6. Never change model defaults without updating ALL locations (Section 4)
7. Never introduce cloud APIs
8. Test each task independently
9. Update this document after each completed task

### What Must Not Change
- Existing ingestion pipeline
- Existing retrieval service internals
- Existing calculation sandbox internals
- Existing PostgreSQL schema
- Existing Neo4j graph schema
- Docker Compose service topology
- Existing test suites (except model name updates)
