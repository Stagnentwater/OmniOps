"""Industrial Permit Human Review, Sign-off State Machine, and Audit Logging."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from permits.permit_models import IndustrialPermit, PermitStatus
from permits.safety_validator import PermitSafetyValidator, SafetyValidationResult

logger = logging.getLogger(__name__)


class PermitReviewService:
    """Manages the strict state machine for industrial permit approvals and human verification."""

    def __init__(self, validator: PermitSafetyValidator | None = None) -> None:
        self._validator = validator or PermitSafetyValidator()

    def submit_for_review(self, permit: IndustrialPermit) -> tuple[IndustrialPermit, SafetyValidationResult]:
        """Validate permit and transition to READY_FOR_REVIEW if all safety gates pass."""
        val_result = self._validator.validate(permit)

        if not val_result.is_valid or permit.missing_information:
            permit.status = PermitStatus.VERIFICATION_INCOMPLETE
            logger.info("Permit %s failed review gate. Status: VERIFICATION_INCOMPLETE", permit.permit_id)
        else:
            permit.status = PermitStatus.READY_FOR_REVIEW
            logger.info("Permit %s passed review gate. Status: READY_FOR_REVIEW", permit.permit_id)

        return permit, val_result

    def sign_off_permit(
        self,
        permit: IndustrialPermit,
        reviewer_id: str,
        reviewer_name: str,
        reviewer_role: str,
        signature_confirmed: bool,
        is_automated_agent: bool = False,
    ) -> IndustrialPermit:
        """Sign off permit with explicit human credentials and audit logging.
        
        CRITICAL INDUSTRIAL SAFETY RULE:
        Autonomous AI agents are strictly forbidden from signing off or authorizing permits.
        """
        # Hard security block
        if is_automated_agent:
            logger.error("CRITICAL SAFETY BLOCK: Automated AI agent tried to authorize permit %s", permit.permit_id)
            raise PermissionError(
                "CRITICAL SAFETY VIOLATION: Automated AI agents are strictly prohibited from authorizing industrial permits. Qualified human sign-off is mandatory."
            )

        if not signature_confirmed:
            raise ValueError("Explicit signature confirmation is mandatory to authorize an industrial permit.")

        if permit.status != PermitStatus.READY_FOR_REVIEW:
            raise ValueError(
                f"Permit {permit.permit_id} cannot be signed off while in status '{permit.status.value}'. Must be 'READY_FOR_REVIEW'."
            )

        # Transition status
        permit.status = PermitStatus.AUTHORIZED_BY_HUMAN
        permit.authorized_by = f"{reviewer_name} ({reviewer_role}, ID: {reviewer_id})"
        permit.authorized_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Permit %s AUTHORIZED_BY_HUMAN by %s at %s",
            permit.permit_id,
            permit.authorized_by,
            permit.authorized_at,
        )
        return permit

    def reject_permit(
        self,
        permit: IndustrialPermit,
        reviewer_id: str,
        reason: str,
    ) -> IndustrialPermit:
        """Reject permit during review, providing actionable deficiencies."""
        permit.status = PermitStatus.VERIFICATION_INCOMPLETE
        permit.missing_information.append(f"Rejected by reviewer {reviewer_id}: {reason}")
        logger.info("Permit %s rejected by %s: %s", permit.permit_id, reviewer_id, reason)
        return permit
