# V15-IMG-ARCH-001 — Final Architecture Decision Document

> [!IMPORTANT]
> No code will be written until every decision in this document is explicitly approved.

---

## System Context (Acknowledged)

| Constraint | Value |
|---|---|
| GPU | NVIDIA RTX 3050 Laptop, **4 GB VRAM** |
| System RAM | **24 GB** |
| Inference Runtime | **Ollama** (only) |
| Reasoning Model | **Llama 3.2** (local, via Ollama) |
| Internet | **Not available / not required** |
| Model Downloads | **Manual only, before deployment** |
| Acceptable Latency | **10–30 seconds/image** |
| Cloud APIs | **Prohibited** |

---

## Decision 1 — Offline Vision Model

### Research Summary

| Model | Params | Q4 Disk | VRAM (base) | VRAM (with KV) | Fits 4 GB? | OCR | Diagrams | Ollama |
|---|---|---|---|---|---|---|---|---|
| **Gemma 4 E2B** | ~2B effective | ~3.2 GB | ~2.5 GB | ~4–5 GB | ✅ Tight but yes | Very good | Good + reasoning | ✅ `gemma4:e2b` |
| Gemma 3 4B | 4B | ~2.5 GB | ~2.5 GB | ~6–8 GB | ⚠️ Likely spills | Good | Good | ✅ `gemma3:4b` |
| Qwen2.5-VL 3B | 3B | ~2 GB | ~2.5 GB | ~5–7 GB | ⚠️ KV pressure | Excellent | Excellent | ✅ `qwen2.5-vl:3b` |
| Qwen2.5-VL 7B | 7B | ~4 GB | ~6 GB | ~8–15 GB | ❌ Too large | Best-in-class | Best-in-class | ✅ |
| Moondream 2 | ~2B | ~1.2 GB | ~1.5 GB | ~2–3 GB | ✅ Comfortable | Acceptable | Weak | ✅ |

### Analysis

**Gemma 4 E2B** is the primary candidate per your requirement. Research confirms:

1. **It runs on RTX 3050 4 GB** — Ollama reports full GPU offload for the base model at Q4_K_M. The model is explicitly designed for edge hardware.
2. **Vision quality** — Good OCR, good document understanding, native image support with variable-resolution encoding. Not the absolute best at diagrams (Qwen2.5-VL 7B leads), but viable within the hardware constraint.
3. **Reasoning** — Built-in thinking mode (`<|think|>`) is useful for multi-step analysis of P&IDs.
4. **Coexistence with Llama 3.2** — Ollama swaps models automatically. Only one is in VRAM at a time. Both fit individually in 4 GB.
5. **Latency** — Expected 10–25 seconds per image on RTX 3050 at Q4, within the 10–30 second target.

**Qwen2.5-VL 3B** is the best alternative. It leads in OCR/diagram quality but its KV cache pressure on 4 GB VRAM is reported as problematic. If Gemma 4 E2B underperforms on P&ID tasks during testing, Qwen2.5-VL 3B should be evaluated as a swap.

### Decision

```text
Vision Model:           Gemma 4 E2B
Model Version:          gemma4:e2b (Ollama tag)
Quantization:           Q4_K_M (4-bit)
Runtime:                Ollama
Approximate VRAM:       ~2.5 GB base, ~4–5 GB with KV cache
Approximate RAM:        ~4 GB system RAM when partially offloaded
Disk Size:              ~3.2 GB
Expected Latency:       10–25 seconds/image (prototype)
Reason:                 Smallest viable multimodal model from Gemma 4 family,
                        fits RTX 3050 4 GB, native vision support, built-in
                        reasoning mode, Apache 2.0 license, edge-optimized.
Fallback:               Qwen2.5-VL 3B (qwen2.5-vl:3b) — swap if E2B
                        underperforms on P&ID or OCR tasks.
```

> [!IMPORTANT]
> **Pre-deployment requirement:** Run `ollama pull gemma4:e2b` before first use. This must be done manually with internet access, then the model file is cached locally forever.

---

## Decision 2 — Multi-Model Routing

### Architecture

