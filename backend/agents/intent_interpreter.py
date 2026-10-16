"""LLM-Driven Intent Interpretation and Structured Planning Engine for OmniOps.

Interprets user requests into a structured intent representation (ParsedIntent)
that identifies the intended outcome, output format, target equipment, required tools,
missing information, safety considerations, and recommended plan steps.

Includes a fast deterministic fallback to ensure reliable operation when LLM
services are unavailable or during rapid local evaluation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Standard industrial equipment tag regex: e.g., P-101, P-101A, E-204, V-101, TK-500, MOV-101A
_EQUIPMENT_TAG_PATTERN = re.compile(r"\b([A-Z]{1,4}-\d{2,5}[A-Z0-9]?)\b")


class TaskType(str, Enum):
    """Categorized task types for OmniOps operations."""

    QUESTION_ANSWER = "question_answer"
    CALCULATION = "calculation"
    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_GENERATION = "document_generation"
    PERMIT_GENERATION = "permit_generation"
    SYSTEM_STATUS = "system_status"
    CLARIFICATION_NEEDED = "clarification_needed"


class DeliverableFormat(str, Enum):
    """Supported artifact output formats."""

    NONE = "none"
    DOCX = "docx"
    PDF = "pdf"
    PPTX = "pptx"


@dataclass
class ParsedIntent:
    """Structured representation of the user's interpreted intent."""

    task_type: TaskType
    target_deliverable: DeliverableFormat
    primary_objective: str
    target_equipment: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    safety_critical: bool = False
    constraints: list[str] = field(default_factory=list)
    confidence: float = 1.0
    recommended_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert ParsedIntent to dictionary for API emission and metadata storage."""
        return {
            "task_type": self.task_type.value,
            "target_deliverable": self.target_deliverable.value,
            "primary_objective": self.primary_objective,
            "target_equipment": self.target_equipment,
            "required_tools": self.required_tools,
            "missing_information": self.missing_information,
            "safety_critical": self.safety_critical,
            "constraints": self.constraints,
            "confidence": self.confidence,
            "recommended_steps": self.recommended_steps,
        }


class IntentInterpreter:
    """Interprets user intent using LLM reasoning with deterministic fallbacks.

    The interpreter acts prior to the agent tool loop:
    1. Examines the user query and recent conversational context.
    2. Determines the high-level task type and deliverable expectations.
    3. Detects target plant equipment tags.
    4. Identifies missing mandatory inputs (e.g. equipment tag for permit).
    5. Formulates recommended plan steps while preserving deterministic safety limits.
    """

    def __init__(self, llm_provider: Any | None = None, timeout_seconds: float = 8.0) -> None:
        self._llm = llm_provider
        self._timeout_seconds = timeout_seconds

    def interpret(
        self,
        query: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> ParsedIntent:
        """Interpret user query into a ParsedIntent.

        Attempts LLM-based interpretation if a provider is configured;
        falls back gracefully to deterministic rule-based analysis.
        """
        clean_query = (query or "").strip()
        if not clean_query:
            return ParsedIntent(
                task_type=TaskType.QUESTION_ANSWER,
                target_deliverable=DeliverableFormat.NONE,
                primary_objective="Empty query",
                confidence=0.0,
            )

        # Attempt LLM interpretation if available
        if self._llm is not None:
            try:
                llm_intent = self._llm_interpret(clean_query, conversation_history)
                if llm_intent is not None:
                    return llm_intent
            except Exception as e:
                logger.debug("LLM intent interpretation failed or timed out, falling back to deterministic: %s", e)

        # Deterministic fallback
        return self._deterministic_interpret(clean_query)

    def _deterministic_interpret(self, query: str) -> ParsedIntent:
        """Fast, robust regex- and lexicon-based intent classifier."""
        q_lower = query.lower()
        equipment_tags = sorted(list(set(_EQUIPMENT_TAG_PATTERN.findall(query))))

        # 1. Check for Work Permit Requests
        permit_keywords = [
            "permit",
            "safe work permit",
            "hot work",
            "cold work",
            "confined space",
            "lockout",
            "tagout",
            "loto",
            "isolate this equipment",
            "isolation documentation",
            "safety officer can review",
            "pre-work safety",
        ]
        is_permit = any(k in q_lower for k in permit_keywords)

        if is_permit:
            # Determine specific deliverable format requested
            deliverable = DeliverableFormat.DOCX  # Default editable format for permits
            if "pdf" in q_lower:
                deliverable = DeliverableFormat.PDF
            elif "presentation" in q_lower or "pptx" in q_lower or "slides" in q_lower:
                deliverable = DeliverableFormat.PPTX

            missing_info: list[str] = []
            if not equipment_tags:
                missing_info.append("target_equipment_tag")

            recommended = [
                "Identify target equipment and plant operational area",
                "Retrieve operating procedures and hazardous isolation requirements",
                "Extract hazard controls, PPE requirements, and atmospheric limits",
                "Draft permit structured fields using approved safety template",
                "Execute Self-RAG and CoV evidence verification on safety claims",
                "Flag any unverified fields for mandatory human sign-off",
            ]

            return ParsedIntent(
                task_type=TaskType.PERMIT_GENERATION,
                target_deliverable=deliverable,
                primary_objective=f"Prepare industrial work permit draft for {', '.join(equipment_tags) if equipment_tags else 'specified work'}",
                target_equipment=equipment_tags,
                required_tools=["search_documents", "search_knowledge_graph"],
                missing_information=missing_info,
                safety_critical=True,
                constraints=["Draft only", "Must flag unverified fields", "Autonomous authorization prohibited"],
                confidence=0.95,
                recommended_steps=recommended,
            )

        # 2. Check for Document / Presentation Deliverables
        doc_patterns = [
            r"\b(generate|draft|prepare|create|write|export|produce|make|need|compile|build)\b.*\b(document|report|deliverable|documentation|summary|overview|brief|paperwork|manual|handover)\b",
            r"\b(document\s+generation|generate\s+a\s+doc|generate\s+document|create\s+doc|need\s+a\s+doc)\b",
            r"\b(presentation|slide deck|slides|powerpoint|deck)\b",
            r"\b(word document|docx|export pdf|export docx|export pptx|as a pdf|as a docx|as a pptx|as a word)\b",
            r"\b(pdf|docx|pptx)\s+(report|document|summary|overview)\b",
        ]
        is_document = any(re.search(pat, q_lower) for pat in doc_patterns)

        if is_document:
            deliverable = DeliverableFormat.DOCX
            if "pdf" in q_lower:
                deliverable = DeliverableFormat.PDF
            elif any(k in q_lower for k in ["pptx", "powerpoint", "slides", "presentation", "deck"]):
                deliverable = DeliverableFormat.PPTX

            recommended = [
                "Retrieve technical evidence from documents and knowledge graph",
                "Construct structured deliverable outline",
                "Validate outline structure against objective",
                "Generate section and slide contents individually",
                "Assemble and validate final binary artifact",
            ]

            return ParsedIntent(
                task_type=TaskType.DOCUMENT_GENERATION,
                target_deliverable=deliverable,
                primary_objective=f"Generate {deliverable.value.upper()} deliverable document",
                target_equipment=equipment_tags,
                required_tools=["search_documents", "search_knowledge_graph"],
                missing_information=[],
                safety_critical=False,
                constraints=["Preserve outline hierarchy", "Cite technical sources"],
                confidence=0.92,
                recommended_steps=recommended,
            )

        # 3. Check for Numerical Calculations
        calc_keywords = [
            "calculate",
            "compute",
            "what is the sum",
            "convert unit",
            "reynolds number",
            "pressure drop",
            "heat duty",
            "delta p",
            "mass flow",
            "efficiency",
            "difference between",
        ]
        is_calc = any(k in q_lower for k in calc_keywords) and any(
            c in q_lower for c in ["+", "-", "*", "/", "%", "kpa", "psi", "bar", "kg/h", "m3/h", "celsius", "fahrenheit", "kw", "mw"]
        )

        if is_calc or q_lower.startswith("calculate ") or q_lower.startswith("compute "):
            return ParsedIntent(
                task_type=TaskType.CALCULATION,
                target_deliverable=DeliverableFormat.NONE,
                primary_objective="Execute deterministic engineering calculation",
                target_equipment=equipment_tags,
                required_tools=["calculate", "search_documents"],
                missing_information=[],
                safety_critical=False,
                constraints=["Use deterministic SubprocessSandbox only", "No manual mental arithmetic"],
                confidence=0.90,
                recommended_steps=[
                    "Locate exact equipment measurements or design parameters",
                    "Execute calculation in deterministic Python sandbox",
                    "Format result with explicit units and formula",
                ],
            )

        # 4. Check for Image / Diagram Analysis
        img_keywords = [
            "attached image",
            "p&id",
            "pid",
            "diagram",
            "schematic",
            "piping",
            "flow sheet",
            "inspect this image",
            "what is shown in the picture",
        ]
        is_img = any(k in q_lower for k in img_keywords)

        if is_img:
            rec_tool = "analyze_pid" if any(k in q_lower for k in ["p&id", "pid", "piping", "schematic", "diagram"]) else "analyze_image"
            return ParsedIntent(
                task_type=TaskType.IMAGE_ANALYSIS,
                target_deliverable=DeliverableFormat.NONE,
                primary_objective="Analyze attached visual diagram or equipment image",
                target_equipment=equipment_tags,
                required_tools=[rec_tool],
                missing_information=[],
                safety_critical=False,
                constraints=["Examine image first", "Report observed tags truthfully"],
                confidence=0.94,
                recommended_steps=[
                    f"Invoke {rec_tool} to extract visual observations",
                    "Walk through equipment tags, valves, and flow connections",
                    "Preserve visual context in session memory for follow-ups",
                ],
            )

        # 5. Check for System Status
        status_keywords = ["system status", "health check", "operational status", "check services"]
        if any(k in q_lower for k in status_keywords):
            return ParsedIntent(
                task_type=TaskType.SYSTEM_STATUS,
                target_deliverable=DeliverableFormat.NONE,
                primary_objective="Check system operational status and connectivity",
                target_equipment=[],
                required_tools=["system_status"],
                missing_information=[],
                safety_critical=False,
                constraints=[],
                confidence=0.98,
                recommended_steps=["Query operational health of PostgreSQL, Neo4j, Qdrant, Ollama"],
            )

        # 6. Default: Standard Question & Answer
        return ParsedIntent(
            task_type=TaskType.QUESTION_ANSWER,
            target_deliverable=DeliverableFormat.NONE,
            primary_objective=f"Answer question regarding {', '.join(equipment_tags) if equipment_tags else 'plant operations'}",
            target_equipment=equipment_tags,
            required_tools=["search_documents", "search_knowledge_graph"],
            missing_information=[],
            safety_critical=False,
            constraints=["Cite evidence from retrieved context"],
            confidence=0.85,
            recommended_steps=[
                "Retrieve evidence from documents or knowledge graph",
                "Synthesize answer strictly grounded in retrieved evidence",
            ],
        )

    def _llm_interpret(
        self,
        query: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> ParsedIntent | None:
        """Prompt LLM for structured intent JSON."""
        system_prompt = (
            "You are an Industrial Intent and Task Classifier for an engineering platform. "
            "Analyze the user request (and recent conversation context) to understand the user's underlying intent, "
            "even if phrasing varies, is informal, or doesn't use exact keywords.\n"
            "If the user wants a document, formal report, summary file, presentation, handover document, or downloadable deliverable, "
            "classify task_type as 'document_generation' and identify target_deliverable ('docx', 'pdf', 'pptx').\n"
            "If the user wants a safe work permit, hot work permit, cold work permit, confined space entry, or LOTO isolation documentation, "
            "classify task_type as 'permit_generation'.\n"
            "Return ONLY a valid JSON object with this exact structure:\n"
            "{\n"
            '  "task_type": "question_answer" | "calculation" | "image_analysis" | "document_generation" | "permit_generation" | "system_status" | "clarification_needed",\n'
            '  "target_deliverable": "none" | "docx" | "pdf" | "pptx",\n'
            '  "primary_objective": "concise description of what user wants to achieve",\n'
            '  "target_equipment": ["equipment tags if mentioned, e.g. P-101A"],\n'
            '  "required_tools": ["search_documents", "search_knowledge_graph", "calculate", "analyze_image", "analyze_pid"],\n'
            '  "missing_information": [],\n'
            '  "safety_critical": true | false,\n'
            '  "constraints": [],\n'
            '  "confidence": 0.0 - 1.0,\n'
            '  "recommended_steps": ["step 1", "step 2"]\n'
            "}\n"
            "Do not output markdown code blocks, explanation or introductory text. Return raw JSON only."
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # Inject recent turns for multi-turn intent resolution
        if conversation_history:
            for turn in conversation_history[-2:]:
                r = turn.get("role") if isinstance(turn, dict) else getattr(turn, "role", None)
                c = turn.get("content") if isinstance(turn, dict) else getattr(turn, "content", None)
                if r in ("user", "assistant") and c:
                    messages.append({"role": r, "content": str(c)[:300]})

        messages.append({"role": "user", "content": f"User Request: {query}"})

        # Invoke provider
        response = self._llm.chat(messages=messages, tools=None)
        content = getattr(response, "content", "") or ""
        clean_content = content.strip()

        # Extract JSON substring robustly
        json_match = re.search(r"\{[\s\S]*\}", clean_content)
        if json_match:
            clean_content = json_match.group(0)

        parsed = json.loads(clean_content)

        # Validate task type with fuzzy mapping
        raw_tt = str(parsed.get("task_type", "question_answer")).lower()
        if raw_tt in TaskType._value2member_map_:
            task_type = TaskType(raw_tt)
        elif "permit" in raw_tt or "loto" in raw_tt:
            task_type = TaskType.PERMIT_GENERATION
        elif "document" in raw_tt or "doc" in raw_tt or "report" in raw_tt or "slide" in raw_tt:
            task_type = TaskType.DOCUMENT_GENERATION
        elif "calc" in raw_tt:
            task_type = TaskType.CALCULATION
        elif "image" in raw_tt or "pid" in raw_tt:
            task_type = TaskType.IMAGE_ANALYSIS
        else:
            task_type = TaskType.QUESTION_ANSWER

        # Validate deliverable with fuzzy mapping
        raw_deliv = str(parsed.get("target_deliverable", "none")).lower()
        if raw_deliv in DeliverableFormat._value2member_map_:
            deliverable = DeliverableFormat(raw_deliv)
        elif "pdf" in raw_deliv:
            deliverable = DeliverableFormat.PDF
        elif any(k in raw_deliv for k in ["ppt", "slide", "presentation", "deck"]):
            deliverable = DeliverableFormat.PPTX
        elif any(k in raw_deliv for k in ["doc", "word"]):
            deliverable = DeliverableFormat.DOCX
        else:
            deliverable = DeliverableFormat.NONE

        equipment = list(parsed.get("target_equipment", []))
        if not equipment:
            equipment = sorted(list(set(_EQUIPMENT_TAG_PATTERN.findall(query))))

        return ParsedIntent(
            task_type=task_type,
            target_deliverable=deliverable,
            primary_objective=str(parsed.get("primary_objective", "Process user request")),
            target_equipment=equipment,
            required_tools=list(parsed.get("required_tools", ["search_documents", "search_knowledge_graph"])),
            missing_information=list(parsed.get("missing_information", [])),
            safety_critical=bool(parsed.get("safety_critical", task_type == TaskType.PERMIT_GENERATION)),
            constraints=list(parsed.get("constraints", [])),
            confidence=float(parsed.get("confidence", 0.9)),
            recommended_steps=list(parsed.get("recommended_steps", [])),
        )
