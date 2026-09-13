#!/usr/bin/env python3
# """Candidate deliverable: stop one backend, measure traffic, restore it and verify."""
# import sys
# print("NOT IMPLEMENTED: write the scoped failure/recovery test, including cleanup.")
# sys.exit(2)


#!/usr/bin/env python3
"""Stop one backend, measure traffic during failure, restore it, verify recovery."""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
PROJECT = "barq-assessment"
TARGET_BACKEND = "app-01"
TIMEOUT = 3

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))


def get_status(path):
    """Return HTTP status code, or None if the request failed entirely."""
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def run_docker(*args):
    cmd = ["docker", "compose", "-p", PROJECT] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def hammer_requests(path, count, delay=0.3):
    """Send repeated requests, return (success_count, error_count)."""
    success, error = 0, 0
    for _ in range(count):
        status = get_status(path)
        if status == 200:
            success += 1
        else:
            error += 1
        time.sleep(delay)
    return success, error


def wait_for_ready(max_wait=20):
    start = time.time()
    while time.time() - start < max_wait:
        if get_status("/ready") == 200:
            return True
        time.sleep(1)
    return False


def main():
    #  Confirm healthy baseline before we touch anything
    baseline_ready = wait_for_ready(max_wait=15)
    record("baseline: environment ready before test", baseline_ready)
    if not baseline_ready:
        print("Environment not ready; aborting failure test.")
        sys.exit(1)

    # 1) Stop backend
    rc, out, err = run_docker("stop", TARGET_BACKEND)
    record(f"stopped {TARGET_BACKEND}", rc == 0, err.strip() if rc != 0 else "")

    # 2) Measure traffic while one backend is down
    success, error = hammer_requests("/instance", count=15, delay=0.3)
    record("traffic continues during failure (some 200s observed)", success > 0,
           f"success={success}, error={error} out of 15 requests")

    # 3) Restore the backend
    rc, out, err = run_docker("start", TARGET_BACKEND)
    record(f"restarted {TARGET_BACKEND}", rc == 0, err.strip() if rc != 0 else "")

    # 4) Wait for it to become healthy again (bounded wait)
    recovered = False
    start = time.time()
    while time.time() - start < 30:
        rc, out, err = run_docker("ps", TARGET_BACKEND)
        if "healthy" in out:
            recovered = True
            break
        time.sleep(2)
    record(f"{TARGET_BACKEND} reports healthy after restart", recovered)

    # 5) Prove the recovered backend actually serves requests again
    seen_instances = set()
    for _ in range(50):
        try:
            with urllib.request.urlopen(BASE_URL + "/instance", timeout=TIMEOUT) as resp:
                body = json.loads(resp.read().decode())
                seen_instances.add(body.get("instance_id"))
        except Exception:
            pass
        time.sleep(0.1)
    record(f"{TARGET_BACKEND} serves requests again post-recovery",
           TARGET_BACKEND in seen_instances, f"saw instance_ids={seen_instances}")

    print("\n--- SUMMARY ---")
    failed = [r for r in results if not r[1]]
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()