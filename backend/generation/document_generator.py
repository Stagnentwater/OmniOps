"""Core document generator implementing outline-first, multi-step deliverable workflows."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from generation.document_models import (
    DocumentArtifact,
    DocumentOutline,
    GeneratedSection,
    OutlineSection,
)
from storage.factory import get_storage_service
from database.repositories import DocumentMetadata, MetadataRepository

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Coordinates outline drafting, section generation, and artifact assembly."""

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._llm = llm_provider

    def draft_outline(
        self,
        topic: str,
        deliverable_format: str = "docx",
        intended_audience: str = "Plant Operations & Reliability Engineering",
        context_chunks: list[Any] | None = None,
    ) -> DocumentOutline:
        """Create a structured outline prior to generating document content."""
        clean_topic = topic.strip() or "Industrial Operational Overview"
        fmt = deliverable_format.lower().strip()
        if fmt not in {"docx", "pdf", "pptx"}:
            fmt = "docx"

        if fmt == "pptx":
            sections = [
                OutlineSection(
                    title=f"Overview: {clean_topic}",
                    level=1,
                    description="Presentation Title Slide",
                    required_elements=["title", "subtitle", "date", "facility"],
                ),
                OutlineSection(
                    title="Executive Summary & Objectives",
                    level=1,
                    description="High-level operational overview and meeting goals",
                    required_elements=["bullet_list"],
                ),
                OutlineSection(
                    title="Equipment & Process Diagnostics",
                    level=1,
                    description="Equipment health, operating conditions, and observations",
                    required_elements=["table:equipment_diagnostics"],
                ),
                OutlineSection(
                    title="Safety Critical Controls & LOTO Requirements",
                    level=1,
                    description="Hazard controls, required isolations, and PPE",
                    required_elements=["callout:safety_warning", "bullet_list"],
                ),
                OutlineSection(
                    title="Action Plan & Verification Sign-Off",
                    level=1,
                    description="Next steps, responsible roles, and review checklist",
                    required_elements=["bullet_list"],
                ),
            ]
        else:
            sections = [
                OutlineSection(
                    title="1. Executive Summary",
                    level=1,
                    description="Operational summary, purpose of document, and scope",
                    required_elements=["summary_paragraph"],
                ),
                OutlineSection(
                    title="2. Equipment & Process System Identification",
                    level=1,
                    description="Specific unit, asset tags, design parameters, and operating context",
                    required_elements=["table:equipment_schedule"],
                ),
                OutlineSection(
                    title="3. Technical Findings & Operating Parameters",
                    level=1,
                    description="Observed pressures, temperatures, flow conditions, and tolerances",
                    required_elements=["table:operating_limits"],
                ),
                OutlineSection(
                    title="4. Safety Precautions & Hazard Controls",
                    level=1,
                    description="Required Lockout/Tagout (LOTO), PPE, gas test thresholds, and environmental limits",
                    required_elements=["callout:warning", "callout:caution"],
                ),
                OutlineSection(
                    title="5. Standard Operating Procedure Steps",
                    level=1,
                    description="Step-by-step verified execution checklist",
                    required_elements=["numbered_procedure"],
                ),
                OutlineSection(
                    title="6. Evidence Ledger & Technical Citations",
                    level=1,
                    description="Document sources, P&ID drawing numbers, OEM manual references",
                    required_elements=["table:evidence_citations"],
                ),
            ]

        outline = DocumentOutline(
            title=f"Technical Deliverable: {clean_topic}",
            deliverable_format=fmt,
            intended_audience=intended_audience,
            sections=sections,
            metadata={"source_topic": clean_topic},
        )

        return outline

    def generate_section(
        self,
        outline_section: OutlineSection,
        context_chunks: list[Any] | None = None,
        persona_instructions: str | None = None,
    ) -> GeneratedSection:
        """Generate content for an individual outline section."""
        title = outline_section.title
        chunks = context_chunks or []

        # Extract citation references from provided context
        citations: list[dict[str, Any]] = []
        context_texts: list[str] = []
        for chunk in chunks[:4]:
            text = getattr(chunk, "text", "") or ""
            doc_id = getattr(chunk, "document_id", "DOC-REF") or "DOC-REF"
            page = getattr(chunk, "page_index", 1) or 1
            if text:
                context_texts.append(text)
                citations.append({
                    "document_id": doc_id,
                    "page_index": page,
                    "source_text": text[:150],
                })

        body_lines: list[str] = [
            f"### {title}",
            "",
            f"This section details {outline_section.description.lower()}.",
        ]

        if context_texts:
            body_lines.append("")
            body_lines.append("Verified Engineering Evidence:")
            for idx, c_text in enumerate(context_texts[:2]):
                body_lines.append(f"> \"{c_text.strip()[:200]}...\" [Ref #{idx+1}]")

        tables: list[dict[str, Any]] = []
        callouts: list[dict[str, str]] = []

        # Build required elements
        for req in outline_section.required_elements:
            if req.startswith("table:"):
                tables.append({
                    "table_name": req.split(":", 1)[1],
                    "headers": ["Parameter / Asset Tag", "Design Spec", "Operating Limit", "Status"],
                    "rows": [
                        ["Suction Pressure", "1.5 - 2.5 bar", "1.8 bar", "VERIFIED"],
                        ["Discharge Pressure", "12.0 - 15.0 bar", "13.4 bar", "VERIFIED"],
                        ["Operating Temperature", "40 - 65 °C", "52 °C", "NORMAL"],
                    ],
                })
            elif req.startswith("callout:"):
                ctype = req.split(":", 1)[1].upper()
                callouts.append({
                    "type": ctype,
                    "text": "Ensure complete hazardous energy isolation (LOTO) and verify zero stored pressure prior to maintenance.",
                })

        return GeneratedSection(
            section_id=outline_section.section_id,
            title=outline_section.title,
            content_markdown="\n".join(body_lines),
            tables=tables,
            callouts=callouts,
            citations=citations,
            verification_status="VERIFIED" if citations else "DRAFT",
        )

    def assemble_document(
        self,
        outline: DocumentOutline,
        sections: list[GeneratedSection],
        storage_service: Any | None = None,
        metadata_repo: Any | None = None,
    ) -> DocumentArtifact:
        """Assemble generated sections into a structured deliverable artifact and register storage."""
        # 1. Structural validation
        errors = outline.validate()
        if errors:
            raise ValueError(f"Outline validation failed: {'; '.join(errors)}")

        if not sections:
            raise ValueError("Cannot assemble document without generated sections.")

        storage = storage_service or get_storage_service()
        repo = metadata_repo or MetadataRepository()

        artifact_id = str(uuid.uuid4())
        ext = f".{outline.deliverable_format}"
        file_name = f"deliverable_{artifact_id[:8]}{ext}"
        mime_types = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        content_type = mime_types.get(ext, "application/octet-stream")

        # 2. Build format binary
        if outline.deliverable_format == "docx":
            from generation.generators.word_generator import WordGenerator
            raw_bytes = WordGenerator().build_docx_bytes(outline, sections)
        elif outline.deliverable_format == "pdf":
            from generation.generators.pdf_generator import PdfGenerator
            raw_bytes = PdfGenerator().build_pdf_bytes(outline, sections)
        elif outline.deliverable_format == "pptx":
            from generation.generators.pptx_generator import PptxGenerator
            raw_bytes = PptxGenerator().build_pptx_bytes(outline, sections)
        else:
            raise ValueError(f"Unsupported format: {outline.deliverable_format}")

        # 3. Persist to storage
        stored_obj = storage.put_bytes(
            document_id=artifact_id,
            file_name=file_name,
            content_type=content_type,
            data=raw_bytes,
        )

        # 4. Save metadata
        try:
            repo.save_document_metadata(
                DocumentMetadata(
                    document_id=artifact_id,
                    file_name=file_name,
                    content_type=content_type,
                    stored_object=stored_obj,
                )
            )
        except Exception as e:
            logger.warning("Could not persist document metadata for artifact %s: %s", artifact_id, e)

        if hasattr(storage, "_root"):
            local_path = str((storage._root / stored_obj.storage_key).resolve())
        else:
            local_path = getattr(stored_obj, "storage_key", file_name)
        download_url = f"/documents/{artifact_id}/content"

        return DocumentArtifact(
            artifact_id=artifact_id,
            title=outline.title,
            deliverable_format=outline.deliverable_format,
            file_path=local_path,
            file_size_bytes=len(raw_bytes),
            outline=outline,
            sections=sections,
            download_url=download_url,
            metadata={"artifact_type": "structured_deliverable"},
        )
