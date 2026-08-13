"""Integration & unit tests for Deterministic Replay Engine and Fault Injection scenarios."""
import pytest
from app.artifacts.schema import (
    CapabilityArtifact, Step, StepAction, TargetSpec,
    InputParamDef, OutputParamDef, Checkpoint, CheckpointType
)
from app.surface.locator import LocatorSpec
from app.replay.engine import ReplayEngine
from app.replay.result import ReplayStatus, ErrorCode
from app.demo_bank.models import GLOBAL_FAULT_STATE

def get_lookup_artifact() -> CapabilityArtifact:
    return CapabilityArtifact(
        capability_id="member.savings_balance.lookup",
        description="Look up member savings balance",
        inputs={
            "member_id": InputParamDef(type="string", required=True, default="12345")
        },
        outputs={
            "savings_balance": OutputParamDef(type="number", description="Savings balance")
        },
        steps=[
            Step(
                step_id="step_1_nav",
                action=StepAction.NAVIGATE,
                url="http://127.0.0.1:8000/members"
            ),
            Step(
                step_id="step_2_fill_search",
                action=StepAction.FILL,
                locator=LocatorSpec(role="textbox", label="Search by Member ID", css_fallback="#search_member_id_input"),
                input_param="member_id"
            ),
            Step(
                step_id="step_3_click_search",
                action=StepAction.CLICK,
                locator=LocatorSpec(role="button", name="Search Member", css_fallback="#btn-search-member")
            ),
            Step(
                step_id="step_4_view_details",
                action=StepAction.CLICK,
                locator=LocatorSpec(role="link", name="View Details & Accounts", css_fallback="#view-member-12345")
            ),
            Step(
                step_id="step_5_read_balance",
                action=StepAction.READ,
                locator=LocatorSpec(semantic_attr={"id": "val-savings-balance"}, css_fallback="#val-savings-balance"),
                output_param="savings_balance"
            )
        ],
        checkpoint=Checkpoint(
            type=CheckpointType.TEXT_CONTAINS,
            expected_value="Member Account Details"
        )
    )

def test_successful_replay_lookup(surface):
    """Test successful replay reading member 12345 savings balance."""
    artifact = get_lookup_artifact()
    engine = ReplayEngine(surface=surface)

    result = engine.execute(artifact, input_params={"member_id": "12345"})

    assert result.status == ReplayStatus.SUCCESS
    assert result.capability_id == "member.savings_balance.lookup"
    assert result.outputs.get("savings_balance") == 12450.32

def test_member_not_found_business_outcome(surface):
    """Test member lookup for non-existent member 99999 resulting in MEMBER_NOT_FOUND business outcome."""
    artifact = CapabilityArtifact(
        capability_id="member.savings_balance.lookup",
        description="Look up member savings balance",
        inputs={"member_id": InputParamDef(type="string", required=True)},
        steps=[
            Step(
                step_id="step_1_nav",
                action=StepAction.NAVIGATE,
                url="http://127.0.0.1:8000/members/99999"
            )
        ]
    )
    engine = ReplayEngine(surface=surface)

    result = engine.execute(artifact, input_params={"member_id": "99999"})

    assert result.status == ReplayStatus.BUSINESS_OUTCOME
    assert result.code == ErrorCode.MEMBER_NOT_FOUND

def set_fault_state(**kwargs):
    """Set global fault state in memory and sync via HTTP to running server."""
    for k, v in kwargs.items():
        setattr(GLOBAL_FAULT_STATE, k, v)
    try:
        import requests
        requests.post("http://127.0.0.1:8000/admin/inject-state", json=GLOBAL_FAULT_STATE.model_dump(), timeout=1)
    except Exception:
        pass

def test_validation_error_fault(surface):
    """Test validation error fault injection."""
    set_fault_state(validation_error=True)
    artifact = CapabilityArtifact(
        capability_id="subaccount.create",
        description="Create sub-account",
        steps=[
            Step(
                step_id="step_1_nav",
                action=StepAction.NAVIGATE,
                url="http://127.0.0.1:8000/members/12345/subaccounts/new"
            ),
            Step(
                step_id="step_2_submit",
                action=StepAction.CLICK,
                locator=LocatorSpec(role="button", name="Submit & Create Sub-Account", css_fallback="#btn-submit-create-subaccount")
            )
        ]
    )
    engine = ReplayEngine(surface=surface)
    result = engine.execute(artifact, input_params={})

    assert result.status == ReplayStatus.BUSINESS_OUTCOME
    assert result.code == ErrorCode.VALIDATION_ERROR

def test_session_timeout_fault(surface):
    """Test session timeout fault injection leading to HARD_FAILURE."""
    set_fault_state(session_timeout=True)
    artifact = get_lookup_artifact()
    engine = ReplayEngine(surface=surface)

    result = engine.execute(artifact, input_params={"member_id": "12345"})

    assert result.status == ReplayStatus.HARD_FAILURE
    assert result.code == ErrorCode.SESSION_TIMEOUT

def test_unexpected_dialog_fault(surface):
    """Test blocking maintenance dialog fault injection leading to RECOVERABLE_FAILURE."""
    set_fault_state(unexpected_dialog=True)
    artifact = get_lookup_artifact()
    engine = ReplayEngine(surface=surface)

    result = engine.execute(artifact, input_params={"member_id": "12345"})

    assert result.status == ReplayStatus.RECOVERABLE_FAILURE
    assert result.code == ErrorCode.UNEXPECTED_DIALOG

def test_application_error_fault(surface):
    """Test 500 internal server error fault injection leading to HARD_FAILURE."""
    set_fault_state(application_error=True)
    artifact = get_lookup_artifact()
    engine = ReplayEngine(surface=surface)

    result = engine.execute(artifact, input_params={"member_id": "12345"})

    assert result.status == ReplayStatus.HARD_FAILURE
    assert result.code == ErrorCode.APPLICATION_ERROR

