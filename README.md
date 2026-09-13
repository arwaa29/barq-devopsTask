# BARQ DevOps Assessment - Arwa

A Flask + PostgreSQL + Redis service running behind NGINX, with two load-balanced
app instances. See `troubleshooting.md` for the full investigation journal,
`log_analysis.md` for historical log analysis, `decisions.md` and
`security_review.md` for design rationale and known risks.

## Prerequisites
- Docker Desktop (Linux containers) with Compose v2
- Linux or WSL2
- Python 3.12 (for validate.py / failure_test.py / log_analysis.py — standard
  library only, no extra installs needed)

## Setup
```bash
git clone https://github.com/arwaa29/barq-devopsTask.git
cd barq-devopsTask
cp .env.example .env
cp config/app.env.example config/app.env
# edit config/app.env if needed — defaults match this repo's docker-compose.yml
```

## Build and start
```bash
docker compose -p barq-assessment up --build -d
docker compose -p barq-assessment ps -a
```
Wait for `app-01` and `app-02` to show `(healthy)` (a few seconds).

## Test the endpoints
```bash
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/ready
curl -i http://127.0.0.1:8080/instance
curl -X POST -H 'Content-Type: application/json' -d '{"title":"Example"}' http://127.0.0.1:8080/records
curl http://127.0.0.1:8080/records
curl http://127.0.0.1:8080/counter
```

## Run validation
```bash
python3 validate.py
echo $?   # 0 = all checks passed
```

## Run the failure/recovery test
```bash
python3 failure_test.py
```
Stops `app-01`, confirms traffic/errors during the outage, restarts it, and
confirms it serves requests again.

## Backup and restore
```bash
./backup.sh
# creates ./backups/backup_<timestamp>.dump

./restore.sh ./backups/backup_<timestamp>.dump
```

## Historical log analysis
```bash
python3 log_analysis.py
```
See `log_analysis.md` for the full write-up.

## Stop
```bash
docker compose -p barq-assessment down
```
Do **not** add `--volumes` — that would delete the PostgreSQL data volume.

## Cleanup (full reset, including data)
```bash
docker compose -p barq-assessment down --volumes
rm -rf backups/*.dump
```

## Project layout
- `app/` — Flask application (server.py)
- `nginx/nginx.conf` — reverse proxy config, load balancing across app-01/app-02
- `docker-compose.yml` — full environment definition
- `config/app.env` — real environment values (gitignored); `app.env.example` is the safe template
- `validate.py` / `failure_test.py` — automated checks (see above)
- `backup.sh` / `restore.sh` — PostgreSQL backup/restore
- `log_analysis.py` — parses the three historical logs in `logs/`
- `.github/workflows/ci.yml` — CI: build, start, validate on every push/PR
- `troubleshooting.md`, `log_analysis.md`, `decisions.md`, `security_review.md`,
  `AI_USAGE.md` — required documentation