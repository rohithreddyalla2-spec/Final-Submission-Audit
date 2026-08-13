"""Unit tests for Capability Artifact schema, validation, missing inputs, and invalid steps."""
import pytest
from pydantic import ValidationError
from app.artifacts.schema import (
    CapabilityArtifact, Step, StepAction, TargetSpec,
    InputParamDef, OutputParamDef, Checkpoint, CheckpointType
)
from app.surface.locator import LocatorSpec

def test_valid_artifact_serialization():
    """Verify clean serialization and deserialization of valid capability artifact."""
    artifact = CapabilityArtifact(
        schema_version="1.0",
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
                step_id="step_1",
                action=StepAction.NAVIGATE,
                url="http://127.0.0.1:8000/members/12345"
            ),
            Step(
                step_id="step_2",
                action=StepAction.READ,
                locator=LocatorSpec(role="cell", css_fallback="#val-savings-balance"),
                output_param="savings_balance"
            )
        ],
        checkpoint=Checkpoint(
            type=CheckpointType.TEXT_CONTAINS,
            expected_value="Member Account Details"
        )
    )

    json_str = artifact.model_dump_json()
    reloaded = CapabilityArtifact.model_validate_json(json_str)

    assert reloaded.capability_id == "member.savings_balance.lookup"
    assert len(reloaded.steps) == 2
    assert reloaded.steps[1].action == StepAction.READ
    assert reloaded.steps[1].locator.css_fallback == "#val-savings-balance"

def test_invalid_artifact_schema():
    """Verify validation error when step action is invalid."""
    with pytest.raises(ValidationError):
        Step.model_validate({
            "step_id": "bad_step",
            "action": "invalid_action_type"
        })

def test_missing_input_parameter_handling():
    """Verify artifact defines required inputs properly."""
    artifact = CapabilityArtifact(
        capability_id="test.capability",
        description="Test description",
        inputs={
            "required_field": InputParamDef(type="string", required=True)
        }
    )
    assert artifact.inputs["required_field"].required is True
    assert artifact.inputs["required_field"].default is None
