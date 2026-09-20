"""
Performance benchmark runner using Locust headless mode.
Runs a local baseline load test and prints summary statistics.
"""
import subprocess
import sys
import time
import requests

def wait_for_server(url="http://localhost:8000/health", timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("Checking if API server is responsive on http://localhost:8000 ...")
    if not wait_for_server():
        print("Server not running. Please start: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    print("Server ready! Running headless Locust benchmark (10 users, 2/s spawn rate, 30s duration)...")
    cmd = [
        sys.executable, "-m", "locust",
        "-f", "locust/locustfile.py",
        "--host=http://localhost:8000",
        "--users", "10",
        "--spawn-rate", "2",
        "--run-time", "30s",
        "--headless",
        "--csv=locust/benchmark_results",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Benchmark complete!")
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)

if __name__ == "__main__":
    main()
