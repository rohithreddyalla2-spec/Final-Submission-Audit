"""Structured logging, telemetry, and evidence export utilities."""
import os
import json
import time
from typing import Optional
from app.safety.policy import SafetyPolicy
from app.replay.result import ReplayResult


class EvidenceExporter:
    """Utility to record structured execution evidence and redact sensitive values."""

    def __init__(self, evidence_dir: str = "evidence"):
        self.evidence_dir = evidence_dir
        os.makedirs(self.evidence_dir, exist_ok=True)
        self.policy = SafetyPolicy()

    def record_replay_result(
        self,
        result: ReplayResult,
        is_error: bool = False,
        surface=None
    ) -> str:
        """Persist a replay result to evidence as a JSON file, optionally with a screenshot."""
        status_val = result.status.value if hasattr(result.status, "value") else str(result.status)
        is_failed = is_error or status_val != "success"
        filename = "replay-error.json" if is_failed else "replay-success.json"
        json_path = os.path.join(self.evidence_dir, filename)

        # Redact any sensitive content in result dictionary
        result_dict = result.model_dump()
        result_dict["timestamp"] = time.time()
        redacted_dict = self.policy.redact_data(result_dict)

        if surface and is_failed:
            png_filename = "replay-error.png"
            png_path = os.path.join(self.evidence_dir, png_filename)
            try:
                surface.screenshot(png_path)
                redacted_dict["evidence_screenshot"] = png_path
            except Exception:
                pass

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(redacted_dict, f, indent=2)

        return json_path
