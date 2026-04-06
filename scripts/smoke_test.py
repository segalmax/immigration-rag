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

    # /ask (needs AWS + indexed chunks)
    r = requests.post(f"{base}/ask", json={"question": "What is USCIS?"}, timeout=120)
    assert r.status_code == 200, f"/ask returned {r.status_code}: {r.text}"
    data = r.json()
    assert "answer" in data and "sources" in data, f"unexpected JSON: {data!r}"
    print("✅ /ask OK")
    print("   answer preview:", (data.get("answer") or "")[:120], "...")

    print("\nSmoke test passed.")

if __name__ == "__main__":
    main()