```text
                    USER REQUEST / FILE
                           │
                           ▼
                  ┌─────────────────┐
                  │   TASK ROUTER   │
                  │ (ModelRouter)   │
                  └────────┬────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     TEXT QUERY       IMAGE FILE       MIXED DOCUMENT
          │                │           (PDF/DOCX with
          │                │            embedded images)
          │                │                │
          ▼                ▼                ▼
    ┌──────────┐   ┌──────────────┐  ┌──────────────┐
    │ Llama 3.2│   │ Image Router │  │ Text Parser  │
    │ Reasoning│   │ (classify →  │  │ + Image      │
    │          │   │  P&ID or     │  │ Extraction   │
    │          │   │  Generic)    │  │ → route each │
    └────┬─────┘   └──────┬───────┘  └──────┬───────┘
         │                │                 │
         │         ┌──────┴──────┐          │
         │         │             │          │
         │      P&ID         Generic       │
         │      Pipeline     Vision        │
         │         │             │          │
         │         ▼             ▼          │
         │    CV + Gemma 4   Gemma 4 E2B   │
         │         │             │          │
         └─────────┴─────────────┴──────────┘
                           │
                           ▼
                  Existing Ingestion Pipeline
                  (chunk → entity → relationship →
                   resolve → graph → vector)
```

### Implementation

A new `ModelRouter` service in `backend/retrieval/` (or a shared `backend/services/` module) that decides routing based on:

| Signal | How Detected | Route |
|---|---|---|
| File extension is `.png`, `.jpg`, `.tiff` | File type check | → Image Router |
| File extension is `.pdf`, `.docx` | File type check | → Text Parser (existing) |
| Document contains embedded images | Normalizer metadata `has_images: True` | → Image sub-pipeline for each image |
| User asks a text question | No file attached | → Llama 3.2 (existing retrieval + generation) |
| Text question references an image | Future enhancement | → Llama 3.2 + image context |

**The user never selects a model.** The router inspects the input and makes the decision. The selected model is logged for debugging but hidden from the user.

---

## Decision 3 — Image Classification Before Processing

### Strategy: Vision-model-based classification

Rather than introducing a separate lightweight classifier (which would add another model to manage on tight hardware), **use Gemma 4 E2B itself** for image classification with a structured prompt.

The model is already loaded for image processing. The classification prompt takes <2 seconds and avoids loading a separate model.

### Classification Flow

```text
IMAGE
  │
  ▼
Gemma 4 E2B
Prompt: "Classify this image into exactly one of:
         PID, PHOTOGRAPH, DIAGRAM, SCREENSHOT, SCANNED_DOCUMENT.
         Respond with only the classification label."
  │
  ├── PID           → P&ID Pipeline
  ├── DIAGRAM       → Generic Vision (with diagram-specific prompt)
  ├── PHOTOGRAPH    → Generic Vision (equipment/inspection prompt)
  ├── SCREENSHOT    → Generic Vision (UI/text extraction prompt)
  └── SCANNED_DOCUMENT → OCR-focused Vision prompt
```

### Classification Categories

| Class | Examples | Pipeline |
|---|---|---|
| `PID` | P&ID diagrams, process flow diagrams, ISA-standard drawings | P&ID Pipeline (Decision 4) |
| `PHOTOGRAPH` | Equipment photos, inspection photos, site photos | Generic Vision |
| `DIAGRAM` | Non-P&ID technical diagrams, schematics, charts | Generic Vision |
| `SCREENSHOT` | UI screenshots, software captures | Generic Vision |
| `SCANNED_DOCUMENT` | Scanned pages, faxes | OCR-focused Vision |

### Fallback

If classification confidence is low or ambiguous, default to `PHOTOGRAPH` (generic pipeline). The generic pipeline still extracts useful information; it just won't apply P&ID-specific processing.

---

## Decision 4 — P&ID Processing

### Architecture: Hybrid Approach (CV deterministic + VLM verification)

```text
                 CLASSIFIED P&ID IMAGE
                         │
              ┌──────────┴──────────┐
              │                     │
     DETERMINISTIC CV         VLM ANALYSIS
     (OpenCV pipeline)        (Gemma 4 E2B)
              │                     │
     ┌────────┼────────┐            │
     │        │        │            │
  Line     Symbol    OCR/Tag        │
  Detection Detection  Extraction   │
     │        │        │            │
     └────────┼────────┘            │
              │                     │
              ▼                     ▼
        CV Extracted           VLM Extracted
        Entities               Entities
              │                     │
              └──────────┬──────────┘
                         │
                    MERGE + SCORE
                    (confidence-weighted)
                         │
                         ▼
                  STRUCTURED DATA
                  (entities, relationships,
                   spatial topology)
                         │
                         ▼
                  KNOWLEDGE LAYER
```

