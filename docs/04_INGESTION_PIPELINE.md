# 04_INGESTION_PIPELINE.md

# OmniOps Ingestion Pipeline
Version: 1.1.0
Status: Living Specification

---

# Purpose

This document specifies how every supported document type is converted into structured knowledge.

The ingestion pipeline is deterministic. It never calls the LLM to answer user questions.

Its responsibility is to transform raw files into a validated Knowledge Package that can be stored, retrieved, and reasoned over later.

---

# MVP Scope

Supported now:
- Machine-readable PDF
- DOCX
- CSV

Architecturally planned for future phases:
- Scanned PDF OCR
- XLSX
- Images
- P&ID
- TXT
- Email

---

# Pipeline Overview

Upload
-> Create Ingestion Job
-> Document Classification
-> Specialized Parser
-> Document Understanding
-> Normalization
-> Knowledge Extraction
-> Knowledge Resolution
-> Knowledge Validation
-> Chunking
-> Embeddings
-> Neo4j + Qdrant + PostgreSQL updates

---

# Stage 1 - Upload

Responsibilities:
- validate MIME type
- generate document_id
- compute file hash
- store original file through StorageService
- create document metadata in PostgreSQL
- create ingestion job in PostgreSQL
- enqueue Redis + RQ work

Output:
- stored document reference
- ingestion job ID

Acceptance:
- invalid files rejected
- duplicate hash detected
- metadata stored
- job queued without blocking the API

---

# Ingestion Job Lifecycle

Public job states:
- PENDING
- PROCESSING
- GRAPH_COMPLETE
- VECTOR_COMPLETE
- COMPLETED
- FAILED

Rules:
- the upload API returns immediately after creating the job
- workers update status as pipeline stages complete
- failed jobs retain structured error information
- jobs must be safe to retry
- reconciliation may resume partially completed jobs

---

# Stage 2 - Document Classification

Determine:
- file extension
- MIME type
- digital or scanned
- language
- parser to use

MVP types:
- Machine PDF
- DOCX
- CSV

Future types:
- Scanned PDF
- XLSX
- Images
- P&ID

Acceptance:
Correct parser selected.

---

# Stage 3 - Specialized Parsers

## Machine PDF

Library:
- PyMuPDF

Extract:
- text
- pages
- images
- tables
- metadata

No OCR.

## DOCX

Extract:
- headings
- paragraphs
- tables
- images
- captions

Preserve hierarchy.

## CSV

Convert rows into structured objects.

## Future Parsers

Future implementations must preserve the same output contract.

Planned:
- scanned PDF OCR
- XLSX parsing
- image OCR
- P&ID understanding

---

# Stage 4 - Document Understanding

Purpose:
Preserve document structure.

Extract:
- sections
- headings
- captions
- reading order
- tables
- figure references

Output:
Structured DocumentContent.

---

# Stage 5 - Normalization

Tasks:
- clean whitespace
- normalize Unicode
- preserve page references
- standardize dates
- normalize units

Output:
Canonical DocumentContent.

---

# Stage 6 - Knowledge Extraction

Extract:

## Entities
- Assets
- Components
- People
- Locations
- Regulations
- Parameters

## Relationships
- HAS_COMPONENT
- LOCATED_IN
- REFERENCES
- INSPECTED_BY
- MAINTAINED_BY
- CAUSES

## Events
- Inspection
- Failure
- Repair
- Shutdown
- Replacement

## Rules

Examples:
- Replace bearing every 5000 hours.
- Pressure must remain below 12 bar.

## Citations

Every extracted fact stores:
- document_id
- page
- chunk
- confidence

---

# Stage 7 - Knowledge Resolution

Purpose:
Resolve extracted knowledge before storage.

Responsibilities:
- duplicate detection
- alias resolution
- canonical asset resolution
- conflicting fact capture
- source authority handling
- confidence normalization
- provenance attachment

Output:
Resolved knowledge candidates ready for validation.

---

# Stage 8 - Knowledge Validation

Purpose:
Prevent graph pollution and incomplete vector entries.

Checks:
- canonical entities present
- missing citations
- invalid relationships
- invalid timestamps
- incomplete metadata
- unsupported units or malformed values

Acceptance:
Every stored fact is traceable and valid enough to index.

---

# Stage 9 - Chunking

Rules:
- semantic chunks
- preserve headings
- preserve page numbers
- overlap neighboring chunks

Every chunk contains:
- text
- page
- section
- document_id

---

# Stage 10 - Embeddings

Generate embeddings for every chunk.

Initial recommendation:
- BAAI/bge-m3

Why this recommendation:
- open-source
- suitable for long documents
- multilingual support is useful for industrial corpora
- compatible with Qdrant-based retrieval

Store:
- embedding
- metadata
- citations
- asset references

Acceptance:
Top-k semantic retrieval returns relevant chunks.

---

# Stage 11 - Storage

## PostgreSQL

Stores:
- document metadata
- ingestion job states
- audit records
- configuration

## Neo4j

Stores:
- nodes
- relationships
- events
- evidence

## Qdrant

Stores:
- chunks
- embeddings
- metadata
- citations

Rules:
- do not assume atomic writes across Neo4j and Qdrant
- graph and vector writes must be idempotent
- retries must be safe
- reconciliation must resume partial jobs
- searchable content must respect readiness and provenance metadata

---

# Knowledge Package

Every document produces:

```json
{
  "document": {},
  "entities": [],
  "relationships": [],
  "events": [],
  "rules": [],
  "parameters": [],
  "chunks": [],
  "citations": [],
  "metadata": {},
  "resolution": {
    "canonical_entities": [],
    "conflicts": [],
    "source_authority": {}
  }
}
```

Downstream systems never operate directly on raw files.

---

# Error Handling

Possible failures:
- corrupted file
- unsupported format
- parser failure
- OCR failure in future parsers
- storage failure
- Redis connectivity failure
- PostgreSQL write failure
- Neo4j write failure
- Qdrant write failure
- embedding failure

Every stage logs structured errors and updates ingestion job status.

---

# Acceptance Criteria

The ingestion pipeline is complete when:

- every supported MVP file type parses
- every parser returns DocumentContent
- every upload returns a job ID
- job status transitions persist correctly
- every document produces a Knowledge Package
- graph updates succeed
- vector updates succeed
- retries do not create duplicate records
- citations are preserved
- unit tests pass

---

# Suggested Micro-task Mapping

FOUND-* -> Environment, queue, storage, job lifecycle

ING-* -> Upload and parsing

NORM-* -> Cleaning and chunk preparation

ENT-* -> Entity extraction

REL-* -> Relationship extraction

GRAPH-* -> Graph updates

VEC-* -> Embeddings and Qdrant storage

RET-* -> Retrieval

---

Dependencies:
- 01_CONTEXT.md
- 02_SYSTEM_ARCHITECTURE.md
- 03_GRAPH_SCHEMA.md

Next:
05_RETRIEVAL_ENGINE.md
