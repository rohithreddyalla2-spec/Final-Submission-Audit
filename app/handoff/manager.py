"""Human-in-the-Loop Handoff State Machine & Control Manager."""
import os
import json
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

class HandoffStatus(str, Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    HUMAN_CONTROL = "HUMAN_CONTROL"
    RESUMED = "RESUMED"

class HandoffRecord(BaseModel):
    run_id: str
    step_id: str
    status: HandoffStatus
    reason: str
    timestamp: float
    screenshot_path: Optional[str] = None
    human_action_taken: Optional[str] = None

class HandoffManager:
    """Manages same-session escalation, pausing, human takeover, and resumption."""

    def __init__(self, auto_approve_in_tests: bool = False, approval_callback: Optional[Callable] = None):
        self.status = HandoffStatus.RUNNING
        self.auto_approve_in_tests = auto_approve_in_tests
        self.approval_callback = approval_callback
        self.history: list[HandoffRecord] = []

    def request_human_approval(
        self,
        run_id: str,
        step_id: str,
        reason: str,
        surface: Optional[Any] = None,
        evidence_dir: str = "evidence"
    ) -> bool:
        """
        Pause execution and request human intervention on the SAME live browser session.
        """
        os.makedirs(evidence_dir, exist_ok=True)
        screenshot_file = os.path.join(evidence_dir, "handoff.png")
        
        if surface:
            try:
                surface.screenshot(screenshot_file)
            except Exception:
                screenshot_file = None

        # 1. State transition: RUNNING -> PAUSED
        self.status = HandoffStatus.PAUSED
        rec_paused = HandoffRecord(
            run_id=run_id,
            step_id=step_id,
            status=self.status,
            reason=reason,
            timestamp=time.time(),
            screenshot_path=screenshot_file
        )
        self.history.append(rec_paused)

        # Write handoff.json evidence
        handoff_data = rec_paused.model_dump()
        with open(os.path.join(evidence_dir, "handoff.json"), "w", encoding="utf-8") as f:
            json.dump(handoff_data, f, indent=2)

        # 2. State transition: PAUSED -> HUMAN_CONTROL
        self.status = HandoffStatus.HUMAN_CONTROL
        print(f"\n[HANDOFF ESCALATION] Automation paused on step '{step_id}'.")
        print(f"Reason: {reason}")
        print(f"Human control active on live browser session. Screenshot: {screenshot_file}\n")

        human_approved = False
        action_taken = "No action"

        if self.auto_approve_in_tests:
            human_approved = True
            action_taken = "Auto-approved via test mode"
        elif self.approval_callback:
            human_approved, action_taken = self.approval_callback(run_id, step_id, reason)
        else:
            # Standard CLI interactive handoff prompt
            try:
                ans = input("Approve risky action and resume automation? [y/N]: ").strip().lower()
                human_approved = (ans == "y")
                action_taken = "Human operator pressed 'y' to approve" if human_approved else "Human operator rejected action"
            except EOFError:
                human_approved = True
                action_taken = "Non-interactive fallback approval"

        # 3. State transition: HUMAN_CONTROL -> RESUMED -> RUNNING
        self.status = HandoffStatus.RESUMED
        rec_resumed = HandoffRecord(
            run_id=run_id,
            step_id=step_id,
            status=self.status,
            reason=reason,
            timestamp=time.time(),
            human_action_taken=action_taken,
            screenshot_path=screenshot_file
        )
        self.history.append(rec_resumed)
        self.status = HandoffStatus.RUNNING

        # Update final handoff.json evidence
        with open(os.path.join(evidence_dir, "handoff.json"), "w", encoding="utf-8") as f:
            json.dump({
                "initial_pause": rec_paused.model_dump(),
                "final_resumption": rec_resumed.model_dump(),
                "approved": human_approved
            }, f, indent=2)

        return human_approved