### What is deterministic (OpenCV)

| Stage | Method | Output |
|---|---|---|
| Line detection | Hough Line Transform | Pipe connections, flow paths |
| Symbol detection | Contour analysis + aspect ratio heuristics | Valve/pump/instrument bounding boxes |
| OCR / Tag extraction | Pytesseract (or vision model) | Equipment tags (P-301, V-200), labels |
| Spatial relationships | Bounding box proximity analysis | Which symbols connect to which lines |

### What is handled by vision model (Gemma 4 E2B)

| Stage | Method | Output |
|---|---|---|
| Semantic verification | Structured prompt with image | Confirms/corrects CV-detected entities |
| Symbol identification | Vision prompt | Names for detected symbols (e.g., "gate valve", "centrifugal pump") |
| Flow direction | Vision prompt | Direction of process flow |
| Missing entities | Vision prompt | Entities that CV missed |

### Confidence scoring

Each entity gets a confidence score based on:
- `cv_only`: 0.6 (detected by CV, not verified by VLM)
- `vlm_only`: 0.7 (detected by VLM, no CV confirmation)  
- `cv_and_vlm`: 0.9 (both agree)
- `cv_vlm_conflict`: 0.4 (disagreement — flagged for review)

### New dependency

```text
opencv-python-headless    (~40 MB, no GUI needed)
pytesseract               (~minimal, uses system Tesseract)
```

> [!NOTE]
> Tesseract OCR must be installed on the system separately. On Windows: `choco install tesseract` or manual download. This is a one-time setup requirement.

---

## Decision 5 — Image Preprocessing

### Adaptive pipeline (not one-size-fits-all)

```text
Original Image
      │
      ├── 1. Store original (auditability)
      │
      ├── 2. Detect orientation (EXIF + Hough)
      │      └── Rotate if needed
      │
      ├── 3. Resize to max dimension
      │      └── Max 2048px on longest side
      │      └── Preserves aspect ratio
      │
      ├── 4. Classification-based adaptive steps:
      │      │
      │      ├── PHOTOGRAPH:
      │      │    └── Light CLAHE contrast (clip_limit=2.0)
      │      │
      │      ├── SCANNED_DOCUMENT:
      │      │    ├── Deskew (Hough transform)
      │      │    ├── Binarization (Otsu threshold)
      │      │    └── Noise reduction (Gaussian blur, kernel=3)
      │      │
      │      ├── PID:
      │      │    ├── Deskew
      │      │    ├── Contrast enhancement (CLAHE)
      │      │    └── No binarization (preserves color info)
      │      │
      │      ├── DIAGRAM:
      │      │    └── CLAHE contrast
      │      │
      │      └── SCREENSHOT:
      │           └── No preprocessing (already clean)
      │
      └── 5. Output: preprocessed image bytes
             (original remains untouched in storage)
```

**The original image is never modified.** Preprocessing produces a temporary copy for the vision pipeline. The original is preserved in `StorageService` for auditability and provenance.

---

## Decision 6 — Images Embedded Inside Documents

### Mixed-content document handling

```text
PDF Upload
  │
  ├── Text Extraction (existing PyMuPDF parser)
  │     └── Normal text → existing pipeline
  │
  ├── Image Extraction (PyMuPDF xref extraction)
  │     └── Each extracted image:
  │           ├── Store as separate image file
  │           ├── Classify (Decision 3)
  │           ├── Preprocess (Decision 5)
  │           ├── Vision pipeline
  │           └── Merge results into parent DocumentContent
  │
  └── Scanned Page Detection
        └── If page has no extractable text but has images:
              └── Treat entire page as image → vision pipeline

DOCX Upload
  │
  ├── Text/Table Extraction (existing python-docx parser)
  │     └── Normal content → existing pipeline
  │
  └── Embedded Image Extraction (python-docx image relationships)
        └── Same as PDF embedded images above
```

### Implementation location

