"""CLI entrypoint for running the Demo Bank FastAPI server."""
import os
import uvicorn

def main():
    host = os.getenv("DEMO_BANK_HOST", "127.0.0.1")
    port = int(os.getenv("DEMO_BANK_PORT", "8000"))
    print(f"Starting Demo Bank Back-Office UI on http://{host}:{port}")
    uvicorn.run("app.demo_bank.main:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
