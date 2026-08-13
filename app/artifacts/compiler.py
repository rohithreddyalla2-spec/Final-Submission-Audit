"""Capability Artifact Compiler converting discovery trajectory to validated artifacts."""
import os
import json
from typing import List, Dict, Any, Optional
from app.artifacts.schema import (
    CapabilityArtifact, Step, StepAction, TargetSpec,
    InputParamDef, OutputParamDef, Checkpoint, CheckpointType
)
from app.surface.locator import LocatorSpec

def compile_trajectory_to_artifact(
    trajectory: List[Dict[str, Any]],
    capability_id: str,
    description: str,
    inputs: Dict[str, InputParamDef],
    outputs: Dict[str, OutputParamDef],
    checkpoint: Checkpoint,
    output_dir: str = "artifacts"
) -> CapabilityArtifact:
    """
    Compile discovery trajectory into a clean, validated capability artifact.
    Strips LLM reasoning and converts raw actions into parameterized, robust steps.
    """
    compiled_steps: List[Step] = []

    for idx, raw_step in enumerate(trajectory, start=1):
        action_str = raw_step.get("action", "").lower()
        if not action_str:
            continue

        action = StepAction(action_str)
        target_dict = raw_step.get("target") or {}
        
        # Build LocatorSpec from target dict
        locator = None
        if action != StepAction.NAVIGATE and target_dict:
            locator = LocatorSpec(
                role=target_dict.get("role"),
                name=target_dict.get("name"),
                label=target_dict.get("label"),
                semantic_attr=target_dict.get("semantic_attr"),
                text=target_dict.get("text"),
                css_fallback=target_dict.get("css_fallback")
            )

        # Check if step is risky (e.g. submitting creation forms or sub-accounts)
        is_risky = raw_step.get("is_risky", False)
        if not is_risky and action in [StepAction.CLICK, StepAction.FILL]:
            desc_lower = (raw_step.get("description") or "").lower()
            name_lower = (target_dict.get("name") or "").lower()
            text_lower = (target_dict.get("text") or "").lower()
            if any(k in desc_lower or k in name_lower or k in text_lower for k in ["submit & create", "create", "open sub-account", "confirm"]):
                is_risky = True

        step = Step(
            step_id=f"step_{idx}_{action.value}",
            action=action,
            locator=locator,
            url=raw_step.get("url"),
            value=raw_step.get("value"),
            input_param=raw_step.get("input_param"),
            output_param=raw_step.get("output_param"),
            expectation=raw_step.get("expectation"),
            is_risky=is_risky,
            description=raw_step.get("description", f"Execute {action.value}")
        )
        compiled_steps.append(step)

    artifact = CapabilityArtifact(
        schema_version="1.0",
        capability_id=capability_id,
        description=description,
        target=TargetSpec(surface="browser", application="demo-bank"),
        inputs=inputs,
        outputs=outputs,
        steps=compiled_steps,
        checkpoint=checkpoint
    )

    # Validate artifact by serializing and deserializing
    serialized = artifact.model_dump_json(indent=2)
    validated_artifact = CapabilityArtifact.model_validate_json(serialized)

    # Save artifact to file
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{capability_id.replace('.', '_')}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(serialized)

    return validated_artifact