Extend the existing normalizer (`ingestion/normalizer.py`) with an `extract_embedded_images` stage that:
1. Detects binary image data in PDF/DOCX files
2. Extracts each image to temporary storage
3. Returns image references in metadata for the vision sub-pipeline
4. The ingestion orchestrator calls the vision pipeline for each extracted image

### Result merging

The parent document's `DocumentContent` accumulates vision-extracted text as additional pages/sections. Citations trace back to both the original document AND the specific embedded image.

---

## Decision 7 — Supported Image Formats

### Standalone upload

| Format | Supported | Notes |
|---|---|---|
| PNG | ✅ | Most common |
| JPG/JPEG | ✅ | Most common |
| TIFF | ✅ | Industrial scanners |
| BMP | ❌ | Rare, no value added |
| WebP | ❌ | Not industrial |

### Internally extracted from

| Source | Image Extraction Method |
|---|---|
| PDF | PyMuPDF `xref` image extraction (already available) |
| DOCX | python-docx `document.inline_shapes` + relationship parts |
| PPTX | ❌ Deferred (not currently in parser list) |

> [!NOTE]
> PPTX support requires a new parser. Adding it here would expand scope beyond the image architecture decision. Recommend deferring to a separate task.

---

## Decision 8 — Backend Processing / UX

### Asynchronous architecture

The existing infrastructure already supports async processing:

```text
User uploads image
       │
       ▼
FastAPI /upload endpoint
       │
       ├── Validate file (type, size, magic bytes)
       ├── Store original via StorageService
       ├── Create ingestion job (PENDING)
       ├── Return immediately: { job_id, status: "processing" }
       │
       ▼
Ingestion Pipeline (async)
       │
       ├── Classify image
       ├── Preprocess
       ├── Vision inference (10–30 sec)
       ├── P&ID pipeline if required
       ├── Entity extraction
       ├── Knowledge resolution
       ├── Graph + Vector persistence
       │
       ▼
Job status → COMPLETED
       │
       ▼
Frontend polls /jobs/{id} or receives SSE event
```

### Mechanism

Use the **existing ingestion pipeline + event bus** (`utils/event_bus.py`). The current system already:
- Creates ingestion jobs with lifecycle tracking (PENDING → PROCESSING → COMPLETED)
- Emits SSE events via the event bus
- Supports the bottom-right widget pattern on the frontend

**No new queue/broker/service is needed.** On Windows (prototype), the pipeline runs in-process via `asyncio.create_task(run_in_threadpool(...))` (existing pattern in `query.py`). On production (Linux), the RQ worker handles it.

---

## Decision 9 — DocumentContent Representation

### Analysis of current model

```python
@dataclass(frozen=True)
class DocumentContent:
    filename: str
    text: str
    pages: tuple[str, ...]
    page_count: int
    metadata: dict[str, str | int | bool | float]
```

### What it needs to carry for image evidence

| Requirement | Current coverage | Gap? |
|---|---|---|
| Vision-extracted text description | `text` field | ✅ No gap |
| OCR text | `text` field | ✅ No gap |
| Original image URI | `metadata["storage_uri"]` | ✅ No gap |
| Image provenance (which image, which page) | `metadata` | ⚠️ Needs structure |
| P&ID entities with bounding boxes | Not representable | ❌ Gap |
| Confidence scores per extraction | Not representable | ❌ Gap |
| Source type (image vs text vs P&ID) | `metadata["source_type"]` | ✅ No gap |
| Page/image relationships | `metadata` | ⚠️ Needs structure |

### Decision: Smallest backward-compatible extension

Add **one optional field** to `DocumentContent`:

```python
@dataclass(frozen=True)
class DocumentContent:
    filename: str
    text: str
    pages: tuple[str, ...]
    page_count: int
    metadata: dict[str, str | int | bool | float]
    visual_evidence: tuple[VisualEvidence, ...] = ()   # NEW — optional, empty by default
```

```python
@dataclass(frozen=True)
class VisualEvidence:
    """Evidence extracted from a visual source (image, diagram, P&ID)."""
    image_uri: str                          # StorageService URI of the original image
    source_type: str                        # "photograph", "pid", "diagram", "screenshot", "scanned"
    extracted_text: str                     # Vision model output text
    classification: str                     # Image class label
    confidence: float                       # Overall extraction confidence
    bounding_boxes: tuple[BoundingBox, ...] = ()  # P&ID entities with spatial info
    parent_page: int | None = None          # Page number if extracted from a document
```

