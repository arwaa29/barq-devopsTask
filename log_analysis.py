#!/usr/bin/env python3
"""Analyze the three historical logs: access, error, application."""
import json
import re
from collections import defaultdict, Counter
from datetime import datetime

def parse_access(path):
    records, malformed = [], 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1
    return records, malformed

def parse_application(path):
    records, malformed = [], 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1
    return records, malformed

ERROR_RE = re.compile(
    r"(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[error\].*?"
    r"request_id=(?P<request_id>\S+?),.*?"
    r'request: "(?P<method>\w+) (?P<path>\S+) HTTP.*?"'
    r'.*?upstream: "(?P<upstream>[^"]+)"'
)

def parse_error(path):
    records, unmatched = [], 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = ERROR_RE.search(line)
            if m:
                records.append(m.groupdict())
            else:
                unmatched += 1
    return records, unmatched

def main():
    access, access_bad = parse_access("logs/access.log")
    app, app_bad = parse_application("logs/application.log")
    error, error_bad = parse_error("logs/error.log")

    print(f"=== Parse summary ===")
    print(f"access.log: {len(access)} parsed, {access_bad} malformed")
    print(f"application.log: {len(app)} parsed, {app_bad} malformed")
    print(f"error.log: {len(error)} parsed, {error_bad} unmatched")

    
    access_ids = Counter(r["request_id"] for r in access)
    dupes = {k: v for k, v in access_ids.items() if v > 1}
    print(f"\n=== Duplicate request_ids in access.log ===")
    print(f"{len(dupes)} request_ids appear more than once")
    if dupes:
        print("Sample:", list(dupes.items())[:5])

    # Status code breakdown
    status_counts = Counter(r["status"] for r in access)
    print(f"\n=== access.log status code counts ===")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    upstream_errors = Counter()
    for e in error:
        m = re.search(r"//([\d.]+):\d+", e["upstream"])
        if m:
            upstream_errors[m.group(1)] += 1
    print(f"\n=== error.log failures by upstream IP ===")
    for ip, count in upstream_errors.most_common():
        print(f"  {ip}: {count}")

    print(f"\n=== error.log timeline (5-min buckets) ===")
    buckets = Counter()
    for e in error:
        dt = datetime.strptime(e["ts"], "%Y/%m/%d %H:%M:%S")
        bucket = dt.replace(minute=(dt.minute // 5) * 5, second=0)
        buckets[bucket] += 1
    for bucket, count in sorted(buckets.items()):
        print(f"  {bucket}: {count} errors")

    # Correlation: for request_ids in error.log, what does access.log say?
    error_ids = {e["request_id"] for e in error}
    access_by_id = {r["request_id"]: r for r in access}
    correlated = sum(1 for rid in error_ids if rid in access_by_id)
    print(f"\n=== Correlation ===")
    print(f"{len(error_ids)} error.log entries; {correlated} have a matching access.log entry")

    # 5xx in access.log matching error.log entries
    access_5xx = [r for r in access if r["status"] >= 500]
    print(f"\n5xx responses in access.log: {len(access_5xx)}")


        # Latency percentiles (client-facing, from access.log request_time)
    import statistics
    times = sorted(r["request_time"] for r in access)
    def percentile(data, pct):
        k = (len(data) - 1) * (pct / 100)
        f, c = int(k), min(int(k) + 1, len(data) - 1)
        return data[f] + (data[c] - data[f]) * (k - f)
    median = percentile(times, 50)
    p95 = percentile(times, 95)
    print(f"\n=== Latency (seconds) ===")
    print(f"median: {median:.3f}s, p95: {p95:.3f}s (n={len(times)})")

    # Distinct client requests (dedup by exact line / request_id)
    distinct_ids = len(set(r["request_id"] for r in access))
    print(f"\n=== Distinct requests ===")
    print(f"Total lines: {len(access)}, distinct request_ids: {distinct_ids}")

    # Retries: upstream field contains a comma = retried
    retried = [r for r in access if "," in r["upstream"]]
    retried_success = [r for r in retried if r["status"] == 200]
    print(f"\n=== Retries ===")
    print(f"Requests that retried upstream: {len(retried)}")
    print(f"Of those, succeeded (200): {len(retried_success)}")

    # Error rate
    error_rate = len(access_5xx) / distinct_ids * 100
    print(f"\n=== Error rate ===")
    print(f"5xx count: {len(access_5xx)}, denominator: {distinct_ids} distinct requests, rate: {error_rate:.2f}%")

    # UTC interval covered
    all_ts = [r["timestamp"] for r in access]
    print(f"\n=== Time interval ===")
    print(f"First: {min(all_ts)}, Last: {max(all_ts)}")

    # Failures by path
    print(f"\n=== Failures (5xx) by path ===")
    path_failures = Counter(r["path"] for r in access if r["status"] >= 500)
    for path, count in path_failures.most_common():
        print(f"  {path}: {count}")

    # Proxy/connectivity vs dependency/application errors
    # error.log = NGINX-level (proxy/connectivity: connection refused to upstream)
    # application.log level=ERROR = app-level dependency errors
    app_errors = [r for r in app if r.get("level") == "ERROR"]
    print(f"\n=== Error classification ===")
    print(f"Proxy/connectivity errors (error.log, connection refused): {len(error)}")
    print(f"Application/dependency errors (application.log, level=ERROR): {len(app_errors)}")

if __name__ == "__main__":
    main()