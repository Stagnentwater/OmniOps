# 10. Agent Activity Stream & Live Tool/Code Visibility Architecture

## 1. Overview

OmniOps replaces legacy static pipeline visualizations (Retrieval → Graph → Calculation → Answer) with a **dynamic, ChatGPT-style Agent Activity Stream**. 

In this architecture, the agent dynamically decides which tools to invoke (or invoke none for conversational prompts). The user interface renders real-time, user-safe activity events accompanied by collapsible, verifiable tool artifacts (such as sandboxed Python calculation code).

---

## 2. Privacy & Confidentiality Rules

| Category | Storage / Streaming Rule |
| :--- | :--- |
| **Raw Model Chain-of-Thought** | **NOT STORED / NOT STREAMED**<br>Private internal deliberation tokens and hidden reasoning are never captured or sent to the client. |
| **User-Safe Activity Summaries** | **STREAMED & PERSISTED**<br>Concise execution state descriptions (e.g. *"Searching technical documents...", "Analyzing P&ID diagram..."*) are emitted by the runtime. |
| **Tool Outputs & Metrics** | **STREAMED & PERSISTED**<br>Sanitized metrics (chunk counts, entity counts, calculation result values) are displayed. |
| **Python Calculation Artifacts** | **SHOWN AS ARTIFACT / PERSISTED**<br>Exact deterministic code executed in the calculation sandbox is visible in collapsible blocks. |
| **Secrets & Credentials** | **REDACTED AT SOURCE**<br>Tool argument values containing API keys, passwords, or tokens are sanitized before emission. |

---

## 3. Agent Event Contract

Every activity event conforms to the following JSON schema emitted over the existing SSE streaming bus:

```json
{
  "stage": "TOOL_EXECUTING",
  "type": "tool_started",
  "event_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "execution_id": "ab18a26a-c192-434e-ae7d-554eb89b83d0",
  "timestamp": 1775638421.24,
  "status": "running",
  "message": "Searching technical documents for 'P-101 pressure'...",
  "tool": "search_documents",
  "metadata": {
    "arguments": {
      "query": "P-101 pressure"
    }
  }
}
```

### Event Types

- `agent_started`: Initial query analysis (`"Analyzing request..."`).
- `reasoning_summary`: Intermediate synthesis step (`"Synthesizing findings (step 2)..."`).
- `tool_started`: Start of tool execution with sanitized query/entity targets.
- `tool_completed`: Successful tool execution with concise metrics (chunks, nodes, tags).
- `tool_failed`: Error message on tool execution failure.
- `code_generated`: Python code generated for calculation sandbox.
- `code_execution_started`: Notification of sandbox execution start.
- `code_execution_completed`: Sandbox execution finished with execution time and result value.
- `final_answer_started`: Transition to answer generation (`"Preparing final response..."`).
- `agent_completed`: Terminal completion event.

---

## 4. Streaming Transport & Event Flow

```
AgentOrchestrator
       │  emit(stage, payload)
       ▼
 FastAPI /query/stream (SSE)
       │  bus.publish(f"query_{session_id}", event)
       ▼
 TextDecoder / SSE EventStream
       │  api.queryStream
       ▼
 React State (activeActivities)
       │
       ▼
 <AgentActivityStream isLive={true} />
```

1. **Backwards Compatibility:** Legacy stage listeners receive existing `stage` values (`AGENT_STARTED`, `REASONING`, `SEARCHING_VECTOR_DB`, `TOOL_COMPLETED`, `COMPLETED`, `FAILED`).
2. **Multiplexed Data:** Activity objects carry rich metadata including Python code blocks and execution timings.

---

## 5. Python Calculation Artifacts

When the LLM selects the `calculate` tool:
1. `code_generated` event delivers the exact Python code submitted to `SubprocessSandbox`.
2. The code is rendered inside a collapsible block:
   ```text
   [ View Python code ]
   ┌─────────────────────────────────────┐
   │ python (sandboxed)          [Copy]  │
   ├─────────────────────────────────────┤
   │ result = 0.02 * (100 / 0.1) * ...   │
   └─────────────────────────────────────┘
   ```
3. `code_execution_completed` displays the measured runtime (`15ms`) and formatted numeric output (`Output: 36000.0 Pa`).

---

## 6. Persistence & Conversation History

1. **PostgreSQL Schema:**
   The `chat_messages` table stores a `metadata JSONB` column.
2. **Assistant Turn Ingestion:**
   Upon agent completion, `AgentResult.activities` (the list of all sanitized activity events and code artifacts) is saved directly into `chat_messages.metadata`.
3. **Session Reload:**
   `GET /chat/sessions/{session_id}` returns message metadata. Older turns render an interactive accordion (`Agent Activity (N steps)`) allowing operators to audit past calculations and retrieval paths without re-running the agent.

---

## 7. Auto-Scroll Preservation

Auto-scroll monitors `scrollHeight - scrollTop - clientHeight < 100`:
- **User at bottom:** Follows live activity events and streaming response tokens.
- **User scrolled up:** Preserves the scroll viewport so the operator can comfortably read historical messages during long-running agent workflows.
