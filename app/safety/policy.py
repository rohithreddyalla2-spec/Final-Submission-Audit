"""Safety Policy Layer for enforcing domain allowlists, action policies, and PII redaction."""
from urllib.parse import urlparse
from typing import Any, Optional, Set, Union
from pydantic import BaseModel, Field
from app.artifacts.schema import StepAction
from app.surface.locator import LocatorSpec

class SafetyPolicyConfig(BaseModel):
    allowed_hosts: Set[str] = Field(default_factory=lambda: {"localhost", "127.0.0.1", "0.0.0.0"})
    allowed_actions: Set[str] = Field(default_factory=lambda: {"navigate", "click", "fill", "read", "wait"})
    risky_keywords: Set[str] = Field(default_factory=lambda: {
        "submit & create", "create", "delete", "transfer", "open sub-account", "confirm", "pay", "withdraw"
    })
    blocked_keywords: Set[str] = Field(default_factory=lambda: {
        "download", "exec", "eval", "cookie_dump", "export_secret", "credential"
    })
    sensitive_keys: Set[str] = Field(default_factory=lambda: {
        "password", "passwd", "secret", "token", "ssn", "social_security", "credit_card", "api_key"
    })

class PolicyDecision(BaseModel):
    allowed: bool
    is_risky: bool = False
    reason: str

class SafetyPolicy:
    """Configurable safety policy engine to validate actions before execution."""

    def __init__(self, config: Optional[SafetyPolicyConfig] = None):
        self.config = config or SafetyPolicyConfig()

    def evaluate_navigation(self, url: str) -> PolicyDecision:
        """Verify URL is within allowed host domain boundaries."""
        if not url:
            return PolicyDecision(allowed=True, reason="Empty URL")

        parsed = urlparse(url)
        # Check scheme (allow http, https, or relative)
        if parsed.scheme and parsed.scheme not in ["http", "https"]:
            return PolicyDecision(allowed=False, reason=f"Blocked scheme '{parsed.scheme}'")

        hostname = parsed.hostname
        if hostname and hostname not in self.config.allowed_hosts:
            return PolicyDecision(
                allowed=False,
                reason=f"Blocked domain '{hostname}'. Allowed domains: {self.config.allowed_hosts}"
            )

        return PolicyDecision(allowed=True, reason="Domain allowed")

    def evaluate_action(
        self,
        action: Union[str, StepAction],
        url: Optional[str] = None,
        locator: Optional[LocatorSpec] = None,
        value: Optional[str] = None,
        description: Optional[str] = None
    ) -> PolicyDecision:
        """Evaluate action, target, and payload against security policy."""
        action_str = action.value if isinstance(action, StepAction) else str(action).lower()

        # 1. Action type check
        if action_str not in self.config.allowed_actions:
            return PolicyDecision(allowed=False, reason=f"Action '{action_str}' is not in allowed actions list.")

        # 2. Domain check for navigation
        if action_str == "navigate" and url:
            nav_dec = self.evaluate_navigation(url)
            if not nav_dec.allowed:
                return nav_dec

        # 3. Check blocked keywords in locator or values
        comb_text = f"{description or ''} {value or ''}"
        if locator:
            comb_text += f" {locator.name or ''} {locator.label or ''} {locator.text or ''} {locator.css_fallback or ''}"
        
        comb_text_lower = comb_text.lower()
        for b_word in self.config.blocked_keywords:
            if b_word in comb_text_lower:
                return PolicyDecision(allowed=False, reason=f"Action contains blocked keyword '{b_word}'")

        # 4. Check risky action keywords (triggers human approval / handoff)
        matched_risky_keyword: Optional[str] = None
        for r_word in self.config.risky_keywords:
            if r_word in comb_text_lower:
                matched_risky_keyword = r_word
                break

        if matched_risky_keyword is not None:
            return PolicyDecision(
                allowed=True,
                is_risky=True,
                reason=f"Risky action detected ('{matched_risky_keyword}'). Requires human approval."
            )

        return PolicyDecision(allowed=True, is_risky=False, reason="Action approved by policy.")

    def redact_data(self, data: Any) -> Any:
        """Recursively redact sensitive key-values or tokens in structures/logs."""
        if isinstance(data, dict):
            redacted = {}
            for k, v in data.items():
                if any(s_key in k.lower() for s_key in self.config.sensitive_keys):
                    redacted[k] = "[REDACTED]"
                else:
                    redacted[k] = self.redact_data(v)
            return redacted
        elif isinstance(data, list):
            return [self.redact_data(item) for item in data]
        elif isinstance(data, str):
            # Redact password patterns or tokens in strings
            if any(s_key in data.lower() for s_key in ["password=", "secret=", "bearer "]):
                return "[REDACTED_SENSITIVE_STRING]"
            return data
        return data
