"""Typed, serializable, versioned Capability Artifact schema definition."""
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from app.surface.locator import LocatorSpec

class StepAction(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    READ = "read"
    WAIT = "wait"

class InputParamDef(BaseModel):
    type: str = "string"
    required: bool = True
    default: Optional[Any] = None
    description: Optional[str] = None

class OutputParamDef(BaseModel):
    type: str = "string"
    description: Optional[str] = None

class TargetSpec(BaseModel):
    surface: str = "browser"
    application: str = "demo-bank"

class Step(BaseModel):
    step_id: str
    action: StepAction
    locator: Optional[LocatorSpec] = None
    url: Optional[str] = None
    value: Optional[str] = None  # Literal value or Jinja/placeholder reference, e.g. "{{member_id}}"
    input_param: Optional[str] = None
    output_param: Optional[str] = None
    expectation: Optional[str] = None
    is_risky: bool = False
    description: Optional[str] = None

class CheckpointType(str, Enum):
    ELEMENT_VISIBLE = "element_visible"
    TEXT_CONTAINS = "text_contains"
    URL_MATCHES = "url_matches"

class Checkpoint(BaseModel):
    type: CheckpointType = CheckpointType.TEXT_CONTAINS
    locator: Optional[LocatorSpec] = None
    expected_value: Optional[str] = None
    description: Optional[str] = None

class CapabilityArtifact(BaseModel):
    schema_version: str = "1.0"
    capability_id: str
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target: TargetSpec = Field(default_factory=TargetSpec)
    inputs: Dict[str, InputParamDef] = Field(default_factory=dict)
    outputs: Dict[str, OutputParamDef] = Field(default_factory=dict)
    steps: List[Step] = Field(default_factory=list)
    checkpoint: Optional[Checkpoint] = None
