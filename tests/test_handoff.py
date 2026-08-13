"""Integration & unit tests for Human-in-the-Loop handoff mechanism."""
import os
import json
import pytest
from app.artifacts.schema import CapabilityArtifact, Step, StepAction, TargetSpec
from app.surface.locator import LocatorSpec
from app.replay.engine import ReplayEngine
from app.replay.result import ReplayStatus
from app.handoff.manager import HandoffManager, HandoffStatus

def test_handoff_pause_and_same_session_resumption(surface, tmp_path):
    """
    Verify handoff flow:
    1. Replay engine encounters a risky action step.
    2. HandoffManager pauses execution (RUNNING -> PAUSED -> HUMAN_CONTROL).
    3. Live browser session state is preserved on the SAME page context.
    4. Operator approves action (HUMAN_CONTROL -> RESUMED -> RUNNING).
    5. Replay engine resumes and completes execution.
    """
    evidence_dir = str(tmp_path / "evidence")

    # Workflow B creation step (marked risky)
    artifact = CapabilityArtifact(
        capability_id="member.subaccount.create",
        description="Open new sub-account with risky confirmation step",
        steps=[
            Step(
                step_id="step_1_nav",
                action=StepAction.NAVIGATE,
                url="http://127.0.0.1:8000/members/12345/subaccounts/new"
            ),
            Step(
                step_id="step_2_fill_name",
                action=StepAction.FILL,
                locator=LocatorSpec(role="textbox", label="Sub-Account Label / Custom Name", css_fallback="#subaccount_name_input"),
                value="Emergency Savings"
            ),
            Step(
                step_id="step_3_submit_risky",
                action=StepAction.CLICK,
                locator=LocatorSpec(role="button", name="Submit & Create Sub-Account", css_fallback="#btn-submit-create-subaccount"),
                is_risky=True
            )
        ]
    )

    handoff_mgr = HandoffManager(auto_approve_in_tests=True)
    engine = ReplayEngine(surface=surface)

    result = engine.execute(
        artifact=artifact,
        input_params={},
        handoff_manager=handoff_mgr
    )

    # 1. Verify replay completed successfully after resumption
    assert result.status == ReplayStatus.SUCCESS

    # 2. Verify same browser session reached confirmation page
    current_url = surface.observe()["url"]
    assert "/subaccounts/confirmation" in current_url

    # 3. Verify handoff state history recorded pause and resumption
    assert len(handoff_mgr.history) == 2
    assert handoff_mgr.history[0].status == HandoffStatus.PAUSED
    assert handoff_mgr.history[1].status == HandoffStatus.RESUMED
    assert handoff_mgr.history[1].human_action_taken == "Auto-approved via test mode"