```python
@dataclass(frozen=True)
class BoundingBox:
    """Spatial location of a detected entity within an image."""
    label: str          # e.g., "Pump P-301", "Gate Valve"
    x: int
    y: int
    width: int
    height: int
    confidence: float
    entity_type: str    # "asset", "component", "label", "line"
```

### Why not just use `metadata`?

- `metadata` is typed as `dict[str, str | int | bool | float]` — it cannot hold nested structures (lists of bounding boxes, nested dicts)
- Changing `metadata`'s type signature would break the frozen dataclass contract
- Adding a separate typed field is cleaner and fully backward-compatible (defaults to empty tuple)

### Backward compatibility

- All existing parsers (PDF, DOCX, CSV, Excel) continue to produce `visual_evidence=()` — **zero changes needed**
- All existing pipeline stages (chunker, entity extractor, etc.) ignore `visual_evidence` unless explicitly extended
- The `text` field still carries the primary content; `visual_evidence` is supplementary

---

## Decision 10 — Resource & Cost Controls

### Prototype hardware limits

| Control | Value | Justification |
|---|---|---|
| Max image file size | **20 MB** | Covers high-res industrial photos; 3050 can process up to ~50 MP images after resize |
| Max image resolution (processing) | **2048 × 2048 px** | Resized before vision inference to control VRAM; original preserved |
| Max concurrent vision jobs | **1** | Single GPU — serialize vision inference to avoid OOM |
| Max images per batch upload | **10** | Prevents queue saturation on prototype |
| Ollama context window | **4096 tokens** for vision | Limits KV cache VRAM pressure on 4 GB |
| Model keep-alive | **5 minutes** | Ollama `OLLAMA_KEEP_ALIVE=5m` — unload after idle to free VRAM |
| Image resize tiling | **Off for prototype** | Tiling splits large images into tiles — unnecessary at 2048px cap |

### Caching strategy

| Cache | Purpose | Implementation |
|---|---|---|
| Image hash dedup | Skip re-processing identical images | SHA-256 of file bytes, checked before pipeline |
| Vision result cache | Avoid re-inference on same image | Store vision output text in `metadata["vision_cache_key"]` keyed by image hash |
| Preprocessed image cache | Skip OpenCV re-processing | Temporary cache in `/data/storage/cache/`, LRU with max 500 MB |

### Configuration

All limits are environment-variable driven via `config/settings.py`:

```python
class VisionSettings(BaseSettings):
    model: str = Field(default="gemma4:e2b", validation_alias="VISION_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    max_image_size_mb: int = Field(default=20, validation_alias="VISION_MAX_IMAGE_SIZE_MB")
    max_resolution: int = Field(default=2048, validation_alias="VISION_MAX_RESOLUTION")
    max_concurrent_jobs: int = Field(default=1, validation_alias="VISION_MAX_CONCURRENT_JOBS")
    max_batch_size: int = Field(default=10, validation_alias="VISION_MAX_BATCH_SIZE")
    context_window: int = Field(default=4096, validation_alias="VISION_CONTEXT_WINDOW")
```

---

## Decision 11 — Model Switching

### Ollama handles model switching automatically

Ollama's built-in model management already solves this:

1. When a text query arrives → Ollama loads Llama 3.2 into VRAM
2. When an image arrives → Ollama unloads Llama 3.2, loads Gemma 4 E2B
3. After vision processing, if a text query arrives → Ollama swaps back

**No custom model-loading code is needed.** The `ModelRouter` simply calls the appropriate Ollama model name. Ollama handles VRAM management, swapping, and caching.

### Model Registry

```python
class ModelRegistry(BaseSettings):
    """Centralized model name configuration."""
    reasoning_model: str = Field(default="llama3.2", validation_alias="REASONING_MODEL")
    vision_model: str = Field(default="gemma4:e2b", validation_alias="VISION_MODEL")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", validation_alias="EMBEDDING_MODEL_NAME")
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
```

### Routing logic (in `ModelRouter`)

