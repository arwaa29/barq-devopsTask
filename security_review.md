# Security and production-readiness review

Record at least 8 concrete risks or improvements relevant to your final solution.
This is a review requirement, not the number of hidden faults.

For each finding:
- Risk and evidence:
- Impact:
- Implemented fix / commit:
- Production follow-up:
- How to verify:

Cover secrets, ports, container user, image selection, networks, persistence/backup,
logging/monitoring and availability. Separate completed work from planned improvements.



## Finding 1 — All containers run as root
- Risk and evidence: `docker compose exec <service> whoami` returns `root`
  for app-01, app-02, postgres, redis, and nginx.
- Impact: If any process inside a container is compromised (e.g. via a
  dependency vulnerability), the attacker has root inside that container,
  increasing the blast radius of a potential container breakout.
- Implemented fix / commit: None — identified but not implemented due to
  time constraints; this is a planned production improvement, not a
  completed fix.
- Production follow-up: Add a non-root `USER` directive to the app
  Dockerfile; use official images' built-in non-root user options where
  available (e.g. postgres/redis alpine images support running as a
  non-root UID via configuration); test thoroughly since file permission
  issues on mounted volumes are a common side effect of this change.
- How to verify: `docker compose exec <service> whoami` should return a
  non-root username after the fix.

## Finding 2 — Real secret was committed to git history
- Risk and evidence: config/app.env (containing a real lab PostgreSQL
  password) was tracked and pushed to a public GitHub repo before being
  caught and removed from tracking (troubleshooting.md Entry 5).
- Impact: The password remains visible in earlier commit history even
  after untracking the file going forward; anyone who clones the repo's
  full history can still find it.
- Implemented fix / commit: Stopped tracking config/app.env, added it to
  .gitignore, created config/app.env.example with placeholder values
  (commit: see troubleshooting.md Entry 5 for hash).
- Production follow-up: For a real production incident, rotate the
  exposed credential immediately, and consider rewriting git history
  (e.g. git filter-repo) if the repo must remain public. Since this is
  synthetic lab data, rotation/history-rewrite was not performed here.
- How to verify: `git log --all --full-history -- config/app.env` shows
  the file's commit history including the exposed value in early commits.

## Finding 3 — PostgreSQL and Redis ports were originally published to host
- Risk and evidence: docker-compose.yml originally published Postgres on
  127.0.0.1:15432 and Redis on 127.0.0.1:16379, directly reachable from
  the host machine, bypassing the app layer entirely.
- Impact: Any process on the host (or anything that could reach the host
  network) could connect directly to the databases, bypassing application-
  level access controls entirely.
- Implemented fix / commit: Removed both `ports:` mappings; verified via
  validate.py that both ports are now unreachable from the host
  (`port_reachable` checks return closed).
- Production follow-up: In production, additionally restrict database
  access at the network/firewall level (security groups, VPC rules) as
  defense in depth beyond just not publishing the port.
- How to verify: `curl http://127.0.0.1:15432` and `:16379` both fail to
  connect; validate.py's network isolation checks pass.

## Finding 4 — No resource limits configured
- Risk and evidence: docker-compose.yml does not set `deploy.resources`
  (CPU/memory limits) for any service.
- Impact: A single misbehaving container (e.g. a memory leak in the Flask
  app) could consume all host resources, starving other containers and
  potentially crashing the whole environment (noisy neighbor problem).
- Implemented fix / commit: None — identified but not implemented due to
  time constraints.
- Production follow-up: Add memory/CPU limits per service (e.g.
  `mem_limit`, `cpus` in Compose, or `deploy.resources.limits` for Swarm/
  Kubernetes), sized based on observed real usage under load testing.
- How to verify: `docker stats` should show enforced limits; attempting to
  exceed them should cause throttling/OOM-kill rather than unbounded growth.

## Finding 5 — NGINX retry behavior inconsistent by route (identified via log analysis)
- Risk and evidence: log_analysis.md shows `/ready` and `/instance`
  requests retried to a healthy backend on failure (19/19 succeeded),
  while `/health`, `/records`, `/counter`, and `/` did not retry at all
  during a historical incident.
- Impact: Inconsistent failover means some endpoints have no resilience
  to a single backend failure, while others do — clients hitting the
  non-retrying endpoints experience visible errors during a partial outage.
- Implemented fix / commit: None — evaluated (Decision 5 in decisions.md)
  but not changed, to avoid introducing untested behavior late in the
  assessment window.
- Production follow-up: Configure `proxy_next_upstream error timeout;`
  consistently for all routes, paired with monitoring/alerting on
  upstream failure rates so retries don't silently mask a failing backend.
- How to verify: Re-run failure_test.py while monitoring which paths
  retry vs fail outright; all should retry consistently after the fix.

## Finding 6 — No centralized/aggregated logging or monitoring
- Risk and evidence: Logs are only accessible via `docker compose logs`
  per-container, with no aggregation, retention policy, or alerting.
- Impact: In production, an incident like the one in log_analysis.md
  could go unnoticed until a user reports it, since nothing proactively
  alerts on error-rate spikes or backend unavailability.
- Implemented fix / commit: None — out of scope for this local lab
  environment, but a real gap for production.
- Production follow-up: Ship logs to a centralized system (e.g. ELK,
  Loki, CloudWatch) and add alerting on error-rate thresholds and
  container health-check failures.
- How to verify: N/A locally; in production, verify an alert fires when
  a synthetic failure is injected.

## Finding 7 — Single point of failure: one PostgreSQL, one Redis instance
- Risk and evidence: docker-compose.yml runs exactly one postgres and
  one redis container each, with no replication.
- Impact: If either container fails, the entire application loses
  read/write capability for that dependency (confirmed by failure_test.py
  logic, though that script only tests app-layer failure, not DB failure).
- Implemented fix / commit: None — matches the assessment's intended
  scope (single-instance lab environment), but a real production risk.
- Production follow-up: Use a managed database service with replication/
  failover (e.g. RDS Multi-AZ, Redis Sentinel/Cluster) instead of a
  single container instance.
- How to verify: Stop the postgres container and confirm /ready and
  /records fail until it's restored — demonstrates the current lack of
  redundancy.

## Finding 8 — restart policy set to "no" for app containers
- Risk and evidence: The x-app anchor in docker-compose.yml sets
  `restart: "no"` for app-01 and app-02.
- Impact: If an app container crashes for any reason, Docker will not
  automatically restart it — it stays down until manually restarted,
  reducing availability.
- Implemented fix / commit: None — identified but not changed; unclear
  if "no" was intentional for this assessment (to make failures visible
  during grading) or an oversight.
- Production follow-up: Set `restart: unless-stopped` or `on-failure` for
  production so transient crashes self-heal without manual intervention.
- How to verify: Manually kill an app container process and observe
  whether Docker restarts it automatically (currently, it would not).
