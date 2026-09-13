#!/usr/bin/env python3
#"""Candidate deliverable: implement environment validation; this is not a solution."""
#import sys
#print("NOT IMPLEMENTED: write bounded checks with PASS/FAIL and non-zero failure exits.")
#sys.exit(2)


"""Validate the running BARQ assessment environment."""
import json
import socket
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
TIMEOUT = 3
RETRIES = 5
RETRY_DELAY = 2

results = []  # (name, passed: bool, detail: str)


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))


def get_json(path, expect_status=None):
    """GET a path, return (status_code, json_body_or_None). Body is None if not valid JSON."""
    url = BASE_URL + path
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, None
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return e.code, None
    except Exception as e:
        return None, str(e)

def post_json(path, payload):
    url = BASE_URL + path
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return None, str(e)


def wait_for_ready(max_wait=20):
    """Bounded wait: poll /ready until it passes or times out."""
    start = time.time()
    body = None
    while time.time() - start < max_wait:
        status, body = get_json("/ready")
        if status == 200:
            return True, body
        time.sleep(1)
    return False, body


def port_reachable(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def main():
    # 1) Bounded wait for readiness before testing anything else
    ready, body = wait_for_ready(max_wait=20)
    record("readiness (postgres+redis via /ready)", ready, json.dumps(body) if ready else "timed out waiting for /ready")

    # 2) Public access
    status, body = get_json("/")
    record("GET / returns 200", status == 200, f"status={status}")

    # 3) /health
    status, body = get_json("/health")
    record("GET /health returns 200", status == 200, f"status={status}")

    # 4) /instance :check both backends respond via NGINX load balancing
    seen_instances = set()
    for _ in range(40):
        status, body = get_json("/instance")
        if status == 200 and isinstance(body, dict):
            seen_instances.add(body.get("instance_id"))
    record("both backends visible via /instance (load balancing)",
           len(seen_instances) >= 2, f"saw instance_ids={seen_instances}")
    # 5) /records  :POST then GET
    status, body = post_json("/records", {"title": "validate.py test record"})
    record("POST /records returns 201", status == 201, f"status={status}")

    status, body = get_json("/records")
    has_records = status == 200 and isinstance(body, dict) and "records" in body
    record("GET /records returns list", has_records, f"status={status}")

    # 6) /counter
    status, body = get_json("/counter")
    record("GET /counter returns 200", status == 200, f"status={status}")

    # 7) Network isolation :prohibited host ports must NOT be reachable
    record("PostgreSQL port 15432 NOT reachable from host",
           not port_reachable("127.0.0.1", 15432), "expected closed")
    record("Redis port 16379 NOT reachable from host",
           not port_reachable("127.0.0.1", 16379), "expected closed")

    # 8) NGINX itself must be reachable
    record("NGINX port 8080 reachable from host",
           port_reachable("127.0.0.1", 8080), "expected open")



    print("\n--- SUMMARY ---")
    failed = [r for r in results if not r[1]]
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")

    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
