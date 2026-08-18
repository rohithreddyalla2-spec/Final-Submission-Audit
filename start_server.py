import sys
import threading
import time
import urllib.request

sys.path.insert(0, '.')
from app.demo_bank.main import app as fastapi_app
from app.demo_bank.models import GLOBAL_FAULT_STATE

# Reset fault states
GLOBAL_FAULT_STATE.session_timeout = False
GLOBAL_FAULT_STATE.unexpected_dialog = False
GLOBAL_FAULT_STATE.application_error = False
GLOBAL_FAULT_STATE.transient_load_failure = False
GLOBAL_FAULT_STATE.validation_error = False

import uvicorn
config = uvicorn.Config(fastapi_app, host='127.0.0.1', port=8000, log_level='error')
server = uvicorn.Server(config)
t = threading.Thread(target=server.run, daemon=False)
t.daemon = False
t.start()

# Wait for server to be ready
for _ in range(20):
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8000/login', timeout=1)
        if r.status in (200, 303, 404, 500):
            break
    except Exception:
        pass
    time.sleep(0.5)

print('Server is running')

# Run verify_e2e.py
import subprocess
result = subprocess.run(
    [sys.executable, 'verify_e2e.py'],
    capture_output=True, text=True, cwd='E:\\Rohit',
    timeout=120
)
print('STDOUT:', result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
print('STDERR:', result.stderr[-3000:] if len(result.stderr) > 3000 else result.stderr)
print('Return code:', result.returncode)