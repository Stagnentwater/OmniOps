"""PersonaContextBuilder for synthesizing dynamic user persona directives for LLM generation."""

from __future__ import annotations

import re
from typing import Any

from database.user_repository import UserProfile


def _sanitize_text(value: Any, max_len: int = 120) -> str:
    """Sanitize user input to prevent prompt injection and markdown breaking."""
    if not value or not isinstance(value, str):
        return ""
    # Strip markdown headers/fences and control characters
    cleaned = re.sub(r"[\r\n\x00-\x1f\x7f]+", " ", value)
    cleaned = re.sub(r"[`#*~|]+", "", cleaned)
    # Remove delimiter patterns that could fake system prompt sections
    cleaned = re.sub(r"---+", "-", cleaned)
    return cleaned.strip()[:max_len]


class PersonaContextBuilder:
    """Converts a validated UserProfile into authoritative system prompt directives."""

    DEFAULT_DESIGNATION = "Plant Personnel"
    DEFAULT_LEVEL = "intermediate"
    DEFAULT_DEPTH = "moderate"
    DEFAULT_SKILLS = ("General engineering",)

    LEVEL_GUIDELINES: dict[str, str] = {
        "beginner": (
            "- The user is a beginner in refinery operations. Explain foundational concepts and operational principles clearly.\n"
            "- Define all technical acronyms, differential terms, and industrial shorthand (e.g., DP, P&ID, fouling, LOTO).\n"
            "- Structure troubleshooting checks in a logical, step-by-step diagnostic sequence.\n"
            "- Use accessible, intuitive explanations without omitting physical mechanisms."
        ),
        "intermediate": (
            "- The user has working familiarity with plant operations. Standard refinery terminology may be used without exhaustive definitions.\n"
            "- Provide clear, structured diagnostic workflows referencing typical unit operations."
        ),
        "advanced": (
            "- The user possesses extensive engineering and practical operations background.\n"
            "- Focus on detailed process variables, control loop dynamics, and unit-specific parameters.\n"
            "- Do not define standard equipment types or fundamental engineering concepts."
        ),
        "expert": (
            "- The user is a senior industrial expert. Provide concise, high-density technical analysis.\n"
            "- Focus directly on differential pressure curves, Reynolds numbers, fouling factors, telemetry, and specific valve/piping restrictions.\n"
            "- Omit introductory definitions and basic operational principles entirely.\n"
            "- Deliver prioritized technical action items."
        ),
    }

    DEPTH_GUIDELINES: dict[str, str] = {
        "concise": "Keep the response focused, direct, and concise. Prioritize key diagnostic data over narrative elaboration.",
        "moderate": "Provide balanced technical explanations with adequate context and diagnostic steps.",
        "detailed": "Provide thorough, in-depth analysis covering operating mechanisms, potential causes, and detailed inspection procedures.",
    }

    @classmethod
    def build(cls, profile: UserProfile | dict[str, Any] | None) -> str:
        """Synthesize authoritative persona instructions from a user profile.
        
        Args:
            profile: UserProfile dataclass instance, dict, or None for guest/default.
            
        Returns:
            Authoritative persona prompt string ready to prepend or append to system prompts.
        """
        designation = cls.DEFAULT_DESIGNATION
        raw_level = cls.DEFAULT_LEVEL
        raw_depth = cls.DEFAULT_DEPTH
        skills_list: list[str] = list(cls.DEFAULT_SKILLS)

        if profile is not None:
            if isinstance(profile, UserProfile):
                designation = _sanitize_text(profile.designation) or designation
                raw_level = (profile.refinery_experience_level or "").lower().strip()
                raw_depth = (profile.preferred_explanation_depth or "").lower().strip()
                if profile.skill_set:
                    skills_list = [_sanitize_text(s, 60) for s in profile.skill_set if _sanitize_text(s, 60)]
            elif isinstance(profile, dict):
                designation = _sanitize_text(profile.get("designation")) or designation
                raw_level = str(profile.get("refinery_experience_level") or "").lower().strip()
                raw_depth = str(profile.get("preferred_explanation_depth") or "").lower().strip()
                raw_skills = profile.get("skill_set") or []
                if isinstance(raw_skills, list) and raw_skills:
                    skills_list = [_sanitize_text(s, 60) for s in raw_skills if _sanitize_text(s, 60)]

        # Fallback to defaults if unrecognized
        level = raw_level if raw_level in cls.LEVEL_GUIDELINES else cls.DEFAULT_LEVEL
        depth = raw_depth if raw_depth in cls.DEPTH_GUIDELINES else cls.DEFAULT_DEPTH
        skills_str = ", ".join(skills_list) if skills_list else "General engineering"

        level_rules = cls.LEVEL_GUIDELINES[level]
        depth_rules = cls.DEPTH_GUIDELINES[depth]

        return (
            "--- USER EXPERTISE & PERSONA DIRECTIVES ---\n"
            f"User Role: {designation}\n"
            f"Declared Skills: {skills_str}\n"
            f"Experience Level: {level.upper()}\n"
            f"Preferred Depth: {depth.upper()}\n\n"
            "COMMUNICATION RULES:\n"
            f"{level_rules}\n"
            f"{depth_rules}\n"
            "MANDATORY SAFETY CONSTRAINT: Never omit hazardous material warnings, high-pressure precautions, PPE requirements, or Lockout/Tagout procedures regardless of the user's expertise level. However, safety warnings must accompany the technical explanation and never replace or omit the primary answer to the user's technical question or diagram inspection.\n"
            "GROUNDING CONSTRAINT: Ground all technical facts in retrieved evidence. Do not invent plant equipment or operational data.\n"
            "---------------------------------------------"
        )
