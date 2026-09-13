# Technical decisions

Record at least 5 decisions. Include assumptions and limits.

## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.


# Technical decisions

## Decision 1 — NGINX container-side port (81 instead of 80)
- Choice: Kept NGINX listening on port 81 inside the container (matching the
  existing docker-compose.yml host mapping), rather than changing it to the
  conventional port 80.
- Why: Ports below 1024 require root privileges on Linux. Using 81 lets NGINX
  run without elevated privileges inside its container, aligning with the
  brief's "avoid root/privileged operation where practical."
- Alternative: Change docker-compose.yml's mapping to publish to container
  port 80 instead, matching NGINX's conventional default.
- Trade-off: 81 is a non-standard, less immediately recognizable port for
  anyone reading the config for the first time; a comment in nginx.conf
  mitigates this.
- Evidence / commit: troubleshooting.md Entry 3; fix applied in nginx.conf.
- Production improvement: In production, we'd run NGINX with capabilities
  (setcap) or behind a cloud load balancer that terminates on 80/443
  externally, keeping the container itself unprivileged either way.

## Decision 2 — PostgreSQL named volume path
- Choice: Mounted the postgres-data named volume at
  /var/lib/postgresql/data (Postgres's real data directory), and removed
  the tmpfs mount that previously claimed that same path.
- Why: The starter config had the named volume mounted at /backup (unused
  by Postgres) while the real data path was tmpfs (memory-only), meaning no
  data actually persisted across container recreation.
- Alternative: Keep a separate backup-only volume in addition to the data
  volume, for redundancy.
- Trade-off: None significant — this is the standard, correct way to persist
  Postgres data in Docker.
- Evidence / commit: troubleshooting.md Entry 6; verified by creating a
  record, recreating the postgres container, and confirming the record
  survived.
- Production improvement: Add scheduled automated backups (e.g. via
  pg_dump on a cron/sidecar) in addition to the volume, and store backups
  off-host (e.g. object storage) rather than only locally.

## Decision 3 — Redis persistence left disabled
- Choice: Left Redis configured with `--save "" --appendonly no`
  (no snapshotting, no append-only file) — counter data is not persisted
  across restarts.
- Why: The only data in Redis is a simple, non-critical request counter.
  The brief asks for persistence "where appropriate" — for this use case,
  losing the counter on restart has no real operational impact.
- Alternative: Enable AOF (`--appendonly yes`) for durability.
- Trade-off: Counter resets to 0 whenever the redis container restarts;
  acceptable since the counter isn't used for anything business-critical.
- Evidence / commit: Observed during troubleshooting Entry 6 investigation.
- Production improvement: If Redis were used for something more critical
  (session data, real caching with cost-to-rebuild), we would enable AOF
  or RDB snapshotting.

## Decision 4 — Secret handling for config/app.env
- Choice: Stopped tracking config/app.env in git, added it to .gitignore,
  and created config/app.env.example with placeholder values instead.
- Why: config/app.env contained a real (lab) PostgreSQL password and was
  being tracked/pushed to a public GitHub repo, violating "keep secrets out
  of images, code and Compose."
- Alternative: Rewrite git history to remove the password from all past
  commits entirely.
- Trade-off: The password remains visible in earlier commit history (not
  rewritten) since this is synthetic lab data, not a real production
  secret, and rewriting history carries its own risks; documented here as
  a known, accepted limitation instead.
- Evidence / commit: troubleshooting.md Entry 5; config/app.env.example
  and .gitignore commits.
- Production improvement: Use a real secrets manager (Docker secrets,
  AWS Secrets Manager, HashiCorp Vault) instead of any .env file for
  production credentials, and enable pre-commit secret scanning.

## Decision 5 — proxy_next_upstream retry behavior: left as-is after evaluation
- Choice: Evaluated the starter's `proxy_next_upstream off;` setting during
  log analysis, and chose not to change it despite finding it caused
  inconsistent retry behavior across endpoints during the historical
  incident (log_analysis.md, Q6-9).
- Why: Changing this now, this late, without dedicated time to test its
  effect on the current environment, risked introducing new untested
  behavior close to submission. Documenting the finding was prioritized
  over an untested live change.
- Alternative: Enable `proxy_next_upstream error timeout;` for automatic
  failover on every route.
- Trade-off: Current setup only fails over on /ready and /instance-style
  behavior observed historically; a live retry-all config might mask
  backend failures without proper monitoring.
- Evidence / commit: log_analysis.md correlation section.
- Production improvement: Enable next_upstream retries with bounded
  attempts, paired with alerting on upstream failure rate.

## Decision 6 — validate.py/failure_test.py use only Python standard library
- Choice: Built validate.py and failure_test.py using only urllib, socket,
  and subprocess (no requests, pytest, or other third-party packages).
- Why: Guarantees the scripts run identically in CI and locally without
  needing a requirements.txt install step just for tooling, reducing
  moving parts in the CI pipeline.
- Alternative: Use the `requests` library for cleaner HTTP code.
- Trade-off: Slightly more verbose code (manual JSON parsing, manual
  error handling) versus requests' more ergonomic API.
- Evidence / commit: validate.py, failure_test.py.
- Production improvement: For a larger test suite, adopt pytest with
  fixtures for more maintainable test structure.