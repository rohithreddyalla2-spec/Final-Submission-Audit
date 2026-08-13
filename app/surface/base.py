"""Abstract Surface Interface Protocol for UI Automation."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.surface.locator import LocatorSpec

class Surface(ABC):
    """Abstract interface for interacting with UI surfaces (Browser, Desktop, Accessibility API)."""

    @abstractmethod
    def observe(self) -> Dict[str, Any]:
        """Observe current surface state (URL, title, accessibility tree, interactive elements)."""
        pass

    @abstractmethod
    def click(self, locator: LocatorSpec) -> None:
        """Click an interactive element resolved by the locator strategy."""
        pass

    @abstractmethod
    def fill(self, locator: LocatorSpec, value: str) -> None:
        """Fill text into an input field resolved by the locator strategy."""
        pass

    @abstractmethod
    def navigate(self, url: str) -> None:
        """Navigate to a target URL."""
        pass

    @abstractmethod
    def read(self, locator: LocatorSpec) -> str:
        """Read visible text or value from an element resolved by the locator strategy."""
        pass

    @abstractmethod
    def wait(self, timeout_ms: int = 2000, locator: Optional[LocatorSpec] = None) -> None:
        """Wait for duration or until locator becomes visible."""
        pass

    @abstractmethod
    def screenshot(self, path: str) -> str:
        """Capture screenshot of the current surface and return output path."""
        pass
