# Log analysis
## Commands / scripts
 All analysis performed with `log_analysis.py` (repo root). 
 Run via: `python3 log_analysis.py`


## Results
Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
   
Interval covered: 2026-08-20T11:00:00.015Z to 2026-08-20T11:29:57.578Z (~30 minutes).
- access.log: 725 valid lines, 1 malformed (line 311, truncated JSON cut off after
  `"request_id":`), 5 duplicate pairs (10 lines total, 5 distinct extra).
- application.log: 729 valid lines, 1 malformed (line 401, truncated JSON cut off
  after `"event":`).
- error.log: 67 valid entries, 1 excluded (line 68, a `[notice]`-level log
  rotation message, not a request/error event)

2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?

720 distinct request_ids in access.log (725 lines − 5 exact duplicate lines).
Deduplicated by exact line match: the 5 duplicates (lab-000121/241/361/481/601)
are byte-identical repeats of the same GET / request (same timestamp down to the
millisecond), not genuine repeat client requests — likely a periodic check
double-logged. Retries (NGINX trying a second upstream for the same request)
are NOT counted as separate requests: a retried request has one request_id and
one access.log line, with upstream/upstream_status showing comma-separated
values (e.g. "172.23.0.12:8080, 172.23.0.11:8080") for that single line.


3. What are the final client status counts and error rate? State your denominator.

Status counts (access.log, deduplicated): 200: 620, 404: 10, 502: 40, 503: 47,
504: 8.
5xx total: 95. Denominator: 720 distinct requests.
Error rate: 95 / 720 = 13.19%


4. Which paths, time windows and backends account for the failures?

By path (5xx count): /records: 26, /counter: 26, /ready: 23, /health: 10, /: 10.
By backend (from error.log connection failures): 172.23.0.12: 63, 172.23.0.11: 4.
Time windows: concentrated in 11:05–11:10 (59 errors) with a smaller recurrence
at 11:25–11:30 (8 errors) — not spread evenly across the 30-minute log.



5. What are the median and p95 client latencies? State the percentile method and units.

Median (p50): 0.054s. p95: 2.001s. Method: linear interpolation on sorted
request_time values from access.log (n=725, seconds as reported by NGINX)

6. Which requests retried upstream? How many succeeded after retrying?
   19 requests show a comma-separated upstream (retried to a second backend).
All 19 succeeded (final status 200) after retry. This means requests that
retried had a 100% recovery rate — the 95 failures that did NOT retry account
for all observed 5xx responses


7. Build an incident timeline using evidence from access, error AND application logs.

- 11:00:00–11:05:00: Normal operation, all 200s, single upstream per request,
  both backends (.11 and .12) appearing in access.log.
- 11:05:02: First failure (lab-000122, GET /health, 502, upstream 172.23.0.12)
  — first error.log entry also at 11:05:02, "connect() failed (111: Connection
  refused)" to 172.23.0.12:8080.
- 11:05:02–11:10:00: Concentrated failure window, 59 error.log entries, nearly
  all against 172.23.0.12. application.log shows corresponding level=ERROR
  dependency_error / http_request warn entries for the same request_ids on
  instance app matching the failing backend.
- 11:10:00 onward: Failures taper; most requests during this period are either
  200 (served entirely by 172.23.0.11) or 200-after-retry (via the 19 retried
  requests).
- 11:25:00–11:30:00: Smaller recurrence, 8 further error.log entries against
  172.23.0.12, then the log ends at 11:29:57


8. Show one correlated failed request and one successful request. Include IDs and timestamps.

Failed (no retry): request_id lab-000122, timestamp 11:05:02.503Z, GET /health,
access.log status 502, upstream 172.23.0.12:8080 only; error.log at the same
timestamp shows "connect() failed (111: Connection refused)... upstream:
http://172.23.0.12:8080/health".
Succeeded (after retry): request_id lab-000124, timestamp 11:05:07.620Z, GET
/ready, access.log status 200, upstream "172.23.0.12:8080, 172.23.0.11:8080",
upstream_status "502, 200" — first attempt failed, NGINX retried the second
backend and succeeded

9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?

67 error.log entries are all NGINX-level proxy/connectivity errors ("connect()
failed... Connection refused" reaching an upstream) — these represent a backend being entirely unreachable, not a request that reached the app and failed internally. Separately, application.log contains 47 level=ERROR entries — these represent the app process itself reporting a dependency failure (e.g. postgres/redis unavailable) while still successfully receiving the request. The two are distinguishable by which log records them: error.log entries never reach the
Flask app at all (NGINX can't connect to it); application.log ERROR entries are logged BY the app, meaning the app was reachable but something it depends on wasn't



10. What do the logs not prove? What would you check next in a running environment?
These logs don't prove *why* 172.23.0.12 stopped accepting connections (crash?
OOM? manual stop? healthcheck-triggered restart loop?) — only that connections
were refused. They also don't include container-level events (docker events,
restart counts, resource usage) that would confirm the actual cause. In a
running environment, we would check: `docker compose ps`/`docker inspect` for
restart counts and OOM kill status around 11:05 and 11:25, `docker stats` for
memory/CPU pressure, and container-level logs for app-01/app-02 (not just
NGINX/app aggregate logs) to see if the affected instance logged a crash or
shutdown reason



## Timeline and correlated examples
i clarified it in question 7, 8
## Conclusions and limits
The incident was caused by backend 172.23.0.12 becoming unreachable at the NGINX level (connection refused) for two windows (11:05–11:10, 11:25–11:30), while 172.23.0.11 remained healthy throughout. NGINX's retry behavior during this incident was inconsistent by endpoint: /ready and /instance requests that hit the failing backend were retried against the healthy one and always succeeded (19/19), while /health, /records, /counter and / requests that hit the failing backend received a 502 with no retry attempt recorded.
 We don't have the historical nginx.conf used during this incident (a separate training scenario per logs/README.md), so we can't confirm the exact `proxy_next_upstream`
configuration that produced this split — this is our best-supported hypothesis from the evidence, not a fully proven root cause. Limits: 2 lines were excluded as malformed/truncated and cannot contribute evidence; the true cause of 172.23.0.12's unavailability is not determinable from these three logs alone
