"""Robust Locator Strategy and Priority Resolver Model."""
from typing import Optional, Dict
from pydantic import BaseModel, Field

class LocatorSpec(BaseModel):
    """Locator abstraction defining multi-tiered locator strategies for robust replay."""
    role: Optional[str] = Field(None, description="Accessibility ARIA role, e.g. 'button', 'textbox', 'link'")
    name: Optional[str] = Field(None, description="Accessible name or button text")
    label: Optional[str] = Field(None, description="Associated form label text")
    semantic_attr: Optional[Dict[str, str]] = Field(None, description="Semantic HTML attributes like id, name, data-test")
    text: Optional[str] = Field(None, description="Visible inner text")
    css_fallback: Optional[str] = Field(None, description="CSS selector fallback")

    def describe(self) -> str:
        """Human-readable explanation of why this target was chosen."""
        parts = []
        if self.role and self.name:
            parts.append(f"role={self.role}[name='{self.name}']")
        if self.label:
            parts.append(f"label='{self.label}'")
        if self.semantic_attr:
            parts.append(f"attrs={self.semantic_attr}")
        if self.text:
            parts.append(f"text='{self.text}'")
        if self.css_fallback:
            parts.append(f"css='{self.css_fallback}'")
        return " -> ".join(parts) or "empty-locator"
