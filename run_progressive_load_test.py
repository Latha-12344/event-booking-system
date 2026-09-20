"""
Progressive load test runner using Locust.
Evaluates progressive concurrency tiers: [10, 25, 50, 100, 200, 300, 500]
Measures RPS, p50, p95, p99, error rate, and identifies the breaking point.
"""
import csv
import json
import os
import subprocess
import sys
import time

HOST = os.environ.get("LOAD_TEST_HOST", "http://127.0.0.1:8000")
RESET_CAPACITY = os.environ.get("LOAD_TEST_TICKET_CAPACITY", "1000")
TIERS = [
    (10, 2, "15s"),
    (25, 5, "15s"),
    (50, 10, "15s"),
    (100, 20, "15s"),
]


def metric_value(value: str | None) -> float:
    return 0.0 if value in (None, "", "N/A") else float(value)

def run_tier(users, spawn_rate, duration, prefix="baseline"):
    csv_prefix = os.path.join("locust", "results", f"{prefix}_users_{users}")
    cmd = [
        sys.executable, "-m", "locust",
        "-f", "locust/locustfile.py",
        f"--host={HOST}",
        "--users", str(users),
        "--spawn-rate", str(spawn_rate),
        "--run-time", duration,
        "--headless",
        f"--csv={csv_prefix}",
    ]
    print(f"\n--- Running Tier: {users} users (spawn rate: {spawn_rate}/s, duration: {duration}) ---")
    start_t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_t
    print(f"Tier completed in {elapsed:.1f}s")

    stats_file = f"{csv_prefix}_stats.csv"
    failures_file = f"{csv_prefix}_failures.csv"

    stats = {
        "users": users,
        "spawn_rate": spawn_rate,
        "total_requests": 0,
        "failed_requests": 0,
        "error_rate": 0.0,
        "rps": 0.0,
        "p50": 0.0,
        "p95": 0.0,
        "p99": 0.0,
        "booking_p99": 0.0,
        "booking_rps": 0.0,
        "booking_requests": 0,
        "successful_bookings": 0,
        "http_409_errors": 0,
        "http_500_errors": 0,
        "timeouts": 0,
        "genuine_failures": 0,
        "genuine_error_rate": 0.0,
        "failures": [],
    }

    if os.path.exists(stats_file):
        with open(stats_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "")
                if name == "Aggregated":
                    total = int(row.get("Request Count", 0))
                    fails = int(row.get("Failure Count", 0))
                    stats["total_requests"] = total
                    stats["failed_requests"] = fails
                    stats["error_rate"] = (fails / total * 100) if total > 0 else 0.0
                    stats["rps"] = metric_value(row.get("Requests/s"))
                    stats["p50"] = metric_value(row.get("50%"))
                    stats["p95"] = metric_value(row.get("95%"))
                    stats["p99"] = metric_value(row.get("99%"))
                elif "/api/v1/bookings/" in name:
                    stats["booking_requests"] = int(row.get("Request Count", 0))
                    stats["booking_p99"] = metric_value(row.get("99%"))
                    stats["booking_p50"] = metric_value(row.get("50%"))
                    stats["booking_p95"] = metric_value(row.get("95%"))
                    stats["booking_rps"] = metric_value(row.get("Requests/s"))

    if os.path.exists(failures_file):
        with open(failures_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                occurrences = int(row.get("Occurrences", 1))
                stats["failures"].append(dict(row))
                error = row.get("Error", "")
                stats["http_409_errors"] += occurrences if "HTTP 409" in error else 0
                stats["http_500_errors"] += occurrences if "HTTP 500" in error else 0
                stats["timeouts"] += occurrences if "timeout" in error.lower() else 0

    stats["successful_bookings"] = max(
        0, stats["booking_requests"] - stats["http_409_errors"] - stats["http_500_errors"] - stats["timeouts"]
    )
    stats["genuine_failures"] = max(
        0, stats["failed_requests"] - stats["http_409_errors"]
    )
    stats["genuine_error_rate"] = (
        stats["genuine_failures"] / stats["total_requests"] * 100
        if stats["total_requests"] else 0.0
    )

    return stats


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    print(f"==================================================")
    print(f"STARTING PROGRESSIVE LOAD TEST: {prefix.upper()}")
    print(f"==================================================")

    results = []
    breaking_point = None

    for users, spawn, duration in TIERS:
        setup_env = os.environ.copy()
        setup_env["LOAD_TEST_TICKET_CAPACITY"] = RESET_CAPACITY
        subprocess.run(
            [sys.executable, "locust/setup_test_data.py"],
            check=True,
            env=setup_env,
            capture_output=True,
            text=True,
        )
        stats = run_tier(users, spawn, duration, prefix=prefix)
        results.append(stats)
        print(f"Results for {users} users:")
        print(f"  Total Requests : {stats['total_requests']}")
        print(f"  Failed Requests: {stats['failed_requests']} ({stats['error_rate']:.2f}%)")
        print(f"  Total RPS      : {stats['rps']:.1f}")
        print(f"  Booking        : {stats['booking_requests']} total / {stats['successful_bookings']} success / {stats['http_409_errors']} HTTP 409")
        print(f"  Genuine errors : {stats['genuine_failures']} (500={stats['http_500_errors']}, timeouts={stats['timeouts']})")
        print(f"  Booking p50/p95: {stats.get('booking_p50', 0):.1f} / {stats.get('booking_p95', 0):.1f} ms")
        print(f"  Booking p99    : {stats['booking_p99']:.1f} ms")
        print(f"  Overall p99    : {stats['p99']:.1f} ms")

        # Expected 409 capacity conflicts are not application degradation.
        # Mark the first tier with genuine failures or booking p99 above 500 ms.
        if breaking_point is None:
            if stats["genuine_error_rate"] > 5.0:
                breaking_point = f"{users} users (genuine error rate = {stats['genuine_error_rate']:.2f}% > 5%)"
            elif stats["booking_p99"] > 500.0:
                breaking_point = f"{users} users (booking p99 = {stats['booking_p99']:.1f}ms > 500ms)"

        # Cool down between tiers
        time.sleep(3)

    summary_file = os.path.join("locust", "results", f"{prefix}_summary.json")
    with open(summary_file, "w") as f:
        json.dump({"results": results, "breaking_point": breaking_point}, f, indent=2)

    print("\n==================================================")
    print(f"LOAD TEST COMPLETED: {prefix.upper()}")
    print(f"Breaking Point Identified: {breaking_point or 'Not reached in tested tiers'}")
    print("==================================================")
    print(f"{'Users':<8}{'Total Req':<12}{'RPS':<10}{'p50 (ms)':<12}{'p95 (ms)':<12}{'p99 (ms)':<12}{'Error %':<10}")
    for r in results:
        print(f"{r['users']:<8}{r['total_requests']:<12}{r['rps']:<10.1f}{r['p50']:<12.1f}{r['p95']:<12.1f}{r['p99']:<12.1f}{r['error_rate']:<10.2f}%")


if __name__ == "__main__":
    main()