```python
def select_model(self, task_type: str) -> str:
    if task_type in ("image_classify", "image_vision", "pid_verify"):
        return self._registry.vision_model    # gemma4:e2b
    elif task_type in ("text_query", "reasoning", "generation"):
        return self._registry.reasoning_model  # llama3.2
    else:
        return self._registry.reasoning_model  # safe default
```

The user **never** sees which model was selected. Logs record it for debugging:

```text
INFO  ModelRouter: task=image_classify model=gemma4:e2b latency=1.2s
INFO  ModelRouter: task=text_query model=llama3.2 latency=3.5s
```

---

## Decision 12 — Production vs Prototype Architecture

### Abstraction layer

```text
                  ┌─────────────────────────┐
                  │     MODEL REGISTRY      │
                  │   (config/settings.py)   │
                  ├─────────────────────────┤
                  │ reasoning_model = ...   │
                  │ vision_model = ...      │
                  │ embedding_model = ...   │
                  │ ollama_base_url = ...   │
                  └────────────┬────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
               PROTOTYPE             PRODUCTION
                    │                     │
           ┌────────┴────────┐    ┌───────┴───────┐
           │ Llama 3.2 (8B)  │    │ Llama 3.3 70B │
           │ Gemma 4 E2B     │    │ Gemma 4 12B   │
           │ RTX 3050 4 GB   │    │ A100 80 GB    │
           │ all-MiniLM-L6   │    │ bge-m3        │
           └─────────────────┘    └───────────────┘
```

### What stays the same between prototype and production

- All pipeline code
- All API routes
- All data models
- All graph/vector persistence
- All frontend code

### What changes (environment variables only)

| Variable | Prototype | Production |
|---|---|---|
| `REASONING_MODEL` | `llama3.2` | `llama3.3:70b` (or equivalent) |
| `VISION_MODEL` | `gemma4:e2b` | `gemma4:12b` or `qwen2.5-vl:7b` |
| `VISION_MAX_RESOLUTION` | `2048` | `4096` |
| `VISION_MAX_CONCURRENT_JOBS` | `1` | `4` |
| `VISION_CONTEXT_WINDOW` | `4096` | `16384` |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | `BAAI/bge-m3` |

**No code changes.** Swap `.env`, pull the larger models, restart.

---

## Decision 13 — Vision Context Injection into Chat

### Problem

After the vision pipeline processes an image and stores it in the knowledge layer (graph + vector), the user should also be able to **immediately ask follow-up questions** about that image in the chat.

For example:
1. User uploads a photo of a pump in a chat session
2. Vision pipeline processes it (10–30 sec)
3. User asks: *"What brand is the pump in the photo I just uploaded?"*
4. Llama 3.2 should be able to answer because it has the vision description in the conversation context

### Solution: Dual-path storage

When the vision pipeline finishes, the extracted description is saved to **two places**:

```text
Vision Pipeline Completes
         │
         ├── PATH 1: Knowledge Layer (existing)
         │     ├── Chunker → Entity Extractor → Graph
         │     └── Embeddings → Qdrant
         │
         └── PATH 2: Chat Context (NEW)
               └── Save vision description as a system message
                   in the active chat session
```

### How it works

```text
User uploads image in Session "abc-123"
         │
         ▼
Vision pipeline runs asynchronously
         │
         ▼
Gemma 4 E2B produces description:
  "This is a photograph of a Grundfos CR 45-2 vertical
   multistage centrifugal pump. Visible labels show model
   number CR 45-2-2 A-F-A-E-HQQE, serial number 98437265.
   The pump casing is stainless steel with blue paint.
   Connected piping shows 3-inch flanged connections..."
         │
         ▼
Save to chat_messages table:
  session_id = "abc-123"
  role = "system"
  content = "[Image Analysis: pump_photo.jpg]\n{description}"
  citations = [{ source: "vision", image_uri: "..." }]
         │
         ▼
SSE event notifies frontend:
  { event: "IMAGE_PROCESSED", data: { session_id, filename, summary } }
         │
         ▼
User asks: "What brand is that pump?"
         │
         ▼
Llama 3.2 sees the vision description in conversation history
         │
         ▼
Llama 3.2 answers: "The pump is a Grundfos CR 45-2..."
```

### Implementation detail

The existing `ChatRepository.add_message()` already supports a `role` field. Use `role = "system"` for vision context messages. This keeps them separate from user/assistant messages and clearly marks them as machine-generated context.

