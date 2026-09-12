# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.

## Entry 1 / 9-9-2026 / 8:00 pm
- Symptom: `docker compose -p barq-assessment ps -a` shows that app01 and app02 both as "up (unhealthy)" 
while postgress and redis are "healthy" 
- Hypothesis: docker healthcheck is targeting a URL path that doesnot exist on app
- Command or test:  `docker compose -p barq-assessment logs app-01`
- Actual output: repeated log lines every 5s (`app-01  | 127.0.0.1 - - [09/Sep/2026 13:31:00] "GET /healthz HTTP/1.1" 404 -`)

- Failed attempt and what changed your thinking: first hypothesis matches the evidence so i was right
- Root cause: `docker-compose.yml` heathcheck test calls `('http://127.0.0.1:8080/healthz')` but `assessment/APPLICATION.md` difine the end point as `/health ` so there is no (z), app never implemnts /healthz so every check gets 404 and docker marks those container as unhealthy after repeated failures
- Fix: change healthcheck test in docker-compose.yml form `('http://127.0.0.1:8080/healthz')`to`('http://127.0.0.1:8080/health')`
- Retest evidence: doing again `docker compose -p barq-assessment ps -a` and it shows that both app-01,app-02 are healthy
- Related commit:investigation record for healthcheck 404 and duplicate instance
- Remaining uncertainty:Need to confirm the Flask app actually implements
  `/health` correctly (returns 200) once we look at the app code directly
  the 404 only proves the *path* is wrong, not that `/health` itself works


## Entry 2 / 10-9-2026 / 1:00 Am
- Symptom: docker-compose.yml showed app-02's INSTANCE_ID set to "app01" and this is identical to app01's instance so both backends will report the same and this violate distinct INSTANCE_ID requirement
- Hypothesis: may be a copy paste error app-02 service block was created from app-01's
- Command or test: manual review of docker-compose.yml
- Actual output: both blocks read `INSTANCE_ID: "app-01"`
- Failed attempt and what changed your thinking: nothing , i found it during manual review so there is no trials
- Root cause: app-02's environment block incorrectly overrides INSTANCE_ID
  with "app-01" instead of "app-02"
- Fix:change app-02's instance with "app-02 in docker-compose.yml
- Retest evidence:`curl -s http://127.0.0.1:8080/instance`
- Related commit:investigation record for healthcheck 404 and duplicate instance
- Remaining uncertainty:None on the config itself; still need to verify
  NGINX correctly load-balances between both and returns different IDs
  on repeated requests

## Entry 3 / 12-9-2026 / 12:30 Am
- Symptom: docker-compose.yml maps host port to container port 81 `["127.0.0.1:${PUBLIC_PORT:-8080}:81"]` while nginx.conf listening to port 80 so there is mismatch between files , alsso noticed  nginx.conf's upstream block pointed app-01 at port 8081 while app-01's actual port is 8080
- Hypothesis: may be lack of focus to wite right port 
- Command or test:manual review for docker.compse.yml and nginx.conf
- Actual output: docker-compose.yml: ports: ["127.0.0.1:${PUBLIC_PORT:-8080}:81"] , nginx.conf: `server app-01:8081`
- Failed attempt and what changed your thinking:first i decided to change host dide port mapping instead of nginx.conf as know before that nginx usually listen to port 80 but brief only requires host port 8080 to stay fixed
so i changed my decision to change the container port to 81 since ports <1024 need root privileges on linix, so 81 avoids running nginx as root
- Root cause: nginx.conf doesnot match what in docker-compose.yml
- Fix: change `listen: 80` to `listen: 81`and
  `server app-01:8081` to `server app-01:8080` in nginx.conf
- Retest evidence: nothing happen after rebuild but descover another issue which is in entry 4
- Related commit: docs: NGINX port mismatch and app host investigation
- Remaining uncertainty: none


## Entry 4 / 12-9-2026 / 2:30 Am
- Symptom: nginx returns 502 bad gateway on all routes even after fixing the listen port mismatch
also when run `docker compose -p barq-assessment logs --tail=50 nginx` shows connect() failed (111: Connection refused)" to app-01/app-02's
  container IP on port 8080
- Hypothesis: flask app and nginx may be listen to different interface as i notice that app host in code define the default app host 0.0.0.0 that listen to all interfaces but in docker-compose.yml it reach app through 127.0.0.1:8080 so it may override app host and block any  another interface 
- Command or test: docker exec app-01 sh -c "cat /proc/net/tcp | grep -i ':1F90'"
- Actual output: 0100007F:1F90 which decodes to 127.0.0.1:8080  and this is not reachable from outside containers 
- Failed attempt and what changed your thinking:nothing
- Root cause: docker-compose.yml shared app environmen sets `APP_HOST: "127.0.0.1"` which override the default host 0.0.0.0 and this makes flask bind only to localhost inside its container and unreachable from nginxeven they shaye same network
- Fix: change app host from "127.0.0.1" to "0.0.0.0" in docker-compose.yml
- Retest evidence:`curl -i http://127.0.0.1:8080/` it returns 200ok now not 502 bad gateway
- Related commit:docs: NGINX port mismatch and app host investigation
- Remaining uncertainty:/ready, /records, /counter still return
  postgres/redis "unavailable" ,separate issue, under investigation