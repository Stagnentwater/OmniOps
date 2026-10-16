"""Domain models for outline-first structured document generation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class OutlineSection:
    """A section or slide in a structured document outline."""

    section_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    level: int = 1
    description: str = ""
    required_elements: list[str] = field(default_factory=list)
    subsections: list[OutlineSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "level": self.level,
            "description": self.description,
            "required_elements": self.required_elements,
            "subsections": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.subsections],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutlineSection:
        subs = [cls.from_dict(s) for s in data.get("subsections", [])]
        return cls(
            section_id=str(data.get("section_id", str(uuid.uuid4())[:8])),
            title=str(data.get("title", "")),
            level=int(data.get("level", 1)),
            description=str(data.get("description", "")),
            required_elements=list(data.get("required_elements", [])),
            subsections=subs,
        )


@dataclass
class DocumentOutline:
    """The master outline for a deliverable document."""

    title: str
    deliverable_format: str  # "docx", "pdf", "pptx"
    intended_audience: str = "Plant Operations & Reliability Engineering"
    outline_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sections: list[OutlineSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate outline structure before section generation."""
        errors: list[str] = []
        if not self.title.strip():
            errors.append("Document title is required.")
        if self.deliverable_format not in {"docx", "pdf", "pptx"}:
            errors.append(f"Unsupported deliverable format: '{self.deliverable_format}'.")
        if not self.sections:
            errors.append("Outline must contain at least one section.")
        for idx, sec in enumerate(self.sections):
            if not sec.title.strip():
                errors.append(f"Section at index {idx} has an empty title.")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "outline_id": self.outline_id,
            "title": self.title,
            "deliverable_format": self.deliverable_format,
            "intended_audience": self.intended_audience,
            "sections": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.sections],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentOutline:
        secs = [OutlineSection.from_dict(s) for s in data.get("sections", [])]
        return cls(
            title=str(data.get("title", "")),
            deliverable_format=str(data.get("deliverable_format", "docx")),
            intended_audience=str(data.get("intended_audience", "")),
            outline_id=str(data.get("outline_id", str(uuid.uuid4()))),
            sections=secs,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class GeneratedSection:
    """A generated and verified content section."""

    section_id: str
    title: str
    content_markdown: str = ""
    tables: list[dict[str, Any]] = field(default_factory=list)
    callouts: list[dict[str, str]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    verification_status: str = "PENDING"

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content_markdown": self.content_markdown,
            "tables": self.tables,
            "callouts": self.callouts,
            "citations": self.citations,
            "verification_status": self.verification_status,
        }


@dataclass
class DocumentArtifact:
    """A fully generated, stored, and downloadable file deliverable."""

    artifact_id: str
    title: str
    deliverable_format: str
    file_path: str
    file_size_bytes: int
    outline: DocumentOutline
    sections: list[GeneratedSection]
    download_url: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def file_name(self) -> str:
        """Return base filename of the generated artifact."""
        import os
        return os.path.basename(self.file_path) if self.file_path else f"{self.artifact_id}.{self.deliverable_format}"

    @property
    def format(self) -> str:
        """Return format alias matching deliverable_format."""
        return self.deliverable_format

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "document_id": self.artifact_id,
            "title": self.title,
            "file_name": self.file_name,
            "format": self.format,
            "deliverable_format": self.deliverable_format,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "download_url": self.download_url,
            "created_at": self.created_at,
            "section_count": len(self.sections),
            "metadata": self.metadata,
        }
