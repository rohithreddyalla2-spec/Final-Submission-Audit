"""Pytest fixtures for Demo Bank server and Playwright surface test environment."""
import os
import time
import socket
import threading
import subprocess
import pytest
import uvicorn
from playwright.sync_api import sync_playwright
from app.demo_bank.main import app as fastapi_app
from app.demo_bank.models import GLOBAL_FAULT_STATE
from app.surface.playwright_surface import PlaywrightSurface

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

def kill_process_on_port(port: int = SERVER_PORT):
    """Ensure port is free by terminating any stale process listening on it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        res = s.connect_ex((SERVER_HOST, port))
        if res != 0:
            return  # Port is free

    try:
        if os.name == "nt":
            netstat_cmd = r"C:\Windows\System32\netstat.exe -ano"
            out = subprocess.check_output(netstat_cmd, shell=True).decode()
            lines = out.strip().splitlines()
            pids = set()
            for line in lines:
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in parts and f":{port}" in parts[1]:
                    pids.add(parts[-1])
            for pid in pids:
                if pid != "0" and pid != str(os.getpid()):
                    taskkill_cmd = f"C:\\Windows\\System32\\taskkill.exe /F /PID {pid}"
                    subprocess.run(taskkill_cmd, shell=True, capture_output=True)
        else:
            subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
        time.sleep(0.5)
    except Exception:
        pass


class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.server = None
        self.exception = None

    def run(self):
        try:
            config = uvicorn.Config(fastapi_app, host=SERVER_HOST, port=SERVER_PORT, log_level="error")
            self.server = uvicorn.Server(config)
            self.server.run()
        except Exception as e:
            self.exception = e

    def stop(self):
        if self.server:
            self.server.should_exit = True

def reset_global_fault_states():
    """Reset fault states both in Python memory and via HTTP endpoint."""
    GLOBAL_FAULT_STATE.session_timeout = False
    GLOBAL_FAULT_STATE.unexpected_dialog = False
    GLOBAL_FAULT_STATE.application_error = False
    GLOBAL_FAULT_STATE.transient_load_failure = False
    GLOBAL_FAULT_STATE.validation_error = False
    try:
        import requests
        requests.post(f"http://{SERVER_HOST}:{SERVER_PORT}/admin/inject-state", json=GLOBAL_FAULT_STATE.model_dump(), timeout=1)
    except Exception:
        pass

@pytest.fixture(scope="session", autouse=True)
def start_demo_bank_server():
    """Start FastAPI Demo Bank server in background thread for test session."""
    kill_process_on_port(SERVER_PORT)

    server_thread = ServerThread()
    server_thread.daemon = True
    server_thread.start()

    # Wait for server to be responsive
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < 5.0:
        if server_thread.exception:
            raise RuntimeError(f"Server thread failed with exception: {server_thread.exception}")
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://{SERVER_HOST}:{SERVER_PORT}/members", timeout=1) as resp:
                if resp.status == 200:
                    server_ready = True
                    break
        except Exception:
            time.sleep(0.1)

    if not server_ready:
        raise RuntimeError(f"Demo Bank server failed to respond on http://{SERVER_HOST}:{SERVER_PORT} within 5s")

    yield

    # Clean teardown
    reset_global_fault_states()
    server_thread.stop()
    server_thread.join(timeout=3.0)

@pytest.fixture(autouse=True)
def reset_fault_states():
    """Reset fault states before and after each test."""
    reset_global_fault_states()
    yield
    reset_global_fault_states()

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

