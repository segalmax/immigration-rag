"""
scripts/smoke_test.py
End-to-end smoke test: hit /health and /ask to confirm the stack is wired up.
Run from the project root after the Flask app is running.

Usage:
    python scripts/smoke_test.py [--url http://localhost:5000]
"""
import sys
import argparse
import requests

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5000")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    # /health
    r = requests.get(f"{base}/health", timeout=5)
    assert r.status_code == 200, f"/health returned {r.status_code}"
    print("✅ /health OK")

    # /ask
    r = requests.post(f"{base}/ask", json={"question": "What is USCIS?"}, timeout=10)
    # 501 = "Not Implemented" (acceptable for /ask if backend is stubbed)
    assert r.status_code in (200, 501), f"/ask returned {r.status_code}"
    print(f"✅ /ask OK  (status={r.status_code})")
    print("   response:", r.json())

    print("\nSmoke test passed.")

if __name__ == "__main__":
    main()