The `QueryOrchestrator` already loads conversation history via `get_recent_messages()`. System messages are included automatically — Llama 3.2 will see the image description as prior context without any changes to the retrieval pipeline.

### Message format

```text
[Image Analysis: {filename}]
Classification: {image_class}
Confidence: {confidence}

{vision_model_extracted_text}

[Source: {image_uri} | Processed: {timestamp}]
```

### What the user sees in the chat

The frontend should render this as a collapsible "Image Analysis" card:

```text
┌─────────────────────────────────────────┐
│ 📷 Image Analysis: pump_photo.jpg       │
│ ─────────────────────────────────       │
│ Classification: Equipment Photograph    │
│                                         │
│ ▶ Show full description                 │
│                                         │
│ ✅ Knowledge graph updated              │
└─────────────────────────────────────────┘
```

When expanded, the full vision description is visible. This gives the user confidence that the system understood the image, and allows them to ask follow-up questions naturally.

### Key behaviors

| Behavior | Detail |
|---|---|
| **Context window** | Vision descriptions are included in conversation history via `get_recent_messages()` — they automatically participate in the sliding window |
| **No re-inference** | The description is generated once by Gemma 4 E2B and stored. Llama 3.2 reads it as text. No vision model is needed for follow-ups. |
| **Multiple images** | Each image gets its own system message. If 3 images are uploaded, 3 system messages appear in history. |
| **Session scope** | The vision context only exists in the session where the image was uploaded. Other sessions don't see it. |
| **Persistence** | Stored in PostgreSQL `chat_messages` table — survives server restarts |

---

## Summary of All Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Vision Model | **Gemma 4 E2B** (Q4_K_M via Ollama) — fallback: Qwen2.5-VL 3B |
| 2 | Multi-Model Routing | **ModelRouter** service — routes by file type + task type automatically |
| 3 | Image Classification | **Vision model (E2B) classifies** — PID / PHOTOGRAPH / DIAGRAM / SCREENSHOT / SCANNED_DOCUMENT |
| 4 | P&ID Processing | **Hybrid: OpenCV deterministic + Gemma 4 E2B verification** — confidence-scored merge |
| 5 | Preprocessing | **Adaptive by image class** — orientation, resize, class-specific enhancements |
| 6 | Embedded Images | **Extract from PDF/DOCX automatically** — each image routes through vision pipeline |
| 7 | Formats | **PNG + JPG + TIFF** standalone; PDF/DOCX embedded extraction; PPTX deferred |
| 8 | Async Processing | **Existing event bus + ingestion pipeline** — no new broker needed |
| 9 | DocumentContent | **Add `visual_evidence: tuple[VisualEvidence, ...]` field** — backward-compatible |
| 10 | Resource Controls | **20 MB max, 2048px resize, 1 concurrent job, 4096 context, hash-based caching** |
| 11 | Model Switching | **Ollama handles automatically** — ModelRegistry in config, user never selects |
| 12 | Prototype → Production | **Environment variables only** — swap models, restart, no code changes |
| 13 | Chat Context | **Vision description saved as system message** — enables follow-up questions via Llama 3.2 |

---

## Questions for Developer

Before implementation, I need clarity on the following:

### Question 1 — Tesseract OCR

The P&ID pipeline (Decision 4) uses Pytesseract for deterministic OCR. **Is Tesseract already installed on the prototype machine, or should I include installation instructions?**

If Tesseract is not acceptable, the alternative is to rely entirely on Gemma 4 E2B for OCR (slightly less deterministic but avoids a new system dependency).

### Question 2 — Ollama `/api/chat` with Images

The current Ollama provider uses `/api/generate`. For vision tasks, Ollama's image support uses the `/api/chat` endpoint with base64-encoded images. **Is this acceptable, or should I extend the existing `/api/generate` path?**

The `/api/chat` endpoint is the standard way to pass images to Ollama vision models.

### Question 3 — opencv-python-headless Dependency

Decision 4 and 5 require `opencv-python-headless` (~40 MB pip package). **Is adding this dependency acceptable?** It has no GUI requirements and runs headlessly.

> [!IMPORTANT]
> Please review all 13 decisions and the 3 questions above. Hit **Proceed** to approve, or tell me what to change.

