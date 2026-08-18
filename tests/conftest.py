"""Pytest fixtures for Demo Bank server and Playwright surface test environment."""
import os
import re
import time
import threading
import signal
import subprocess
import pytest
import uvicorn
from playwright.sync_api import sync_playwright
from app.demo_bank.main import app as fastapi_app
from app.demo_bank.models import GLOBAL_FAULT_STATE
from app.surface.playwright_surface import PlaywrightSurface

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
DEMO_BANK_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def _is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use on the given host."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _kill_process_on_port(host: str, port: int) -> None:
    """Kill any process listening on the given port."""
    # Try taskkill on python processes first
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "python.exe"], capture_output=True, text=True, timeout=5
        )
        # If taskkill failed (no matching process), that's fine
    except Exception:
        pass
    # Try to find and kill the specific process on the port using netstat
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )
        # Find the PID listening on our port
        lines = result.stdout.split('\n')
        for line in lines:
            # Format:  TCP    0.0.0.0:8000    0.0.0.0:0      LISTENING       12345
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}"):
                try:
                    pid = int(parts[-1])
                    if pid > 0 and pid != os.getpid():
                        os.kill(pid, signal.SIGKILL)
                except (ValueError, ProcessLookupError, PermissionError):
                    pass
                break
    except Exception:
        pass


class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.server = None
        self.error = None

    def run(self):
        try:
            config = uvicorn.Config(
                fastapi_app, host=SERVER_HOST, port=SERVER_PORT, log_level="error"
            )
            self.server = uvicorn.Server(config)
            self.server.run()
        except Exception as e:
            self.error = e


@pytest.fixture(scope="session", autouse=True)
def start_demo_bank_server():
    """Start FastAPI Demo Bank server in background thread for test session."""
    # Kill any stale process on port 8000 to avoid port conflicts
    if _is_port_in_use(SERVER_HOST, SERVER_PORT):
        _kill_process_on_port(SERVER_HOST, SERVER_PORT)
        time.sleep(0.5)  # Allow port to free

    server_thread = ServerThread()
    server_thread.daemon = True
    server_thread.start()

    # Wait for server to be actually ready, not just spawned
    for _ in range(20):
        if server_thread.error is not None:
            raise RuntimeError(
                f"Demo bank server failed to start: {server_thread.error}"
            )
        import urllib.request
        try:
            r = urllib.request.urlopen(f"{DEMO_BANK_URL}/login", timeout=1)
            if r.status in (200, 303, 404, 500):
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        raise RuntimeError("Demo bank server did not become ready within 10 seconds")

    yield

    # Clean shutdown: signal the server to stop
    if server_thread.server:
        try:
            import httpx
            httpx.get(f"{DEMO_BANK_URL}/logout", timeout=2)
        except Exception:
            pass
    # Reset fault state at end of session
    GLOBAL_FAULT_STATE.session_timeout = False
    GLOBAL_FAULT_STATE.unexpected_dialog = False
    GLOBAL_FAULT_STATE.application_error = False
    GLOBAL_FAULT_STATE.transient_load_failure = False
    GLOBAL_FAULT_STATE.validation_error = False


@pytest.fixture(autouse=True)
def reset_fault_states():
    """Reset fault states before each test."""
    GLOBAL_FAULT_STATE.session_timeout = False
    GLOBAL_FAULT_STATE.unexpected_dialog = False
    GLOBAL_FAULT_STATE.application_error = False
    GLOBAL_FAULT_STATE.transient_load_failure = False
    GLOBAL_FAULT_STATE.validation_error = False
    yield


@pytest.fixture(scope="function")
def surface():
    """Create fresh PlaywrightSurface page per test function."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        surface_obj = PlaywrightSurface(page)
        yield surface_obj
        browser.close()