"""Unit tests for Safety Guardrails policy enforcement and PII redaction."""
import pytest
from app.safety.policy import SafetyPolicy, SafetyPolicyConfig
from app.surface.locator import LocatorSpec
from app.artifacts.schema import StepAction

def test_safety_allowed_action_and_domain():
    policy = SafetyPolicy()
    dec = policy.evaluate_action(
        action=StepAction.NAVIGATE,
        url="http://127.0.0.1:8000/members"
    )
    assert dec.allowed is True
    assert dec.is_risky is False

def test_safety_blocked_external_domain():
    policy = SafetyPolicy()
    dec = policy.evaluate_action(
        action=StepAction.NAVIGATE,
        url="https://malicious-external-bank.com/steal"
    )
    assert dec.allowed is False
    assert "Blocked domain" in dec.reason

def test_safety_risky_action_detection():
    policy = SafetyPolicy()
    loc = LocatorSpec(role="button", name="Submit & Create Sub-Account")
    dec = policy.evaluate_action(
        action=StepAction.CLICK,
        locator=loc,
        description="Submit open sub-account form"
    )
    assert dec.allowed is True
    assert dec.is_risky is True
    assert "Risky action" in dec.reason

def test_safety_blocked_keyword():
    policy = SafetyPolicy()
    dec = policy.evaluate_action(
        action=StepAction.FILL,
        value="export_secret_token",
        description="Extract raw credential dump"
    )
    assert dec.allowed is False
    assert "blocked keyword" in dec.reason

def test_pii_redaction():
    policy = SafetyPolicy()
    raw_log = {
        "user": "operator",
        "password": "super_secret_password_123",
        "ssn_number": "000-12-3456",
        "details": {
            "token": "bearer_abc_xyz"
        }
    }
    redacted = policy.redact_data(raw_log)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["ssn_number"] == "[REDACTED]"
    assert redacted["details"]["token"] == "[REDACTED]"
    assert redacted["user"] == "operator"
