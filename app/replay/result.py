"""Typed Replay Result & Error Taxonomy Models."""
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class ReplayStatus(str, Enum):
    SUCCESS = "success"
    BUSINESS_OUTCOME = "business_outcome"
    RECOVERABLE_FAILURE = "recoverable_failure"
    HARD_FAILURE = "hard_failure"

class ErrorCode(str, Enum):
    # Business Outcomes
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    
    # Recoverable Failure Conditions
    TRANSIENT_LOAD_FAILURE = "TRANSIENT_LOAD_FAILURE"
    UNEXPECTED_DIALOG = "UNEXPECTED_DIALOG"

    # Hard Automation/System Failures
    APPLICATION_ERROR = "APPLICATION_ERROR"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"
    LOCATOR_FAILURE = "LOCATOR_FAILURE"
    RISKY_ACTION_PAUSED = "RISKY_ACTION_PAUSED"
    SAFETY_POLICY_VIOLATION = "SAFETY_POLICY_VIOLATION"
    CHECKPOINT_FAILED = "CHECKPOINT_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class ReplayResult(BaseModel):
    """Structured, typed execution result returned by the deterministic replay engine."""
    status: ReplayStatus
    code: Optional[ErrorCode] = None
    step_id: Optional[str] = None
    capability_id: str = ""
    outputs: Dict[str, Any] = Field(default_factory=dict)
    expected: Optional[str] = None
    observed: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    evidence_path: Optional[str] = None
